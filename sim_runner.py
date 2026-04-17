from __future__ import annotations

"""Multi-pair simultaneous simulation runner.

Dynamically discovers the best pairs via PairSelector, optionally uses
ML predictions for position sizing, and runs multiple strategies in parallel.

Usage:
    py sim_runner.py [--poll 60] [--warmup 30] [--ml]
"""

import argparse
import logging
import os
import time
from datetime import datetime, timedelta

import yaml

from exchange.coinbase_client import CoinbaseClient, GRANULARITY_MAP
from exchange.models import Candle
from engine.simulator import Simulator
from data.candle_store import CandleStore
from data.trade_logger import TradeLogger
from strategies.grid_strategy import GridStrategy
from intelligence.strategy_orchestrator import StrategyOrchestrator
from intelligence.pair_selector import PairSelector, load_pair_selector_config
from intelligence.ml_predictor import MLPredictor, load_ml_config
from intelligence.volatility_predictor import VolatilityPredictor, VolatilityPrediction
from strategies.base_strategy import BaseStrategy
from exchange.ws_recorder import WSRecorder
from engine.momentum_engine import MomentumEngine, PAIRS as MOMENTUM_PAIRS
from engine.momentum_scanner import MomentumScanner

logger = logging.getLogger(__name__)


def _fmt_price(price: float) -> str:
    """Format price smartly: $1,234.56 for large, $0.004180 for sub-penny."""
    if price >= 1:
        return f"${price:,.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    else:
        return f"${price:.6f}"


# --- Per-pair engine (lightweight, no polling loop) ---

class PairEngine:
    """Manages one pair's strategy + simulator. No polling — called externally."""

    def __init__(
        self,
        name: str,
        strategy: BaseStrategy,
        pair: str,
        granularity: str,
        allocation_usd: float,
        maker_fee: float = 0.004,
        taker_fee: float = 0.006,
        slippage: float = 0.001,
    ):
        self.name = name
        self.pair = pair
        self.granularity = granularity
        self.allocation = allocation_usd
        self.strategy = strategy

        self.simulator = Simulator(
            starting_balance_usd=allocation_usd,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            slippage=slippage,
        )

        self.last_candle_ts: datetime | None = None
        self.last_price: float = 0.0
        self.candles_fed: int = 0
        self.trade_count: int = 0

    def process_candles(self, candles: list[Candle], size_multiplier: float = 1.0,
                        warmup: bool = False) -> list[dict]:
        """Feed new candles to strategy, execute signals. Returns trade events."""
        events = []
        for candle in candles:
            if self.last_candle_ts is not None and candle.timestamp <= self.last_candle_ts:
                continue

            self.last_candle_ts = candle.timestamp
            self.last_price = candle.close
            self.candles_fed += 1

            signals = self.strategy.on_candle(candle, warmup=warmup)
            for signal in signals:
                # Apply ML size multiplier to buy signals
                if size_multiplier < 1.0 and signal.action == "buy" and signal.amount_usd:
                    signal.amount_usd = signal.amount_usd * size_multiplier
                    if signal.amount_usd < 1.0:
                        continue  # Skip tiny trades

                price = signal.limit_price if signal.order_type == "limit" and signal.limit_price else candle.close
                trade = self.simulator.execute(signal, price, candle.timestamp)
                if trade:
                    self.trade_count += 1
                    events.append({
                        "pair": self.pair,
                        "name": self.name,
                        "trade": trade,
                    })

        return events

    def get_equity(self) -> float:
        return self.simulator.get_equity({self.pair: self.last_price})

    def has_open_positions(self) -> bool:
        """Check if this engine has any open grid positions (holding crypto)."""
        if hasattr(self.strategy, 'grid_levels'):
            return any(level.holding for level in self.strategy.grid_levels)
        return self.simulator.balance_usd < (self.simulator.starting_balance - 1.0)


# --- Multi-pair runner ---

