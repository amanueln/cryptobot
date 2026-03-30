"""Multi-pair simultaneous simulation runner.

Runs multiple pairs with their optimal strategies in parallel,
tracks combined equity, and displays a unified dashboard.

Usage:
    py sim_runner.py [--poll 60] [--warmup 30]
"""

import argparse
import os
import time
import sqlite3
from datetime import datetime, timedelta

import yaml

from exchange.coinbase_client import CoinbaseClient, GRANULARITY_MAP
from exchange.models import Candle
from engine.simulator import Simulator
from data.candle_store import CandleStore
from data.trade_logger import TradeLogger
from strategies.grid_strategy import GridStrategy
from intelligence.strategy_orchestrator import StrategyOrchestrator
from strategies.base_strategy import BaseStrategy


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

    def process_candles(self, candles: list[Candle]) -> list[dict]:
        """Feed new candles to strategy, execute signals. Returns trade events."""
        events = []
        for candle in candles:
            if self.last_candle_ts is not None and candle.timestamp <= self.last_candle_ts:
                continue

            self.last_candle_ts = candle.timestamp
            self.last_price = candle.close
            self.candles_fed += 1

            signals = self.strategy.on_candle(candle)
            for signal in signals:
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
    def __init__(self, poll_seconds: int = 60, warmup_days: int = 30):
        self.poll_seconds = poll_seconds
        self.warmup_days = warmup_days
        self.client = CoinbaseClient()
        self.candle_store = CandleStore("data/candles.db")
        self.trade_logger = TradeLogger("data/candles.db")
        self.engines: list[PairEngine] = []
        self.total_allocation: float = 0.0
        self.session_start = datetime.now()
        self.equity_history: list[tuple[datetime, float]] = []
        self.running = False

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
        """Warmup all pair engines with historical data."""
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
                engine.process_candles(candles)
                engine.trade_count = 0  # Reset — warmup trades don't count
                print(f"  {engine.name:<20} warmed up with {len(candles)} candles (last: {engine.last_candle_ts})")
            else:
                print(f"  {engine.name:<20} WARNING: no warmup data")

    def run(self):
        """Main polling loop — polls all pairs, prints combined dashboard."""
        self.running = True
        self._print_header()
        self.warmup_all()

        print(f"\n  Live polling every {self.poll_seconds}s")
        print(f"  Press Ctrl+C to stop.\n")

        try:
            while self.running:
                self._poll_all()
                time.sleep(self.poll_seconds)
        except KeyboardInterrupt:
            pass

        self._print_summary()

    def _poll_all(self):
        """Poll all pairs and process new candles."""
        now = datetime.now()
        total_equity = 0.0
        any_trade = False

        for engine in self.engines:
            candles = self.client.get_latest_candles(engine.pair, engine.granularity, count=5)
            if candles:
                self.candle_store.save_candles(engine.pair, engine.granularity, candles)
                events = engine.process_candles(candles)
                for event in events:
                    self._print_trade(event)
                    self.trade_logger.log_trade(event["trade"])
                    any_trade = True

            equity = engine.get_equity()
            total_equity += equity

        # Snapshot combined equity
        self.equity_history.append((now, total_equity))
        self.trade_logger.log_equity(now, total_equity, total_equity, 0)

        self._print_dashboard(total_equity)

    def _print_header(self):
        print()
        print("=" * 80)
        print("  CRYPTOBOT MULTI-PAIR SIMULATION")
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

        print(
            f"  [{now.strftime('%m-%d %H:%M')}]  "
            f"Combined: ${total_equity:>10,.2f}  "
            f"P&L: {sign}${pnl:>8,.2f} ({sign}{pnl_pct:.1f}%)  "
            f"Trades: {sum(e.trade_count for e in self.engines)}  |  "
            + "  ".join(parts)
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


def auto_fit_grid(candles: list[Candle], base_config: dict) -> dict:
    lows = [c.low for c in candles]
    highs = [c.high for c in candles]
    config = dict(base_config)
    config["lower_price"] = min(lows) * 0.95
    config["upper_price"] = max(highs) * 1.05
    return config


def build_runner(poll_seconds: int = 60, warmup_days: int = 30) -> SimRunner:
    """Build the multi-pair runner with optimal strategies per pair."""

    with open("config/bot_config.yaml") as f:
        bot_config = yaml.safe_load(f)

    starting_balance = bot_config.get("starting_balance_usd", 3000)
    sim = bot_config.get("simulation", {})
    maker_fee = sim.get("maker_fee", 0.004)
    taker_fee = sim.get("taker_fee", 0.006)
    slippage = sim.get("slippage", 0.001)

    # Allocate capital: DOGE 40%, ETH 35%, PEPE 25%
    doge_alloc = starting_balance * 0.40
    eth_alloc = starting_balance * 0.35
    pepe_alloc = starting_balance * 0.25

    runner = SimRunner(poll_seconds=poll_seconds, warmup_days=warmup_days)
    client = CoinbaseClient()
    store = CandleStore("data/candles.db")

    # Helper to get recent candles for auto-fitting grid ranges
    def get_recent(pair, gran, days):
        end = datetime.now()
        start = end - timedelta(days=days)
        candles = store.get_candles(pair, gran, start, end)
        if not candles or len(candles) < days * 20:
            fetched = client.get_candles(pair, gran, start, end)
            if fetched:
                store.save_candles(pair, gran, fetched)
            candles = store.get_candles(pair, gran, start, end) or fetched
        return candles or []

    # --- DOGE: Adaptive grid + death cross filter ---
    with open("config/strategies/doge.yaml") as f:
        doge_config = yaml.safe_load(f)
    doge_config["pair"] = "DOGE-USD"
    doge_candles = get_recent("DOGE-USD", "ONE_HOUR", 30)
    if doge_candles:
        doge_config = auto_fit_grid(doge_candles, doge_config)

    doge_strategy = GridStrategy()
    doge_strategy.configure(doge_config)
    runner.add_pair("DOGE-grid", doge_strategy, "DOGE-USD", "ONE_HOUR", doge_alloc, maker_fee, taker_fee, slippage)

    # --- ETH: Intelligent regime-aware orchestrator ---
    with open("config/strategies/eth.yaml") as f:
        eth_grid_config = yaml.safe_load(f)
    eth_grid_config["pair"] = "ETH-USD"
    eth_candles = get_recent("ETH-USD", "ONE_HOUR", 30)
    if eth_candles:
        eth_grid_config = auto_fit_grid(eth_candles, eth_grid_config)

    with open("config/intelligence.yaml") as f:
        intel_config = yaml.safe_load(f)

    eth_dca_config = {
        "pair": "ETH-USD",
        "granularity": "ONE_HOUR",
        "risk_per_deal_pct": 0.35,
        "volume_scale": 1.5,
        "step_scale": 1.5,
        "max_safety_orders": 5,
        "atr_period": 14,
        "bounce_lookback_days": 30,
        "min_take_profit_pct": 0.8,
        "max_take_profit_pct": 3.0,
        "max_portfolio_drawdown_pct": 0.10,
        "cooldown_candles": 5,
        "starting_balance": eth_alloc,
    }

    eth_orchestrator = StrategyOrchestrator()
    eth_orchestrator.configure({
        "pair": "ETH-USD",
        "detector": intel_config,
        "grid": eth_grid_config,
        "dca": eth_dca_config,
        "starting_balance": eth_alloc,
    })
    runner.add_pair("ETH-intelligent", eth_orchestrator, "ETH-USD", "ONE_HOUR", eth_alloc, maker_fee, taker_fee, slippage)

    # --- PEPE: Adaptive grid ---
    with open("config/strategies/pepe.yaml") as f:
        pepe_config = yaml.safe_load(f)
    pepe_config["pair"] = "PEPE-USD"
    pepe_candles = get_recent("PEPE-USD", "ONE_HOUR", 30)
    if pepe_candles:
        pepe_config = auto_fit_grid(pepe_candles, pepe_config)

    pepe_strategy = GridStrategy()
    pepe_strategy.configure(pepe_config)
    runner.add_pair("PEPE-grid", pepe_strategy, "PEPE-USD", "ONE_HOUR", pepe_alloc, maker_fee, taker_fee, slippage)

    return runner


def main():
    parser = argparse.ArgumentParser(description="Multi-pair simulation runner")
    parser.add_argument("--poll", type=int, default=60, help="Poll interval in seconds")
    parser.add_argument("--warmup", type=int, default=30, help="Warmup days of historical data")
    args = parser.parse_args()

    os.makedirs("data", exist_ok=True)
    runner = build_runner(poll_seconds=args.poll, warmup_days=args.warmup)
    runner.run()


if __name__ == "__main__":
    main()
