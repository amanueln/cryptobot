"""
Compare grid strategy improvements incrementally using real 7-day candle data.

Scenarios:
  0. Baseline       — old config (10 grids, arithmetic, no improvements)
  1. Geometric       — geometric spacing only
  2. + Profit filter — geometric + min-profit-per-grid filter
  3. + Position limit— above + 60% position cap
  4. + Trailing      — above + trailing grid
  5. Full stack      — all 6 (geometric, filter, limit, trailing, compounding, auto-mode)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from data.candle_store import CandleStore
from strategies.grid_strategy import GridStrategy
from engine.backtester import Backtester

ALLOCATION = 100.0  # USD per pair
MAKER_FEE = 0.004
TAKER_FEE = 0.006
SLIPPAGE = 0.001

# Use the pairs with the most candle data — the ones the bot actually watches
TEST_PAIRS = ["NKN-USD", "ABT-USD", "GHST-USD", "2Z-USD", "GWEI-USD"]


def get_candles(store, pair):
    end = datetime.now()
    start = end - timedelta(days=7)
    candles = store.get_candles(pair, "ONE_HOUR", start, end)
    return candles


def make_config(pair, candles, scenario):
    """Build grid config for a given scenario."""
    low = min(c.low for c in candles) * 0.95
    high = max(c.high for c in candles) * 1.05

    if scenario == 0:
        # Baseline: old config — 10 grids, arithmetic, no improvements
        return {
            "pair": pair,
            "granularity": "ONE_HOUR",
            "upper_price": high,
            "lower_price": low,
            "num_grids": 10,
            "total_investment_usd": ALLOCATION,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10,
            "adaptive_range": False,
            "max_trades_per_day": 20,
            "grid_mode": "arithmetic",
            "auto_grid_mode": False,
            "trailing_enabled": False,
            "fee_pct": 0.40,
            "slippage_pct": 0.10,
            "min_profit_multiplier": 0,  # disabled
            "max_position_pct": 1.0,     # no limit
            "compound_enabled": False,
        }

    elif scenario == 1:
        # Geometric spacing only
        return {
            "pair": pair,
            "granularity": "ONE_HOUR",
            "upper_price": high,
            "lower_price": low,
            "num_grids": 20,
            "total_investment_usd": ALLOCATION,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10,
            "adaptive_range": False,
            "max_trades_per_day": 20,
            "grid_mode": "geometric",
            "auto_grid_mode": False,
            "trailing_enabled": False,
            "fee_pct": 0.40,
            "slippage_pct": 0.10,
            "min_profit_multiplier": 0,
            "max_position_pct": 1.0,
            "compound_enabled": False,
        }

    elif scenario == 2:
        # + Profit filter
        return {
            "pair": pair,
            "granularity": "ONE_HOUR",
            "upper_price": high,
            "lower_price": low,
            "num_grids": 20,
            "total_investment_usd": ALLOCATION,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10,
            "adaptive_range": False,
            "max_trades_per_day": 20,
            "grid_mode": "geometric",
            "auto_grid_mode": False,
            "trailing_enabled": False,
            "fee_pct": 0.40,
            "slippage_pct": 0.10,
            "min_profit_multiplier": 1.5,
            "max_position_pct": 1.0,
            "compound_enabled": False,
        }

    elif scenario == 3:
        # + Position limit
        return {
            "pair": pair,
            "granularity": "ONE_HOUR",
            "upper_price": high,
            "lower_price": low,
            "num_grids": 20,
            "total_investment_usd": ALLOCATION,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10,
            "adaptive_range": False,
            "max_trades_per_day": 20,
            "grid_mode": "geometric",
            "auto_grid_mode": False,
            "trailing_enabled": False,
            "fee_pct": 0.40,
            "slippage_pct": 0.10,
            "min_profit_multiplier": 1.5,
            "max_position_pct": 0.60,
            "compound_enabled": False,
        }

    elif scenario == 4:
        # + Trailing grid
        return {
            "pair": pair,
            "granularity": "ONE_HOUR",
            "upper_price": high,
            "lower_price": low,
            "num_grids": 20,
            "total_investment_usd": ALLOCATION,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10,
            "adaptive_range": False,
            "max_trades_per_day": 20,
            "grid_mode": "geometric",
            "auto_grid_mode": False,
            "trailing_enabled": True,
            "trailing_buffer_pct": 0.02,
            "fee_pct": 0.40,
            "slippage_pct": 0.10,
            "min_profit_multiplier": 1.5,
            "max_position_pct": 0.60,
            "compound_enabled": False,
        }

    elif scenario == 5:
        # Full stack (all 6)
        return {
            "pair": pair,
            "granularity": "ONE_HOUR",
            "upper_price": high,
            "lower_price": low,
            "num_grids": 20,
            "total_investment_usd": ALLOCATION,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10,
            "adaptive_range": False,
            "max_trades_per_day": 20,
            "grid_mode": "geometric",
            "auto_grid_mode": True,
            "trailing_enabled": True,
            "trailing_buffer_pct": 0.02,
            "fee_pct": 0.40,
            "slippage_pct": 0.10,
            "min_profit_multiplier": 1.5,
            "max_position_pct": 0.60,
            "compound_enabled": True,
            "compound_floor_pct": 0.50,
            "compound_cap_pct": 2.0,
        }


SCENARIO_NAMES = [
    "Baseline (old)",
    "Geometric",
    "+ Profit filter",
    "+ Position limit",
    "+ Trailing",
    "Full stack",
]


def count_completed_cycles(trades):
    """Count completed buy->sell grid cycles."""
    cycles = 0
    for t in trades:
        if t.side == "sell" and "grid sell" in t.reason:
            cycles += 1
    return cycles


def run_comparison():
    store = CandleStore("data/candles.db")
    backtester = Backtester()

    # Load candle data per pair
    pair_candles = {}
    for pair in TEST_PAIRS:
        candles = get_candles(store, pair)
        if candles and len(candles) >= 50:
            pair_candles[pair] = candles
            print(f"  {pair:<16} {len(candles)} candles")
        else:
            print(f"  {pair:<16} SKIPPED (only {len(candles) if candles else 0} candles)")

    if not pair_candles:
        print("No usable candle data found.")
        return

    # Run each scenario
    results = []  # list of dicts per scenario

    for scenario in range(6):
        total_trades = 0
        total_cycles = 0
        total_pnl = 0.0
        max_dd = 0.0
        errors = []

        for pair, candles in pair_candles.items():
            config = make_config(pair, candles, scenario)
            strategy = GridStrategy()
            try:
                strategy.configure(config)
            except Exception as e:
                errors.append(f"{pair}: configure failed: {e}")
                continue

            try:
                result = backtester.run(
                    strategy, candles, ALLOCATION,
                    maker_fee=MAKER_FEE, taker_fee=TAKER_FEE, slippage=SLIPPAGE,
                )
            except Exception as e:
                errors.append(f"{pair}: backtest failed: {e}")
                continue

            total_trades += result.total_trades
            total_cycles += count_completed_cycles(result.trades)
            total_pnl += result.total_pnl
            if result.max_drawdown > max_dd:
                max_dd = result.max_drawdown

        results.append({
            "name": SCENARIO_NAMES[scenario],
            "trades": total_trades,
            "cycles": total_cycles,
            "pnl": total_pnl,
            "max_dd": max_dd,
            "errors": errors,
        })

    # Print summary table
    print()
    print("=" * 80)
    print("  GRID IMPROVEMENT COMPARISON — 7-day backtest across", len(pair_candles), "pairs")
    print("  Pairs:", ", ".join(pair_candles.keys()))
    print(f"  Allocation: ${ALLOCATION:.0f}/pair, ${ALLOCATION * len(pair_candles):.0f} total")
    print("=" * 80)
    print()
    print(f"  {'Scenario':<22} {'Trades':>8} {'Cycles':>8} {'Net P&L':>12} {'Max DD':>10}")
    print(f"  {'-' * 22} {'-' * 8} {'-' * 8} {'-' * 12} {'-' * 10}")

    baseline_pnl = results[0]["pnl"] if results else 0

    for r in results:
        pnl_str = f"${r['pnl']:+.2f}"
        dd_str = f"{r['max_dd']:.1%}"
        delta = ""
        if r["name"] != SCENARIO_NAMES[0] and baseline_pnl != 0:
            improvement = r["pnl"] - baseline_pnl
            delta = f"  ({'+' if improvement >= 0 else ''}{improvement:.2f})"
        print(f"  {r['name']:<22} {r['trades']:>8} {r['cycles']:>8} {pnl_str:>12}{delta:<12} {dd_str:>10}")
        if r["errors"]:
            for err in r["errors"]:
                print(f"    ERROR: {err}")

    print()
    print("=" * 80)

    # Per-pair breakdown for full stack
    print()
    print("  PER-PAIR BREAKDOWN (Full stack):")
    print(f"  {'Pair':<16} {'Trades':>8} {'Cycles':>8} {'P&L':>10} {'Max DD':>10}")
    print(f"  {'-' * 16} {'-' * 8} {'-' * 8} {'-' * 10} {'-' * 10}")

    for pair, candles in pair_candles.items():
        config = make_config(pair, candles, 5)
        strategy = GridStrategy()
        strategy.configure(config)
        result = backtester.run(
            strategy, candles, ALLOCATION,
            maker_fee=MAKER_FEE, taker_fee=TAKER_FEE, slippage=SLIPPAGE,
        )
        cycles = count_completed_cycles(result.trades)
        name = pair.replace("-USD", "")
        print(f"  {name:<16} {result.total_trades:>8} {cycles:>8} ${result.total_pnl:>+9.2f} {result.max_drawdown:>9.1%}")

    print()


if __name__ == "__main__":
    run_comparison()