class SimRunner:
    def __init__(
        self,
        poll_seconds: int = 60,
        warmup_days: int = 30,
        use_ml: bool = False,
    ):
        self.poll_seconds = poll_seconds
        self.warmup_days = warmup_days
        self.use_ml = use_ml
        self.client = CoinbaseClient()
        self.candle_store = CandleStore("data/candles.db")
        self.trade_logger = TradeLogger("data/candles.db")
        self.engines: list[PairEngine] = []
        self.total_allocation: float = 0.0
        self.session_start = datetime.now()
        self.equity_history: list[tuple[datetime, float]] = []
        self.running = False

        # ML predictor (only created if --ml)
        self.ml_predictor: MLPredictor | None = None
        # Pending outcome checks: {prediction_id: (pair, predicted_candle_ts, candles_remaining)}
        self._pending_outcomes: dict[int, dict] = {}

        # Volatility predictor (always active when prediction_mode=volatility)
        self.vol_predictor: VolatilityPredictor | None = None
        self._latest_vol_predictions: dict[str, VolatilityPrediction] = {}
        self._last_vol_train: datetime | None = None
        self._last_vol_eval: datetime | None = None
        self._vol_eval_errors: list[float] = []  # recent error percentages for auto-retrain

        # Loss limits
        self._trading_paused: bool = False
        self._pause_reason: str = ""
        self._pause_until: datetime | None = None
        self._day_start_equity: float = 0.0
        self._week_start_equity: float = 0.0
        self._last_day_reset: datetime | None = None
        self._last_week_reset: datetime | None = None

        # Risk config from bot_master.yaml
        self._max_loss_per_day: float = 30.0
        self._max_loss_per_week: float = 75.0

        # Pair selector for periodic rescans
        self.pair_selector: PairSelector | None = None
        self._last_full_scan: datetime | None = None
        self._last_quick_check: datetime | None = None

        # Feedback loop state
        self._learned_spacing_prefs: dict[str, float] = {}   # pair -> multiplier
        self._vol_train_windows: dict[str, int] = {}          # pair -> days
        self._vol_improvement_streak: dict[str, int] = {}     # pair -> consecutive improvements

        # Momentum rotation engine (optional, runs alongside grid)
        self.momentum_engine: MomentumEngine | None = None
        self.momentum_scanner: MomentumScanner | None = None
        self._last_momentum_scan: datetime | None = None
        self._momentum_scan_interval_hours = 24  # rescan every 24h

        # WebSocket tick recorder for stop comparison analysis
        self._ws_recorder = WSRecorder()

    def add_pair(
        self,
        name: str,
        strategy: BaseStrategy,
        pair: str,
        granularity: str,
        allocation_usd: float,
        maker_fee: float = 0.004,
        taker_fee: float = 0.006,
        slippage: float = 0.001,
    ):
        engine = PairEngine(
            name=name,
            strategy=strategy,
            pair=pair,
            granularity=granularity,
            allocation_usd=allocation_usd,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            slippage=slippage,
        )
        self.engines.append(engine)
        self.total_allocation += allocation_usd

    def warmup_all(self):
        """Warmup all pair engines with historical data.

        Warmup only updates indicators (EMA, ADX, candle history for adaptive range).
        No trades are executed and no positions are created during warmup.
        """
        for engine in self.engines:
            end = datetime.now()
            start = end - timedelta(days=self.warmup_days)

            candles = self.candle_store.get_candles(engine.pair, engine.granularity, start, end)
            interval = GRANULARITY_MAP.get(engine.granularity, timedelta(hours=1))
            expected = int(self.warmup_days * 24 * 3600 / interval.total_seconds() * 0.8)

            if not candles or len(candles) < expected:
                print(f"  Fetching {self.warmup_days}d warmup for {engine.pair}...")
                fetched = self.client.get_candles(engine.pair, engine.granularity, start, end)
                if fetched:
                    self.candle_store.save_candles(engine.pair, engine.granularity, fetched)
                candles = self.candle_store.get_candles(engine.pair, engine.granularity, start, end) or fetched

            if candles:
                engine.process_candles(candles, warmup=True)
                engine.trade_count = 0
                engine.candles_fed = 0
                # Set last_candle_ts to NOW so first live poll only picks up fresh candles
                engine.last_candle_ts = datetime.now()
                print(f"  {engine.name:<20} warmed up with {len(candles)} candles (last: {engine.last_candle_ts})")
            else:
                engine.last_candle_ts = datetime.now()
                print(f"  {engine.name:<20} WARNING: no warmup data")

    def _ws_start_recording(self, pair: str):
        """Start WebSocket recording when a position is opened."""
        try:
            trade_id = f"{pair}_{int(time.time())}"
            self._ws_recorder.start(pair, trade_id)
            logger.info("WS recorder started for %s (id=%s)", pair, trade_id)
        except Exception as e:
            logger.warning("WS recorder failed to start: %s", e)

    def _ws_stop_and_compare(self, pair: str, trade: "Trade"):
        """Stop WebSocket recording and log comparison after a sell."""
        try:
            tick_count = self._ws_recorder.stop()
            if tick_count < 10:
                logger.info("WS recorder: only %d ticks, skipping comparison", tick_count)
                return
            # Get stop prices from the holding (already sold, but we can reconstruct)
            holding_info = getattr(self.momentum_engine, '_last_exit_snapshot', None)
            atr_stop = 0.0
            trail_stop = 0.0
            entry_price = trade.price  # fallback
            if holding_info and isinstance(holding_info, dict):
                atr_stop = holding_info.get("atr_stop_price", 0.0)
                trail_stop = holding_info.get("trail_stop_price", 0.0)
                entry_price = holding_info.get("entry_price", trade.price)
            result = self._ws_recorder.compare_stops(
                entry_price=entry_price,
                atr_stop=atr_stop,
                trail_stop=trail_stop,
                actual_sell_price=trade.price,
            )
            if result:
                summary = result.get("summary", "no data")
                logger.info("WS vs Poll comparison: %s (%d ticks over %.0fs)",
                            summary, result["total_ticks"], result["duration_seconds"])
                self.trade_logger.log_momentum_event(
                    "ws_comparison",
                    f"[WS] {pair.replace('-USD', '')}: {summary}",
                    f"Ticks: {result['total_ticks']}, Duration: {result['duration_seconds']:.0f}s, "
                    f"Poll sell: ${result['sell_price_poll']:.4f}, WS sell: ${result['sell_price_ws']:.4f}",
                )
        except Exception as e:
            logger.warning("WS recorder comparison failed: %s", e)

    def _run_momentum_scan(self):
        """Run the momentum scanner to find best coins, excluding grid pairs."""
        if not self.momentum_scanner or not self.momentum_engine:
            return

        grid_pairs = {e.pair for e in self.engines}
        old_pairs = set(self.momentum_engine.pairs)
        pairs = self.momentum_scanner.scan(exclude_pairs=grid_pairs)

        if pairs:
            self.momentum_engine.update_pairs(pairs)
            print(f"  Momentum scanner: {len(pairs)} pairs selected (excluding {len(grid_pairs)} grid pairs)")

            # Warmup any newly added pairs so engine can evaluate them immediately
            new_pairs = set(pairs) - old_pairs
            if new_pairs:
                end = datetime.now()
                start = end - timedelta(hours=900)
                for pair in new_pairs:
                    if len(self.momentum_engine._closes.get(pair, [])) >= 720:
                        continue  # already has data
                    candles = self.candle_store.get_candles(pair, "ONE_HOUR", start, end)
                    if not candles or len(candles) < 100:
                        fetched = self.client.get_candles(pair, "ONE_HOUR", start, end)
                        if fetched:
                            self.candle_store.save_candles(pair, "ONE_HOUR", fetched)
                        candles = self.candle_store.get_candles(pair, "ONE_HOUR", start, end) or fetched
                    if candles:
                        for c in candles:
                            self.momentum_engine.feed_candle(pair, c, warmup=True)
                        print(f"  Warmed new pair {pair} with {len(candles)} candles")
        else:
            print("  Momentum scanner: no pairs found, keeping current list")

        self._last_momentum_scan = datetime.now()

    def _restore_momentum_state(self) -> bool:
        """Restore engine state from DB after a restart (not a reset).

        Reads the last equity snapshot and trade history to reconstruct
        cash, holdings, and trade count so the engine doesn't re-buy
        positions it already sold.

        Returns True if state was restored, False if no prior state exists.
        """
        import sqlite3, json as _json
        try:
            conn = sqlite3.connect(self.trade_logger.db_path)
            conn.row_factory = sqlite3.Row

            # Get last equity snapshot
            eq_row = conn.execute(
                "SELECT * FROM momentum_equity ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not eq_row:
                conn.close()
                return False

            # Restore cash and status
            self.momentum_engine.cash = eq_row["cash"]
            self.momentum_engine.status = eq_row["status"] or "cash"

            # Restore holdings from the snapshot JSON
            try:
                holdings_json = eq_row["holdings"] or "[]"
            except (IndexError, KeyError):
                holdings_json = "[]"
            holdings_data = _json.loads(holdings_json)

            # Rebuild MomentumHolding objects
            from engine.momentum_engine import MomentumHolding
            self.momentum_engine.holdings = {}
            for h in holdings_data:
                pair = h["pair"]

                # Ensure the held pair is in the engine's tracked pairs
                if pair not in self.momentum_engine.pairs:
                    self.momentum_engine.pairs.append(pair)
                if pair not in self.momentum_engine._closes:
                    self.momentum_engine._closes[pair] = []
                    self.momentum_engine._highs[pair] = []
                    self.momentum_engine._lows[pair] = []
                    self.momentum_engine._timestamps[pair] = []

                # Seed current price into _closes if empty (so get_equity works)
                if not self.momentum_engine._closes[pair] and h.get("current_price"):
                    self.momentum_engine._closes[pair].append(h["current_price"])

                # Fetch latest price from exchange to get accurate equity
                try:
                    live_price = self.client.get_ticker_price(pair)
                    if live_price:
                        if self.momentum_engine._closes[pair]:
                            self.momentum_engine._closes[pair][-1] = live_price
                        else:
                            self.momentum_engine._closes[pair].append(live_price)
                except Exception:
                    pass

                # Restore or recalculate stop prices
                entry_price = h["entry_price"]
                saved_stop = h.get("atr_stop_price") or h.get("stop_price") or 0
                if saved_stop <= 0 and entry_price > 0:
                    # Recalculate: try ATR, fallback to 8%
                    from engine.momentum_engine import _atr, ATR_STOP_LOOKBACK, ATR_STOP_MULT
                    atr = _atr(
                        self.momentum_engine._highs.get(pair, []),
                        self.momentum_engine._lows.get(pair, []),
                        self.momentum_engine._closes.get(pair, []),
                        ATR_STOP_LOOKBACK,
                    )
                    if atr and entry_price > 0:
                        saved_stop = entry_price * (1 - (atr / entry_price) * ATR_STOP_MULT)
                    else:
                        saved_stop = entry_price * 0.92
                    logger.info("Recalculated stop for %s: $%.4f", pair, saved_stop)

                holding = MomentumHolding(
                    pair=pair,
                    shares=h["shares"],
                    entry_price=entry_price,
                    entry_time=datetime.fromisoformat(h["entry_time"]) if h.get("entry_time") else datetime.now(),
                    peak_price=h.get("peak_price", h.get("current_price", 0)),
                    atr_stop_price=saved_stop,
                    trail_stop_price=h.get("trail_stop_price", 0.0),
                    ticks_above_tighten=h.get("ticks_above_tighten", 0),
                    ticks_since_new_peak=h.get("ticks_since_new_peak", 0),
                )
                self.momentum_engine.holdings[pair] = holding

            # Restore trade count
            trade_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM momentum_trades"
            ).fetchone()["cnt"]
            self.momentum_engine.trade_count = trade_count

            # Restore same-coin 24h lockout from the most recent sell so the
            # engine doesn't re-buy a coin it just sold after a container restart.
            last_sell = conn.execute(
                "SELECT pair, timestamp FROM momentum_trades WHERE side = 'sell' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if last_sell:
                try:
                    self.momentum_engine._last_sold_pair = last_sell["pair"]
                    self.momentum_engine._last_sold_time = datetime.fromisoformat(last_sell["timestamp"])
                except Exception:
                    pass

            # Set state flags based on whether we're holding
            if self.momentum_engine.holdings:
                self.momentum_engine._was_cash = False
                self.momentum_engine.status = "holding"
                held = [p.replace('-USD', '') for p in self.momentum_engine.holdings]
                self.momentum_engine.status_detail = f"Restored — holding {', '.join(held)}"
                # Set peak equity from DB snapshot (more reliable than computing now)
                self.momentum_engine._peak_equity = max(
                    eq_row["equity"], self.momentum_engine.get_equity()
                )
            else:
                self.momentum_engine._was_cash = True
                self.momentum_engine.status = "cash"
                self.momentum_engine.status_detail = "Restored — watching for signals"

            conn.close()
            logger.info("Restored momentum state: cash=$%.2f, %d holdings, %d trades, equity=$%.2f",
                        self.momentum_engine.cash, len(self.momentum_engine.holdings),
                        trade_count, self.momentum_engine.get_equity())
            return True

        except Exception as e:
            logger.warning("Could not restore momentum state: %s", e)
            return False

    def _warmup_momentum(self, clear_tables: bool = False):
        """Warmup momentum engine with historical hourly candles."""
        if not self.momentum_engine:
            return

        # Only clear tables on explicit reset, NOT on normal restart
        if clear_tables:
            try:
                import sqlite3
                conn = sqlite3.connect(self.trade_logger.db_path)
                for table in ["momentum_trades", "momentum_equity", "momentum_events"]:
                    try:
                        conn.execute(f"DELETE FROM {table}")
                    except Exception:
                        pass
                conn.commit()
                conn.close()
                logger.info("Cleared momentum tables for fresh start")
            except Exception as e:
                logger.warning("Could not clear momentum tables: %s", e)

        # Run scanner first to get the right pairs
        if self.momentum_scanner:
            print("\n  Running momentum scanner...")
            self._run_momentum_scan()

        pairs_to_warm = self.momentum_engine.pairs
        total = len(pairs_to_warm)
        print(f"\n  Warming up momentum rotation engine ({total} pairs)...")
        end = datetime.now()
        # Need ~750 hours (31 days) for LONG_LB + ~500 for BTC MA = ~750 hours minimum
        start = end - timedelta(hours=900)

        import json as _json
        warmup_start = time.time()

        for idx, pair in enumerate(pairs_to_warm):
            # Save progress for dashboard
            elapsed = time.time() - warmup_start
            avg_per_pair = elapsed / max(idx, 1)
            remaining = avg_per_pair * (total - idx)
            progress = {
                "step": "warmup",
                "pair": pair,
                "done": idx,
                "total": total,
                "pct": round(idx / total * 100),
                "elapsed_seconds": round(elapsed),
                "estimated_remaining": round(remaining),
            }
            try:
                with open("data/momentum_progress.json", "w") as f:
                    _json.dump(progress, f)
            except Exception:
                pass

            candles = self.candle_store.get_candles(pair, "ONE_HOUR", start, end)
            if not candles or len(candles) < 100:
                print(f"  Fetching warmup candles for {pair}...")
                fetched = self.client.get_candles(pair, "ONE_HOUR", start, end)
                if fetched:
                    self.candle_store.save_candles(pair, "ONE_HOUR", fetched)
                candles = self.candle_store.get_candles(pair, "ONE_HOUR", start, end) or fetched

            if candles:
                for c in candles:
                    self.momentum_engine.feed_candle(pair, c, warmup=True)
                print(f"  [{idx+1}/{total}] {pair:<12} warmed with {len(candles)} candles")
            else:
                print(f"  [{idx+1}/{total}] {pair:<12} WARNING: no warmup data")

        # Reset counters after warmup so rebalance triggers properly
        self.momentum_engine._warmup_done = True
        self.momentum_engine._hours_since_rebal = 0
        self.momentum_engine._hours_since_regime_check = 0
        self.momentum_engine._candles_fed = 0

        # Restore state from DB if we have prior trading history (not a fresh reset)
        restored = False
        if not clear_tables:
            restored = self._restore_momentum_state()

        if not restored:
            self.momentum_engine.trade_count = 0
            self.momentum_engine.trades = []
            self.momentum_engine.status = "cash" if not self.momentum_engine.regime_bullish else "ready"
            self.momentum_engine.status_detail = "Warmup complete — watching for signals"
        else:
            # Resume WS tick recording for any position we just restored on startup
            for h in self.momentum_engine.holdings:
                self._ws_start_recording(h.pair)

        # Mark warmup complete
        try:
            with open("data/momentum_progress.json", "w") as f:
                _json.dump({"step": "ready", "done": total, "total": total, "pct": 100}, f)
        except Exception:
            pass

        print(f"  Momentum engine ready — BTC MA500: ${self.momentum_engine.btc_ma:,.0f}, "
              f"regime: {'BULL' if self.momentum_engine.regime_bullish else 'BEAR'}")

        # Only trigger immediate entry if we didn't restore an existing position
        if not restored:
            btc_candles = self.candle_store.get_candles('BTC-USD', "ONE_HOUR", end - timedelta(hours=2), end)
            if btc_candles:
                last_btc = btc_candles[-1]
                trigger_candle = Candle(
                    pair='BTC-USD', granularity='ONE_HOUR',
                    timestamp=last_btc.timestamp + timedelta(seconds=1),
                    open=last_btc.open, high=last_btc.high, low=last_btc.low,
                    close=last_btc.close, volume=last_btc.volume,
                )
                trades = self.momentum_engine.feed_candle('BTC-USD', trigger_candle)
                for trade in trades:
                    try:
                        self.trade_logger.log_momentum_trade(trade)
                        if trade.side == "sell" and hasattr(self.momentum_engine, '_last_exit_snapshot') and self.momentum_engine._last_exit_snapshot:
                            self.trade_logger.log_exit_snapshot(self.momentum_engine._last_exit_snapshot)
                            self.momentum_engine._last_exit_snapshot = None
                        short = trade.pair.replace("-USD", "")
                        if trade.side == "buy":
                            title = f"[MOM] Bought {short} at {_fmt_price(trade.price)}"
                            self._ws_start_recording(trade.pair)
                        else:
                            title = f"[MOM] Sold {short} at {_fmt_price(trade.price)}"
                            self._ws_stop_and_compare(trade.pair, trade)
                        self.trade_logger.log_momentum_event(
                            f"momentum_{trade.side}", title, trade.reason
                        )
                        logger.info(f"[MOMENTUM] {trade.side.upper()} {short} @ {_fmt_price(trade.price)} — {trade.reason}")
                    except Exception as e:
                        logger.error(f"[MOMENTUM] Failed to log trade: {e}")
                if trades:
                    print(f"  Momentum engine: immediate entry — {len(trades)} trades executed")
                # Log gate evaluations from warmup entry check
                if hasattr(self.momentum_engine, '_gate_log') and self.momentum_engine._gate_log:
                    try:
                        self.trade_logger.log_momentum_gates(self.momentum_engine._gate_log)
                    except Exception as e:
                        logger.error(f"[MOMENTUM] Failed to log gates: {e}")

    def _poll_momentum(self):
        """Poll candles for all momentum pairs and feed to momentum engine."""
        if not self.momentum_engine:
            return

        import json

        # Check for reset flag (written by API /momentum/reset endpoint)
        reset_flag = os.path.join(os.path.dirname(__file__), "data", "momentum_reset.flag")
        if os.path.exists(reset_flag):
            try:
                os.remove(reset_flag)
            except Exception:
                pass
            logger.info("Momentum engine reset requested — reinitializing")
            alloc = self.momentum_engine.starting_balance
            fee = self.momentum_engine.fee_rate
            pairs = self.momentum_engine.pairs
            self.momentum_engine = MomentumEngine(
                allocation_usd=alloc, fee_rate=fee, pairs=pairs,
            )
            # Re-run warmup from DB so the engine has price history immediately
            self._warmup_momentum(clear_tables=True)
            logger.info("Momentum engine reset complete with $%.0f", alloc)

        # Check for manual sell flag
        sell_flag = os.path.join(os.path.dirname(__file__), "data", "momentum_sell.flag")
        if os.path.exists(sell_flag):
            try:
                with open(sell_flag, "r") as f:
                    sell_pair = f.read().strip()
                os.remove(sell_flag)
            except Exception:
                sell_pair = ""
            if sell_pair and sell_pair in self.momentum_engine.holdings:
                trade = self.momentum_engine._sell(
                    sell_pair, datetime.now(), "Manual sell from dashboard"
                )
                if trade:
                    self.momentum_engine._was_cash = not self.momentum_engine.holdings
                    # Apply cooldown just like an automatic exit
                    from engine.momentum_engine import EXIT_COOLDOWN
                    self.momentum_engine._exit_cooldown = EXIT_COOLDOWN
                    self.momentum_engine._hours_in_position = 0
                    self.momentum_engine._peak_equity = self.momentum_engine.get_equity()
                    if not self.momentum_engine.holdings:
                        self.momentum_engine.status = "cash"
                        self.momentum_engine.status_detail = "Manual sell — cooldown active"
                    self.trade_logger.log_momentum_trade(trade)
                    if hasattr(self.momentum_engine, '_last_exit_snapshot') and self.momentum_engine._last_exit_snapshot:
                        self.trade_logger.log_exit_snapshot(self.momentum_engine._last_exit_snapshot)
                        self.momentum_engine._last_exit_snapshot = None
                    short = trade.pair.replace("-USD", "")
                    self._ws_stop_and_compare(trade.pair, trade)
                    self.trade_logger.log_momentum_event(
                        "momentum_sell",
                        f"[MOM] Manual sold {short} at {_fmt_price(trade.price)}",
                        trade.reason,
                    )
                    logger.info("[MOMENTUM] MANUAL SELL %s @ %s", short, _fmt_price(trade.price))
                    # Snapshot equity immediately so dashboard updates
                    import json as _json
                    eq = self.momentum_engine.get_equity()
                    self.trade_logger.log_momentum_equity(
                        datetime.now(), eq,
                        self.momentum_engine.cash,
                        self.momentum_engine.get_positions_value(),
                        self.momentum_engine.status,
                        _json.dumps(self.momentum_engine.get_holdings_info()),
                    )

        # Check for skip cooldown flag
        skip_flag = os.path.join(os.path.dirname(__file__), "data", "momentum_skip_cooldown.flag")
        if os.path.exists(skip_flag):
            try:
                os.remove(skip_flag)
            except Exception:
                pass
            self.momentum_engine._exit_cooldown = 0
            logger.info("Momentum cooldown skipped by user — ready to re-enter")

        # Periodic rescan (every 24h)
        if (self.momentum_scanner and self._last_momentum_scan and
                (datetime.now() - self._last_momentum_scan).total_seconds() >
                self._momentum_scan_interval_hours * 3600):
            logger.info("Momentum scanner: periodic rescan triggered")
            self._run_momentum_scan()

        # Ticker-based stop check for held positions (runs every 60s)
        for pair in list(self.momentum_engine.holdings.keys()):
            price = self.client.get_ticker_price(pair)
            if price is None:
                continue
            trade = self.momentum_engine.check_stop_ticker(pair, price)
            if trade:
                self.trade_logger.log_momentum_trade(trade)
                if hasattr(self.momentum_engine, '_last_exit_snapshot') and self.momentum_engine._last_exit_snapshot:
                    self.trade_logger.log_exit_snapshot(self.momentum_engine._last_exit_snapshot)
                    self.momentum_engine._last_exit_snapshot = None
                short = trade.pair.replace("-USD", "")
                title = f"[MOM] Sold {short} at {_fmt_price(trade.price)}"
                self._ws_stop_and_compare(trade.pair, trade)
                self.trade_logger.log_momentum_event(
                    f"momentum_{trade.side}", title, trade.reason
                )
                logger.info(f"[MOMENTUM] STOP {short} @ {_fmt_price(trade.price)} — {trade.reason}")

        # Feed hourly candles for all pairs (rebalance/entry/history)
        for pair in self.momentum_engine.pairs:
            candles = self.client.get_latest_candles(pair, "ONE_HOUR", count=5)
            if not candles:
                continue
            self.candle_store.save_candles(pair, "ONE_HOUR", candles)

            for candle in candles:
                trades = self.momentum_engine.feed_candle(pair, candle)
                for trade in trades:
                    self.trade_logger.log_momentum_trade(trade)
                    if trade.side == "sell" and hasattr(self.momentum_engine, '_last_exit_snapshot') and self.momentum_engine._last_exit_snapshot:
                        self.trade_logger.log_exit_snapshot(self.momentum_engine._last_exit_snapshot)
                        self.momentum_engine._last_exit_snapshot = None
                    short = trade.pair.replace("-USD", "")
                    if trade.side == "buy":
                        title = f"[MOM] Bought {short} at {_fmt_price(trade.price)}"
                        self._ws_start_recording(trade.pair)
                    else:
                        title = f"[MOM] Sold {short} at {_fmt_price(trade.price)}"
                        self._ws_stop_and_compare(trade.pair, trade)
                    self.trade_logger.log_momentum_event(
                        f"momentum_{trade.side}", title, trade.reason
                    )
                    logger.info(f"[MOMENTUM] {trade.side.upper()} {short} @ {_fmt_price(trade.price)} — {trade.reason}")

        # Snapshot momentum equity
        now = datetime.now()
        mom = self.momentum_engine
        holdings_json = json.dumps(mom.get_holdings_info())
        self.trade_logger.log_momentum_equity(
            now, mom.get_equity(), mom.cash, mom.get_positions_value(),
            mom.status, holdings_json
        )

        # Refresh gate log every poll — even while holding — so the
        # scanner UI doesn't go stale. feed_candle only runs the full
        # entry/rebalance eval on new hourly candles, so within the hour
        # we'd otherwise re-write the same frozen rows every minute.
        try:
            mom.info_scan()
        except Exception as e:
            logger.error(f"[MOMENTUM] Failed info scan: {e}")

        # Log gate evaluations for every candidate this cycle
        if hasattr(mom, '_gate_log') and mom._gate_log:
            try:
                self.trade_logger.log_momentum_gates(mom._gate_log)
            except Exception as e:
                logger.error(f"[MOMENTUM] Failed to log gates: {e}")

        # Reset per-poll compute flag so next cycle's info_scan runs fresh
        mom._compute_ran_this_tick = False

        # Backfill follow-up prices for old gate log entries
        try:
            filled = self.trade_logger.backfill_gate_outcomes()
            if filled > 0:
                logger.info(f"[MOMENTUM] Backfilled {filled} gate log outcomes")
        except Exception as e:
            logger.error(f"[MOMENTUM] Failed to backfill gate outcomes: {e}")

        # Persist engine status for dashboard API
        try:
            status_path = os.path.join(os.path.dirname(__file__), "data", "momentum_status.json")
            status_dict = mom.get_status_dict()
            status_dict["ws_recorder"] = self._ws_recorder.get_status()
            with open(status_path, "w") as f:
                json.dump(status_dict, f, default=str)
        except Exception:
            pass

    def _evaluate_vol_accuracy(self):
        """Compare predicted volatility vs actual realized volatility.

        Runs every 12 hours. If predictions are off by >50% for 3 consecutive
        days (6 checks), triggers immediate retrain.
        """
        if not self.vol_predictor:
            return

        now = datetime.now()
        end = now
        start = end - timedelta(hours=12)

        for engine in self.engines:
            candles = self.candle_store.get_candles(engine.pair, "ONE_HOUR", start, end)
            if not candles or len(candles) < 10:
                continue

            # Compute actual realized vol over last 12h
            import numpy as np
            closes = [c.close for c in candles]
            log_rets = [np.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
            actual_vol = float(np.std(log_rets) * np.sqrt(24) * 100) if log_rets else 0

            # Get the prediction that was made ~12h ago
            pred = self._latest_vol_predictions.get(engine.pair)
            if pred is None:
                continue

            predicted_vol = pred.predicted_vol_12h
            error_pct = abs(predicted_vol - actual_vol) / actual_vol * 100 if actual_vol > 0 else 0

            self.trade_logger.log_vol_accuracy(engine.pair, predicted_vol, actual_vol)
            logger.info(
                f"[VOL EVAL] {engine.pair}: predicted={predicted_vol:.1f}% actual={actual_vol:.1f}% "
                f"error={error_pct:.0f}%"
            )

            # Loop 3: tune vol training window based on accuracy trend
            self._tune_vol_window(engine.pair, error_pct)

            self._vol_eval_errors.append(error_pct)

        self._last_vol_eval = now

        # Check if we need emergency retrain: >50% error for 6 consecutive checks (3 days)
        if len(self._vol_eval_errors) >= 6:
            recent = self._vol_eval_errors[-6:]
            if all(e > 50 for e in recent):
                logger.warning("[VOL] Predictions off by >50%% for 3 days — emergency retrain")
                self.trade_logger.log_self_check(
                    "vol_emergency_retrain",
                    f"Last 6 error checks all >50%: {[f'{e:.0f}%' for e in recent]}"
                )
                self._train_vol_models()
                self._vol_eval_errors.clear()

        # Keep only last 14 checks (7 days)
        if len(self._vol_eval_errors) > 14:
            self._vol_eval_errors = self._vol_eval_errors[-14:]

    def _check_loss_limits(self, total_equity: float) -> bool:
        """Check daily/weekly loss limits. Returns True if trading should be paused."""
        now = datetime.now()

        # Reset day tracker at midnight
        if self._last_day_reset is None or now.date() != self._last_day_reset.date():
            self._day_start_equity = total_equity
            self._last_day_reset = now
            # Clear daily pause if new day
            if self._pause_reason.startswith("daily"):
                self._trading_paused = False
                self._pause_reason = ""
                self._pause_until = None

        # Reset week tracker on Monday
        if self._last_week_reset is None or (now.weekday() == 0 and
                (now - self._last_week_reset).days >= 1):
            self._week_start_equity = total_equity
            self._last_week_reset = now
            if self._pause_reason.startswith("weekly"):
                self._trading_paused = False
                self._pause_reason = ""
                self._pause_until = None

        if self._trading_paused:
            if self._pause_until and now >= self._pause_until:
                logger.info("[SAFETY] Loss limit pause expired — resuming trading")
                self._trading_paused = False
                self._pause_reason = ""
                self._pause_until = None
            return self._trading_paused

        # Check daily loss
        day_loss = self._day_start_equity - total_equity
        if day_loss >= self._max_loss_per_day:
            tomorrow = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
            hours_left = (tomorrow - now).total_seconds() / 3600
            self._trading_paused = True
            self._pause_reason = f"daily loss limit (${day_loss:.2f} >= ${self._max_loss_per_day:.0f})"
            self._pause_until = tomorrow
            msg = (f"Trading paused — {self._pause_reason}. "
                   f"Resumes in {hours_left:.0f} hours.")
            logger.warning(f"[SAFETY] {msg}")
            self.trade_logger.log_self_check("daily_loss_pause", msg)
            return True

        # Check weekly loss
        week_loss = self._week_start_equity - total_equity
        if week_loss >= self._max_loss_per_week:
            days_until_monday = (7 - now.weekday()) % 7 or 7
            next_monday = now.replace(hour=0, minute=0, second=0) + timedelta(days=days_until_monday)
            hours_left = (next_monday - now).total_seconds() / 3600
            self._trading_paused = True
            self._pause_reason = f"weekly loss limit (${week_loss:.2f} >= ${self._max_loss_per_week:.0f})"
            self._pause_until = next_monday
            msg = (f"Trading paused — {self._pause_reason}. "
                   f"Resumes in {hours_left:.0f} hours.")
            logger.warning(f"[SAFETY] {msg}")
            self.trade_logger.log_self_check("weekly_loss_pause", msg)
            return True

        return False

    def _train_vol_models(self):
        """Train volatility models for all active pairs."""
        if not self.vol_predictor:
            return

        print("\n  Training volatility models (GARCH-LightGBM)...")

        # Fetch BTC candles for cross-market features (use max window)
        btc_candles = None
        end = datetime.now()
        max_window = max(self._vol_train_windows.values(), default=30)
        btc_start = end - timedelta(days=max(max_window, 30))
        btc_candles_raw = self.candle_store.get_candles("BTC-USD", "ONE_HOUR", btc_start, end)
        if btc_candles_raw and len(btc_candles_raw) >= 100:
            btc_candles = btc_candles_raw

        for engine in self.engines:
            # Use per-pair learned training window (Loop 3)
            train_days = self._vol_train_windows.get(engine.pair, 30)
            start = end - timedelta(days=train_days)
            candles = self.candle_store.get_candles(engine.pair, "ONE_HOUR", start, end)
            if not candles or len(candles) < 200:
                print(f"  {engine.pair:<12} vol skipped (only {len(candles) if candles else 0} candles)")
                continue

            meta = self.vol_predictor.train(engine.pair, candles, btc_candles)
            if meta:
                print(
                    f"  {engine.pair:<12} vol trained v{meta.version} "
                    f"(RMSE: {meta.validation_rmse:.4f}  R²: {meta.validation_r2:.3f}  "
                    f"vol_mean: {meta.vol_mean:.1f}%)"
                )
            else:
                print(f"  {engine.pair:<12} vol training failed")

        self._last_vol_train = datetime.now()

    def _run_vol_predictions(self):
        """Run volatility predictions for all engines and adjust grid spacing."""
        if not self.vol_predictor:
            return

        end = datetime.now()
        start = end - timedelta(days=7)

        # BTC candles for cross-market feature
        btc_candles = self.candle_store.get_candles("BTC-USD", "ONE_HOUR", start, end)

        for engine in self.engines:
            candles = self.candle_store.get_candles(engine.pair, "ONE_HOUR", start, end)
            if not candles or len(candles) < 50:
                continue

            pred = self.vol_predictor.predict(engine.pair, candles, btc_candles)
            if pred is None:
                continue

            self._latest_vol_predictions[engine.pair] = pred
            self.trade_logger.log_vol_prediction(pred)

            # Apply to grid strategy — only if model R² > 0 (better than mean)
            # Otherwise ATR-based spacing (computed inside grid_strategy) stays active
            meta = self.vol_predictor._metadata.get(engine.pair)
            r2 = meta.validation_r2 if meta else 0.0
            if r2 > 0 and hasattr(engine.strategy, 'apply_volatility_adjustment'):
                engine.strategy.apply_volatility_adjustment(
                    pred.spacing_multiplier, pred.vol_regime, pred.recommended_num_grids
                )
                layer = "ML override"
            else:
                # Reset ML override so ATR layer stays in control
                if hasattr(engine.strategy, '_vol_ml_override'):
                    engine.strategy._vol_ml_override = False
                atr_mult = getattr(engine.strategy, '_vol_spacing_multiplier', 1.0)
                layer = f"ATR (R²={r2:.3f}, atr_mult={atr_mult:.2f}x)"

            print(
                f"  [VOL] {engine.pair:<12} "
                f"pred={pred.predicted_vol_12h:.1f}%  "
                f"regime={pred.vol_regime:<8} "
                f"spacing={pred.spacing_multiplier:.2f}x  "
                f"grids={pred.recommended_num_grids}  "
                f"[{layer}]"
            )
            short = engine.pair.replace("-USD", "")
            self.trade_logger.log_event(
                "vol_check",
                f"{short} vol {pred.vol_regime} — spacing {pred.spacing_multiplier:.2f}x",
                f"Predicted 12h vol: {pred.predicted_vol_12h:.1f}% | {layer}",
                pair=engine.pair,
            )

    def _train_ml_models(self):
        """Train ML models for all active pairs using cached candles."""
        if not self.ml_predictor:
            return

        print("\n  Training ML models...")
        for engine in self.engines:
            end = datetime.now()
            start = end - timedelta(days=30)
            candles = self.candle_store.get_candles(engine.pair, "ONE_HOUR", start, end)
            if not candles or len(candles) < 100:
                print(f"  {engine.pair:<12} skipped (only {len(candles) if candles else 0} candles)")
                continue

            meta = self.ml_predictor.train(engine.pair, candles)
            if meta:
                print(f"  {engine.pair:<12} trained v{meta.version} (RMSE: {meta.validation_rmse:.4f}  R²: {meta.validation_r2:.3f}  features: {len(meta.feature_names)})")
            else:
                print(f"  {engine.pair:<12} training failed")

    def _cleanup_warmup_trades(self):
        """Remove any synthetic warmup trades from previous runs."""
        import sqlite3
        conn = sqlite3.connect("data/candles.db")
        try:
            deleted = conn.execute(
                "DELETE FROM sim_trades WHERE reason = 'warmup position'"
            ).rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old warmup position trades from DB")
        except Exception:
            pass
        finally:
            conn.close()

    def run(self):
        """Main polling loop — polls all pairs, prints combined dashboard."""
        self.running = True
        self._cleanup_warmup_trades()
        self._print_header()
        self.warmup_all()

        # Warmup momentum engine if active
        if self.momentum_engine:
            self._warmup_momentum()

        if self.use_ml:
            self._train_ml_models()

        # Train volatility models (always, independent of --ml flag)
        if self.vol_predictor:
            self._train_vol_models()

        # Log boot event
        pairs_str = ", ".join(e.pair.replace("-USD", "") for e in self.engines)
        self.trade_logger.log_event(
            "boot",
            f"Bot started — watching {len(self.engines)} pairs",
            f"Pairs: {pairs_str}",
        )

        print(f"\n  Live polling every {self.poll_seconds}s")
        if self.use_ml:
            print(f"  ML predictions: ENABLED")
        if self.vol_predictor:
            print(f"  Volatility forecasting: ENABLED (GARCH-LightGBM)")
        print(f"  Press Ctrl+C to stop.\n")

        try:
            while self.running:
                self._poll_all()
                self._check_periodic_tasks()
                time.sleep(self.poll_seconds)
        except KeyboardInterrupt:
            pass

        self._print_summary()

    def _poll_all(self):
        """Poll all pairs and process new candles."""
        now = datetime.now()
        total_equity = 0.0

        for engine in self.engines:
            candles = self.client.get_latest_candles(engine.pair, engine.granularity, count=5)
            if not candles:
                total_equity += engine.get_equity()
                continue

            self.candle_store.save_candles(engine.pair, engine.granularity, candles)

            # Skip trading signals if loss limits are hit (still poll/track equity)
            if self._trading_paused:
                total_equity += engine.get_equity()
                continue

            # ML prediction for latest candle
            size_multiplier = 1.0
            if self.use_ml and self.ml_predictor:
                size_multiplier = self._run_ml_prediction(engine, candles)

            events = engine.process_candles(candles, size_multiplier)
            for event in events:
                self._print_trade(event)
                self.trade_logger.log_trade(event["trade"])
                # Log trade event to activity feed
                trade = event["trade"]
                evt_type = "trade_buy" if trade.side == "buy" else "trade_sell"
                evt_title = f"{'Bought' if trade.side == 'buy' else 'Sold'} {trade.amount:,.0f} {trade.pair.replace('-USD', '')} at ${trade.price:,.4f}"
                self.trade_logger.log_event(evt_type, evt_title, trade.reason, pair=trade.pair)
                # Track completed grid cycles (sell = cycle complete)
                self._track_grid_cycle(engine, event)

            equity = engine.get_equity()
            total_equity += equity

        # Check pending ML outcome evaluations
        if self.use_ml:
            self._evaluate_pending_outcomes()

        # Run volatility predictions and adjust grid spacing
        if self.vol_predictor:
            self._run_vol_predictions()

        # Snapshot combined equity with proper balance/positions breakdown
        total_balance = sum(e.simulator.balance_usd for e in self.engines)
        total_positions = total_equity - total_balance
        self.equity_history.append((now, total_equity))
        self.trade_logger.log_equity(now, total_equity, total_balance, total_positions)

        # Check loss limits
        self._check_loss_limits(total_equity)

        # Poll momentum engine (independent from grid)
        self._poll_momentum()

        self._print_dashboard(total_equity)

    def _run_ml_prediction(self, engine: PairEngine, candles: list[Candle]) -> float:
        """Run ML prediction for a pair. Returns size multiplier."""
        if not self.ml_predictor:
            return 1.0

        # Get longer history for feature extraction
        end = datetime.now()
        start = end - timedelta(days=7)
        history = self.candle_store.get_candles(engine.pair, "ONE_HOUR", start, end)
        if not history or len(history) < 30:
            return 1.0

        pred = self.ml_predictor.predict(engine.pair, history)
        if pred is None:
            return 1.0

        # Log prediction to SQLite
        pred_id = self.trade_logger.log_ml_prediction(pred)

        # Track for outcome evaluation (4 candles later)
        self._pending_outcomes[pred_id] = {
            "pair": engine.pair,
            "timestamp": pred.timestamp,
            "price_at_prediction": candles[-1].close,
            "candles_remaining": self.ml_predictor.prediction_horizon,
        }

        # Print ML info
        arrow = "^" if pred.direction == "up" else ("v" if pred.direction == "down" else "-")
        dp = pred.do_predict if hasattr(pred, "do_predict") else "?"
        pct = pred.predicted_change_pct if hasattr(pred, "predicted_change_pct") else 0
        print(
            f"  [ML] {engine.pair:<12} {arrow} {pred.direction:<8} "
            f"pred={pct:+.2f}%  conf={pred.confidence:.1%}  "
            f"DI={dp}  action={pred.recommended_action}  "
            f"size={pred.recommended_size_pct:.0%}"
        )

        return self.ml_predictor.get_size_multiplier(pred)

    def _evaluate_pending_outcomes(self):
        """Check predictions that are now 4+ candles old and record actual outcome."""
        resolved = []
        for pred_id, info in self._pending_outcomes.items():
            info["candles_remaining"] -= 1
            if info["candles_remaining"] > 0:
                continue

            # Get current price for this pair
            pair = info["pair"]
            current_price = None
            for engine in self.engines:
                if engine.pair == pair:
                    current_price = engine.last_price
                    break

            if current_price and current_price > 0:
                price_change = (current_price - info["price_at_prediction"]) / info["price_at_prediction"]
                outcome = "up" if price_change > 0.005 else ("down" if price_change < -0.005 else "flat")
                self.trade_logger.update_ml_outcome(pred_id, outcome, price_change)

            resolved.append(pred_id)

        for pred_id in resolved:
            del self._pending_outcomes[pred_id]

    def _track_grid_cycle(self, engine: PairEngine, event: dict):
        """Log completed grid cycles (sell events) with spacing and regime context."""
        trade = event["trade"]
        if trade.side != "sell" or "grid sell" not in trade.reason:
            return

        # Extract buy price from the grid level's entry_price
        sell_price = trade.price
        buy_price = 0.0
        amount = trade.amount

        # Try to find the matching buy entry from the strategy's grid levels
        if hasattr(engine.strategy, 'grid_spacing'):
            buy_price = sell_price - engine.strategy.grid_spacing
            if buy_price <= 0:
                buy_price = sell_price * 0.97  # fallback estimate

        # Calculate P&L
        cost = buy_price * amount
        revenue = sell_price * amount
        fee_rate = 0.006  # taker fee
        pnl = revenue - cost - (cost + revenue) * fee_rate

        # Spacing as percentage
        spacing_pct = (engine.strategy.grid_spacing / buy_price * 100) if buy_price > 0 else 0

        # Get current vol context
        vol_pred = self._latest_vol_predictions.get(engine.pair)
        vol_regime = vol_pred.vol_regime if vol_pred else ""
        spacing_mult = vol_pred.spacing_multiplier if vol_pred else 1.0

        self.trade_logger.log_grid_cycle(
            pair=engine.pair,
            buy_price=buy_price,
            sell_price=sell_price,
            amount=amount,
            pnl_usd=pnl,
            spacing_pct=spacing_pct,
            vol_regime=vol_regime,
            spacing_multiplier=spacing_mult,
        )

        # Improvement 6: compound cycle profit back into allocation
        if hasattr(engine.strategy, 'apply_cycle_profit'):
            engine.strategy.apply_cycle_profit(pnl)

    # ------------------------------------------------------------------
    # Feedback loops
    # ------------------------------------------------------------------

    def _learn_spacing_preferences(self):
        """Loop 1: Learn which grid spacing works best per pair."""
        for engine in self.engines:
            pair = engine.pair
            stats = self.trade_logger.get_spacing_stats(pair, since_days=7)
            total_cycles = sum(s["cycle_count"] for s in stats)
            if total_cycles < 5:
                continue  # not enough data

            # Find the spacing bucket with highest avg profit
            best = max(stats, key=lambda s: s["avg_pnl"])
            best_spacing = best["spacing_bucket"]
            best_avg = best["avg_pnl"]

            # Current spacing from strategy
            current_spacing = getattr(engine.strategy, 'grid_spacing', 0)
            current_price = getattr(engine.strategy, '_last_price', 0)
            current_pct = (current_spacing / current_price * 100) if current_price > 0 else 2.0

            if current_pct <= 0:
                continue

            # Compute nudge: ratio of best-performing spacing to current
            nudge = best_spacing / current_pct if current_pct > 0 else 1.0
            nudge = max(0.7, min(1.3, nudge))

            # Blend with existing preference (exponential smoothing)
            old_pref = self._learned_spacing_prefs.get(pair, 1.0)
            new_pref = 0.7 * old_pref + 0.3 * nudge

            if abs(new_pref - old_pref) > 0.02:  # only log meaningful changes
                name = pair.replace("-USD", "")
                # Find worst spacing for comparison
                worst = min(stats, key=lambda s: s["avg_pnl"])
                desc = (
                    f"{name} learned that {best_spacing:.1f}% spacing works better "
                    f"— averaging ${best_avg:.2f}/cycle vs ${worst['avg_pnl']:.2f} at "
                    f"{worst['spacing_bucket']:.1f}%"
                )
                self.trade_logger.log_adaptation(pair, "spacing_learned", desc, old_pref, new_pref)
                self.trade_logger.log_event(
                    "adaptation", f"{name}: spacing preference updated",
                    desc, pair=pair,
                )

            self._learned_spacing_prefs[pair] = new_pref

            # Apply to strategy
            if hasattr(engine.strategy, 'apply_learned_spacing'):
                engine.strategy.apply_learned_spacing(new_pref)

    def _learn_pair_performance(self):
        """Loop 2: Compare actual P&L to backtest prediction and adjust scores."""
        if not self.pair_selector:
            return

        for engine in self.engines:
            pair = engine.pair
            # Check if pair has been active long enough (48h)
            first_trade = self.trade_logger.get_pair_first_trade_time(pair)
            if not first_trade:
                continue
            try:
                first_dt = datetime.fromisoformat(first_trade)
            except (ValueError, TypeError):
                continue
            hours_active = (datetime.now() - first_dt).total_seconds() / 3600
            if hours_active < 48:
                continue

            # Get actual P&L from last 48h of grid cycles
            actual_pnl = self.trade_logger.get_pair_actual_pnl(pair, since_hours=48)

            # Get backtest prediction from the pair's score
            scores = self.pair_selector.get_active_scores()
            pair_score = next((s for s in scores if s.pair == pair), None)
            if not pair_score or pair_score.backtest_pnl == 0:
                continue

            predicted_pnl = pair_score.backtest_pnl

            # Compute ratio of actual vs predicted
            if predicted_pnl > 0:
                ratio = actual_pnl / predicted_pnl
            elif actual_pnl > 0:
                ratio = 1.5  # actual positive but predicted zero/negative = overperformer
            else:
                ratio = 1.0  # both zero or negative, no signal

            # Compute adjustment
            if ratio > 1.2:
                adj = min(0.3, 0.1 * (ratio - 1))
            elif ratio < 0.8:
                adj = max(-0.3, -0.1 * (1 - ratio))
            else:
                adj = 0.0

            # Blend with existing
            old_adj = self.pair_selector._performance_adjustments.get(pair, 0.0)
            new_adj = 0.6 * old_adj + 0.4 * adj

            if abs(new_adj) > 0.01 and abs(new_adj - old_adj) > 0.005:
                name = pair.replace("-USD", "")
                pct = int(abs(ratio - 1) * 100)
                if new_adj > 0:
                    desc = f"{name} is outperforming its scan score by {pct}% — boosted for next rescan"
                else:
                    desc = f"{name} is underperforming its scan score by {pct}% — penalized for next rescan"
                self.trade_logger.log_adaptation(pair, "pair_adjustment", desc, old_adj, new_adj)
                self.trade_logger.log_event(
                    "adaptation", f"{name}: scan score adjusted ({new_adj:+.2f})",
                    desc, pair=pair,
                )

            self.pair_selector._performance_adjustments[pair] = new_adj

    def _tune_vol_window(self, pair: str, current_error: float):
        """Loop 3: Self-tune vol model training window based on accuracy trend."""
        history = self.trade_logger.get_vol_accuracy_history(pair, limit=2)
        if len(history) < 2:
            return

        previous_error = history[1]["error_pct"]
        window = self._vol_train_windows.get(pair, 30)
        old_window = window
        streak = self._vol_improvement_streak.get(pair, 0)

        if current_error < previous_error:  # improved
            streak += 1
            if streak >= 3:  # improved 3x in a row -> expand window
                window = min(60, int(window * 1.10))
                streak = 0
        else:  # worsened -> shrink window
            window = max(7, int(window * 0.90))
            streak = 0

        self._vol_improvement_streak[pair] = streak
        self._vol_train_windows[pair] = window

        if window != old_window:
            name = pair.replace("-USD", "")
            direction = "expanded" if window > old_window else "shrunk"
            desc = (
                f"Vol model training window {direction} from {old_window}d to {window}d "
                f"— {'recent data more relevant' if window < old_window else 'model benefits from more history'}"
            )
            self.trade_logger.log_adaptation(pair, "vol_window_tuned", desc, old_window, window)
            self.trade_logger.log_event(
                "adaptation", f"{name}: vol training window → {window}d",
                desc, pair=pair,
            )

    def _check_periodic_tasks(self):
        """Run periodic rescans and retrains."""
        now = datetime.now()

        # Quick check every 6 hours
        if self.pair_selector and self._last_quick_check:
            hours_since_quick = (now - self._last_quick_check).total_seconds() / 3600
            if hours_since_quick >= 6:
                self._run_quick_check()

        # Full rescan every 24 hours
        if self.pair_selector and self._last_full_scan:
            hours_since_full = (now - self._last_full_scan).total_seconds() / 3600
            if hours_since_full >= 24:
                self._run_full_rescan()

        # Evaluate vol prediction accuracy every 12 hours
        if self.vol_predictor and self._last_vol_eval:
            hours_since_eval = (now - self._last_vol_eval).total_seconds() / 3600
            if hours_since_eval >= 12:
                self._evaluate_vol_accuracy()
        elif self.vol_predictor and self._last_vol_train:
            # First eval 12h after initial training
            hours_since_train = (now - self._last_vol_train).total_seconds() / 3600
            if hours_since_train >= 12:
                self._evaluate_vol_accuracy()

        # Retrain volatility models periodically
        if self.vol_predictor and self._last_vol_train:
            vol_cfg = load_ml_config().get("volatility", {})
            retrain_hours = vol_cfg.get("retrain_interval_hours", 24)
            hours_since_vol = (now - self._last_vol_train).total_seconds() / 3600
            if hours_since_vol >= retrain_hours:
                self._train_vol_models()

        # Retrain ML models every 24 hours
        if self.use_ml and self.ml_predictor and self._last_full_scan:
            for engine in self.engines:
                end = datetime.now()
                start = end - timedelta(days=30)
                candles = self.candle_store.get_candles(engine.pair, "ONE_HOUR", start, end)
                if candles and len(candles) >= 100:
                    self.ml_predictor.retrain_in_background(engine.pair, candles)

    def _run_quick_check(self):
        """Quick check active pairs — swap out any in TRENDING_DOWN."""
        if not self.pair_selector:
            return

        print("\n  [SCAN] Running quick check on active pairs...")
        result = self.pair_selector.quick_check(self.total_allocation)
        self._last_quick_check = datetime.now()

        if result.swapped_out:
            for swap in result.swapped_out:
                print(f"  [SCAN] Swapped OUT: {swap['pair']} ({swap['reason']})")
            for swap in result.swapped_in:
                print(f"  [SCAN] Swapped IN: {swap['pair']} ({swap['reason']})")
            self._rebuild_engines(result)
            out_names = ", ".join(s["pair"].replace("-USD", "") for s in result.swapped_out)
            in_names = ", ".join(s["pair"].replace("-USD", "") for s in result.swapped_in)
            self.trade_logger.log_event(
                "scan_complete",
                f"Quick check — swapped {out_names} → {in_names}",
                f"Reason: {result.swapped_out[0].get('reason', '')}",
            )
        else:
            active = ", ".join(e.pair.replace("-USD", "") for e in self.engines)
            self.trade_logger.log_event(
                "scan_complete",
                f"Quick check — {len(self.engines)} pairs confirmed, no swaps",
                f"Active: {active}",
            )

        self.trade_logger.log_pair_scan(self.pair_selector.scan_result_to_dict(result))

    def _run_full_rescan(self):
        """Full rescan of all Coinbase pairs."""
        if not self.pair_selector:
            return

        print("\n  [SCAN] Running full pair rescan...")
        result = self.pair_selector.full_scan(self.total_allocation)
        self._last_full_scan = datetime.now()
        self._last_quick_check = datetime.now()

        new_pairs = {s.pair for s in result.selected}
        old_pairs = {e.pair for e in self.engines}

        if new_pairs != old_pairs:
            print(f"  [SCAN] Pair change: {old_pairs} -> {new_pairs}")
            self._rebuild_engines(result)
            added = new_pairs - old_pairs
            removed = old_pairs - new_pairs
            detail_parts = []
            if removed:
                detail_parts.append(f"Dropped: {', '.join(p.replace('-USD', '') for p in removed)}")
            if added:
                detail_parts.append(f"Added: {', '.join(p.replace('-USD', '') for p in added)}")
            self.trade_logger.log_event(
                "scan_complete",
                f"Full rescan — {len(new_pairs)} pairs selected",
                " | ".join(detail_parts),
            )
        else:
            self.trade_logger.log_event(
                "scan_complete",
                f"Full rescan — {len(new_pairs)} pairs confirmed, no changes",
                f"Active: {', '.join(p.replace('-USD', '') for p in new_pairs)}",
            )

        self.trade_logger.log_pair_scan(self.pair_selector.scan_result_to_dict(result))

        # Feedback loops: learn from past performance before next scan
        try:
            self._learn_spacing_preferences()
            self._learn_pair_performance()
        except Exception as e:
            logger.warning(f"Feedback loop error: {e}")

        # Retrain ML for any new pairs
        if self.use_ml and self.ml_predictor:
            self._train_ml_models()

    def _rebuild_engines(self, scan_result):
        """Rebuild pair engines after a rescan changed the active set."""
        configs = self.pair_selector.get_active_configs()
        selected_pairs = [s.pair for s in scan_result.selected]
        alloc_per_pair = self.total_allocation / max(len(selected_pairs), 1)

        # Keep engines that are still active, remove stale ones
        # BUT: never drop an engine that has open positions
        existing = {e.pair: e for e in self.engines}
        new_engines = []

        with open("config/bot_config.yaml") as f:
            bot_config = yaml.safe_load(f)
        sim = bot_config.get("simulation", {})
        maker_fee = sim.get("maker_fee", 0.004)
        taker_fee = sim.get("taker_fee", 0.006)
        slippage = sim.get("slippage", 0.001)

        for pair in selected_pairs:
            if pair in existing:
                new_engines.append(existing[pair])
            else:
                config = configs.get(pair, self._default_grid_config(pair, alloc_per_pair))
                strategy = GridStrategy()
                strategy.configure(config)
                engine = PairEngine(
                    name=f"{pair.split('-')[0]}-grid",
                    strategy=strategy,
                    pair=pair,
                    granularity="ONE_HOUR",
                    allocation_usd=alloc_per_pair,
                    maker_fee=maker_fee,
                    taker_fee=taker_fee,
                    slippage=slippage,
                )
                new_engines.append(engine)
                print(f"  [SCAN] Added engine for {pair}")

        # Keep engines with open positions even if deselected by scanner
        kept_pairs = {e.pair for e in new_engines}
        for pair, engine in existing.items():
            if pair not in kept_pairs and engine.has_open_positions():
                new_engines.append(engine)
                print(f"  [SCAN] Keeping {pair} — has open positions")

        self.engines = new_engines

    def _default_grid_config(self, pair: str, allocation: float) -> dict:
        """Build a fallback grid config for a pair."""
        end = datetime.now()
        start = end - timedelta(days=3)
        candles = self.candle_store.get_candles(pair, "ONE_HOUR", start, end)

        low = 0.01
        high = 1.0
        if candles:
            low = min(c.low for c in candles) * 0.95
            high = max(c.high for c in candles) * 1.05

        return {
            "pair": pair,
            "granularity": "ONE_HOUR",
            "upper_price": high,
            "lower_price": low,
            "num_grids": 20,
            "total_investment_usd": allocation,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10,
            "adaptive_range": True,
            "range_lookback_days": 3,
            "recalc_interval_hours": 12,
            "min_spacing_pct": 0.01,
            "max_trades_per_day": 20,
            # Improvement 1+4: grid mode
            "grid_mode": "geometric",
            "auto_grid_mode": True,
            # Improvement 2: trailing grid
            "trailing_enabled": True,
            "trailing_buffer_pct": 0.02,
            # Improvement 3: profit filter
            "fee_pct": 0.40,
            "slippage_pct": 0.10,
            "min_profit_multiplier": 1.5,
            # Improvement 5: position limit
            "max_position_pct": 0.60,
            # Improvement 6: compounding
            "compound_enabled": True,
            "compound_floor_pct": 0.50,
            "compound_cap_pct": 2.0,
        }

    def _print_header(self):
        print()
        print("=" * 80)
        print("  CRYPTOBOT MULTI-PAIR SIMULATION")
        if self.use_ml:
            print("  ML PREDICTIONS: ENABLED")
        print("=" * 80)
        for engine in self.engines:
            print(f"  {engine.name:<20} {engine.pair:<12} ${engine.allocation:>10,.2f}")
        print(f"  {'TOTAL':<20} {'':12} ${self.total_allocation:>10,.2f}")
        print(f"  Started: {self.session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

    def _print_trade(self, event: dict):
        trade = event["trade"]
        arrow = ">>BUY " if trade.side == "buy" else "<<SELL"
        print(
            f"  {arrow} [{event['name']}]  {trade.pair}  "
            f"${trade.price:>10,.4f}  amt={trade.amount:.6f}  "
            f"fee=${trade.fee:.4f}  {trade.reason}"
        )

    def _print_dashboard(self, total_equity: float):
        pnl = total_equity - self.total_allocation
        pnl_pct = (pnl / self.total_allocation) * 100
        sign = "+" if pnl >= 0 else ""

        now = datetime.now()
        parts = []
        for engine in self.engines:
            e_equity = engine.get_equity()
            e_pnl = e_equity - engine.allocation
            e_sign = "+" if e_pnl >= 0 else ""
            parts.append(f"{engine.pair}: ${e_equity:,.2f}({e_sign}{e_pnl:.2f})")

        pause_tag = ""
        if self._trading_paused:
            hours_left = 0
            if self._pause_until:
                hours_left = max(0, (self._pause_until - now).total_seconds() / 3600)
            pause_tag = f"  !! PAUSED ({self._pause_reason}, {hours_left:.0f}h left)"

        mom_tag = ""
        if self.momentum_engine:
            m = self.momentum_engine
            m_eq = m.get_equity()
            m_pnl = m.get_pnl()
            m_sign = "+" if m_pnl >= 0 else ""
            held = [h.pair.replace('-USD', '') for h in m.holdings.values()]
            held_str = ','.join(held) if held else 'CASH'
            mom_tag = (f"  || MOM: ${m_eq:,.2f}({m_sign}{m_pnl:.2f}) [{held_str}]")

        print(
            f"  [{now.strftime('%m-%d %H:%M')}]  "
            f"Grid: ${total_equity:>10,.2f}  "
            f"P&L: {sign}${pnl:>8,.2f} ({sign}{pnl_pct:.1f}%)  "
            f"Trades: {sum(e.trade_count for e in self.engines)}  |  "
            + "  ".join(parts)
            + mom_tag
            + pause_tag
        )

    def _print_summary(self):
        duration = datetime.now() - self.session_start
        hours = duration.total_seconds() / 3600

        total_equity = sum(e.get_equity() for e in self.engines)
        pnl = total_equity - self.total_allocation
        pnl_pct = (pnl / self.total_allocation) * 100
        sign = "+" if pnl >= 0 else ""

        print()
        print("=" * 80)
        print("  SIMULATION SESSION COMPLETE")
        print(f"  Duration:     {hours:.1f} hours")
        print(f"  Total Equity: ${total_equity:,.2f}")
        print(f"  P&L:          {sign}${pnl:,.2f} ({sign}{pnl_pct:.1f}%)")
        if self.use_ml:
            print(f"  ML Mode:      ENABLED")
        print()

        for engine in self.engines:
            e_equity = engine.get_equity()
            e_pnl = e_equity - engine.allocation
            e_sign = "+" if e_pnl >= 0 else ""
            print(
                f"  {engine.name:<20} ${e_equity:>10,.2f}  "
                f"P&L: {e_sign}${e_pnl:>8,.2f}  "
                f"Trades: {engine.trade_count}  "
                f"Candles: {engine.candles_fed}"
            )

        # ASCII equity curve
        if len(self.equity_history) > 2:
            print()
            self._print_equity_curve()

        print("=" * 80)
        print()

    def _print_equity_curve(self):
        values = [eq for _, eq in self.equity_history]
        width = min(60, len(values))
        height = 8
        step = max(1, len(values) // width)
        sampled = [values[i] for i in range(0, len(values), step)][:width]

        min_val = min(sampled)
        max_val = max(sampled)
        val_range = max_val - min_val if max_val != min_val else 1.0

        print("  COMBINED EQUITY CURVE:")
        for row in range(height - 1, -1, -1):
            threshold = min_val + (row / (height - 1)) * val_range
            label = f"${threshold:>10,.0f} |"
            chars = ["*" if val >= threshold else " " for val in sampled]
            print(f"  {label}{''.join(chars)}")

        print(f"  {' ' * 12}+{'-' * len(sampled)}")


def build_runner(poll_seconds: int = 60, warmup_days: int = 30, use_ml: bool = False) -> SimRunner:
    """Build the multi-pair runner using PairSelector for dynamic pair discovery."""

    with open("config/bot_config.yaml") as f:
        bot_config = yaml.safe_load(f)

    starting_balance = bot_config.get("starting_balance_usd", 3000)
    sim = bot_config.get("simulation", {})
    maker_fee = sim.get("maker_fee", 0.004)
    taker_fee = sim.get("taker_fee", 0.006)
    slippage = sim.get("slippage", 0.001)

    runner = SimRunner(poll_seconds=poll_seconds, warmup_days=warmup_days, use_ml=use_ml)

    # --- Pair Selection ---
    print("\n  Scanning Coinbase for optimal pairs...")
    ps_config = load_pair_selector_config()
    selector = PairSelector(ps_config, db_path="data/candles.db")
    scan_result = selector.full_scan(starting_balance)

    runner.pair_selector = selector
    runner._last_full_scan = datetime.now()
    runner._last_quick_check = datetime.now()

    if not scan_result.selected:
        print("  ERROR: No pairs selected. Check internet connection.")
        return runner

    selected_pairs = [s.pair for s in scan_result.selected]
    configs = selector.get_active_configs()
    alloc_per_pair = starting_balance / len(selected_pairs)

    print(f"\n  Selected {len(selected_pairs)} pairs: {', '.join(selected_pairs)}")
    print(f"  Allocation per pair: ${alloc_per_pair:,.2f}")

    # Log initial scan
    runner.trade_logger.log_pair_scan(selector.scan_result_to_dict(scan_result))
    pair_names = [s.pair.replace("-USD", "") for s in scan_result.selected]
    runner.trade_logger.log_event(
        "scan_complete",
        f"Initial scan selected {len(scan_result.selected)} pairs: {', '.join(pair_names)}",
        f"Scanned {scan_result.total_scanned} pairs, rejected {scan_result.total_scanned - len(scan_result.selected)}",
    )

    # --- Build engines ---
    for pair in selected_pairs:
        config = configs.get(pair)
        if not config:
            config = runner._default_grid_config(pair, alloc_per_pair)

        strategy = GridStrategy()
        strategy.configure(config)

        name = f"{pair.split('-')[0]}-grid"
        runner.add_pair(name, strategy, pair, "ONE_HOUR", alloc_per_pair, maker_fee, taker_fee, slippage)

    # --- ML Predictor ---
    if use_ml:
        ml_config = load_ml_config()
        runner.ml_predictor = MLPredictor(config=ml_config, models_dir="models")
        print(f"\n  ML predictor initialized (regression, expires every {ml_config.get('expiration_hours', 48)}h)")

    # --- Volatility Predictor (always enabled when prediction_mode=volatility) ---
    ml_config = load_ml_config()
    if ml_config.get("prediction_mode") == "volatility":
        vol_cfg = ml_config.get("volatility", {})
        runner.vol_predictor = VolatilityPredictor(config=vol_cfg)
        print(f"\n  Volatility predictor initialized (GARCH-LightGBM, horizon={vol_cfg.get('forecast_horizon', 12)}h)")

    # --- Load risk limits and ATR config from bot_master.yaml ---
    try:
        with open("config/bot_master.yaml") as f:
            master_config = yaml.safe_load(f) or {}
        runner._max_loss_per_day = float(master_config.get("max_loss_per_day_usd", 30))
        runner._max_loss_per_week = float(master_config.get("max_loss_per_week_usd", 75))
        atr_mult = float(master_config.get("atr_spacing_multiplier", 2.0))
        # Inject ATR multiplier into all active strategies
        for engine in runner.engines:
            if hasattr(engine.strategy, 'atr_spacing_multiplier'):
                engine.strategy.atr_spacing_multiplier = atr_mult
        print(f"\n  Loss limits: ${runner._max_loss_per_day:.0f}/day, ${runner._max_loss_per_week:.0f}/week")
        print(f"  ATR spacing multiplier: {atr_mult}x")
    except Exception:
        pass  # use defaults

    # Print pair selection explanation
    print(f"\n  {selector.generate_explanation(scan_result)}")

    # --- Momentum Rotation Engine (dual engine) ---
    try:
        with open("config/bot_config.yaml") as f:
            bot_cfg_reload = yaml.safe_load(f)
        mom_config = bot_cfg_reload.get("momentum_rotation", {})
        if mom_config.get("enabled", False):
            mom_alloc = float(mom_config.get("allocation_usd", 1500))
            # Create scanner first — it will find the best pairs
            runner.momentum_scanner = MomentumScanner(runner.client, runner.candle_store)
            runner.momentum_engine = MomentumEngine(
                allocation_usd=mom_alloc,
                fee_rate=taker_fee,
                # pairs will be set by scanner during warmup
            )
            print(f"\n  Momentum Rotation Engine: ENABLED (${mom_alloc:,.0f} allocation)")
            print(f"  Scanner: top ~30 by volume, excluding grid pairs")
            print(f"  Config: weekly rebalance, BTC 500MA regime, 7% re-entry")
    except Exception as e:
        logger.warning(f"Momentum engine init error: {e}")

    return runner


def main():
    parser = argparse.ArgumentParser(description="Multi-pair simulation runner")
    parser.add_argument("--poll", type=int, default=60, help="Poll interval in seconds")
    parser.add_argument("--warmup", type=int, default=30, help="Warmup days of historical data")
    parser.add_argument("--ml", action="store_true", help="Enable ML predictions for position sizing")
    args = parser.parse_args()

    os.makedirs("data", exist_ok=True)
    os.makedirs("models", exist_ok=True)

    runner = build_runner(poll_seconds=args.poll, warmup_days=args.warmup, use_ml=args.ml)
    runner.run()


if __name__ == "__main__":
    main()
