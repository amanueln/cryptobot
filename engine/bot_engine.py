from __future__ import annotations

"""Bot engine for simulation mode — polls live Coinbase candles, runs strategy, executes against virtual balance."""

import os
import time
from datetime import datetime, timedelta

import yaml

from exchange.coinbase_client import CoinbaseClient, GRANULARITY_MAP
from exchange.models import Candle
from engine.simulator import Simulator
from data.candle_store import CandleStore
from data.trade_logger import TradeLogger
from strategies.base_strategy import BaseStrategy
from strategies.grid_strategy import GridStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.dca_safety import DCASafetyStrategy
from intelligence.strategy_orchestrator import StrategyOrchestrator

STRATEGY_MAP = {
    "grid": GridStrategy,
    "mean_reversion": MeanReversionStrategy,
    "dca_safety": DCASafetyStrategy,
    "intelligent": StrategyOrchestrator,
}


class BotEngine:
    def __init__(
        self,
        strategy_name: str,
        strategy_config: dict,
        starting_balance: float,
        maker_fee: float = 0.004,
        taker_fee: float = 0.006,
        slippage: float = 0.001,
        db_path: str = "data/candles.db",
        poll_seconds: int = 60,
        warmup_days: int = 30,
    ):
        self.strategy_name = strategy_name
        self.strategy_config = strategy_config
        self.pair = strategy_config["pair"]
        self.granularity = strategy_config.get("granularity", "ONE_HOUR")
        self.starting_balance = starting_balance
        self.poll_seconds = poll_seconds
        self.warmup_days = warmup_days

        # Strategy
        strategy_cls = STRATEGY_MAP.get(strategy_name)
        if strategy_cls is None:
            # Check for pair-specific grid configs (doge, pepe, etc.)
            strategy_cls = GridStrategy
        self.strategy: BaseStrategy = strategy_cls()
        self.strategy.configure(strategy_config)

        # Simulator (virtual balance)
        self.simulator = Simulator(
            starting_balance_usd=starting_balance,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            slippage=slippage,
        )

        # Data
        self.client = CoinbaseClient()
        self.candle_store = CandleStore(db_path)
        self.trade_logger = TradeLogger(db_path)

        # Inject trade_logger into strategy for event logging (e.g. ATR adjustments)
        if hasattr(self.strategy, '_trade_logger'):
            self.strategy._trade_logger = self.trade_logger

        # State
        self._last_candle_ts: datetime | None = None
        self._candles_fed: int = 0
        self._session_start: datetime = datetime.now()
        self.running = False

    def warmup(self) -> int:
        """Feed historical candles to the strategy so indicators are primed."""
        end = datetime.now()
        start = end - timedelta(days=self.warmup_days)

        # Try cache first
        candles = self.candle_store.get_candles(self.pair, self.granularity, start, end)
        interval = GRANULARITY_MAP.get(self.granularity, timedelta(hours=1))
        expected = int(self.warmup_days * 24 * 3600 / interval.total_seconds() * 0.8)

        if not candles or len(candles) < expected:
            print(f"  Fetching {self.warmup_days}d warmup candles for {self.pair}...")
            fetched = self.client.get_candles(self.pair, self.granularity, start, end)
            if fetched:
                self.candle_store.save_candles(self.pair, self.granularity, fetched)
            candles = self.candle_store.get_candles(self.pair, self.granularity, start, end) or fetched

        if not candles:
            print("  WARNING: No warmup candles available.")
            return 0

        for candle in candles:
            self.strategy.on_candle(candle)
            self._candles_fed += 1

        self._last_candle_ts = candles[-1].timestamp
        print(f"  Warmed up with {len(candles)} candles (last: {self._last_candle_ts})")
        return len(candles)

    def run(self) -> None:
        """Main polling loop. Ctrl+C to stop."""
        self.running = True
        self._print_header()
        self.warmup()

        print(f"\n  Live polling every {self.poll_seconds}s for {self.pair} ({self.granularity})")
        print(f"  Press Ctrl+C to stop.\n")

        try:
            while self.running:
                self._poll_and_process()
                time.sleep(self.poll_seconds)
        except KeyboardInterrupt:
            pass

        self._print_summary()

    def _poll_and_process(self) -> None:
        """Fetch latest candles and process any new ones."""
        candles = self.client.get_latest_candles(self.pair, self.granularity, count=5)
        if not candles:
            return

        # Cache fetched candles
        self.candle_store.save_candles(self.pair, self.granularity, candles)

        for candle in candles:
            if self._last_candle_ts is not None and candle.timestamp <= self._last_candle_ts:
                continue

            self._last_candle_ts = candle.timestamp
            self._candles_fed += 1

            signals = self.strategy.on_candle(candle)

            for signal in signals:
                price = signal.limit_price if signal.order_type == "limit" and signal.limit_price else candle.close
                trade = self.simulator.execute(signal, price, candle.timestamp)
                if trade:
                    self.trade_logger.log_trade(trade)
                    self._print_trade(trade)
                    event_type = "trade_buy" if trade.side == "buy" else "trade_sell"
                    title = f"{'Bought' if trade.side == 'buy' else 'Sold'} {trade.amount:,.0f} {trade.pair.replace('-USD', '')} at ${trade.price}"
                    detail = trade.reason
                    self.trade_logger.log_event(event_type, title, detail, pair=trade.pair)

            # Equity snapshot
            equity = self.simulator.get_equity({self.pair: candle.close})
            positions_value = equity - self.simulator.balance_usd
            self.trade_logger.log_equity(candle.timestamp, equity, self.simulator.balance_usd, positions_value)
            self.simulator.snapshot_equity({self.pair: candle.close})

            self._print_status(candle, equity)

    def stop(self) -> None:
        self.running = False

    def _print_header(self) -> None:
        print()
        print("=" * 70)
        print(f"  CRYPTOBOT SIMULATION MODE")
        print(f"  Strategy:  {self.strategy_name}")
        print(f"  Pair:      {self.pair}")
        print(f"  Balance:   ${self.starting_balance:,.2f}")
        print(f"  Started:   {self._session_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

    def _print_trade(self, trade) -> None:
        pnl_info = ""
        if trade.side == "sell":
            pnl_info = f"  (equity: ${self.simulator.get_equity({self.pair: trade.price}):,.2f})"
        arrow = ">>BUY " if trade.side == "buy" else "<<SELL"
        print(
            f"  {arrow}  {trade.pair}  "
            f"${trade.price:>10,.2f}  "
            f"amt={trade.amount:.6f}  "
            f"fee=${trade.fee:.2f}  "
            f"{trade.reason}{pnl_info}"
        )

    def _print_status(self, candle: Candle, equity: float) -> None:
        pnl = equity - self.starting_balance
        pnl_pct = (pnl / self.starting_balance) * 100
        sign = "+" if pnl >= 0 else ""
        state = self.strategy.get_state()
        trades = len(self.simulator.trades)

        # Strategy-specific status
        extra = ""
        if self.strategy_name in ("grid",) or isinstance(self.strategy, GridStrategy):
            filled_buys = state.get("filled_buy_count", 0)
            filled_sells = state.get("filled_sell_count", 0)
            extra = f"  buys={filled_buys} sells={filled_sells}"
            if state.get("grid_paused_divergence"):
                extra += " [PAUSED:divergence]"
            if state.get("trade_cap_paused"):
                extra += " [PAUSED:cap]"
        elif isinstance(self.strategy, MeanReversionStrategy):
            rsi = state.get("rsi")
            pos = state.get("position")
            extra = f"  RSI={rsi:.1f}" if rsi else ""
            if pos:
                extra += f"  IN_POSITION@${pos['entry_price']:,.2f}"

        print(
            f"  [{candle.timestamp.strftime('%m-%d %H:%M')}]  "
            f"${candle.close:>10,.2f}  "
            f"equity=${equity:>10,.2f}  "
            f"P&L={sign}${pnl:>8,.2f} ({sign}{pnl_pct:.1f}%)  "
            f"trades={trades}{extra}"
        )

    def _print_summary(self) -> None:
        duration = datetime.now() - self._session_start
        hours = duration.total_seconds() / 3600

        # Get latest price for final equity
        candles = self.client.get_latest_candles(self.pair, self.granularity, count=1)
        last_price = candles[-1].close if candles else 0
        equity = self.simulator.get_equity({self.pair: last_price})
        pnl = equity - self.starting_balance
        pnl_pct = (pnl / self.starting_balance) * 100
        sign = "+" if pnl >= 0 else ""

        print()
        print("=" * 70)
        print(f"  SIMULATION SESSION COMPLETE")
        print(f"  Duration:    {hours:.1f} hours")
        print(f"  Candles:     {self._candles_fed}")
        print(f"  Trades:      {len(self.simulator.trades)}")
        print(f"  Final Equity: ${equity:,.2f}")
        print(f"  P&L:         {sign}${pnl:,.2f} ({sign}{pnl_pct:.1f}%)")
        print("=" * 70)
        print()
