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

logger = logging.getLogger(__name__)


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
                print(f"  {engine.name:<20} warmed up with {len(candles)} candles (last: {engine.last_candle_ts})")
            else:
                print(f"  {engine.name:<20} WARNING: no warmup data")

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

        # Fetch BTC candles for cross-market features
        btc_candles = None
        end = datetime.now()
        start = end - timedelta(days=30)
        btc_candles_raw = self.candle_store.get_candles("BTC-USD", "ONE_HOUR", start, end)
        if btc_candles_raw and len(btc_candles_raw) >= 100:
            btc_candles = btc_candles_raw

        for engine in self.engines:
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

        # Retrain ML for any new pairs
        if self.use_ml and self.ml_predictor:
            self._train_ml_models()

    def _rebuild_engines(self, scan_result):
        """Rebuild pair engines after a rescan changed the active set."""
        configs = self.pair_selector.get_active_configs()
        selected_pairs = [s.pair for s in scan_result.selected]
        alloc_per_pair = self.total_allocation / max(len(selected_pairs), 1)

        # Keep engines that are still active, remove stale ones
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

        self.engines = new_engines

    def _default_grid_config(self, pair: str, allocation: float) -> dict:
        """Build a fallback grid config for a pair."""
        end = datetime.now()
        start = end - timedelta(days=14)
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
            "num_grids": 10,
            "total_investment_usd": allocation,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10,
            "adaptive_range": True,
            "range_lookback_days": 14,
            "recalc_interval_hours": 12,
            "min_spacing_pct": 0.01,
            "max_trades_per_day": 20,
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

        print(
            f"  [{now.strftime('%m-%d %H:%M')}]  "
            f"Combined: ${total_equity:>10,.2f}  "
            f"P&L: {sign}${pnl:>8,.2f} ({sign}{pnl_pct:.1f}%)  "
            f"Trades: {sum(e.trade_count for e in self.engines)}  |  "
            + "  ".join(parts)
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
