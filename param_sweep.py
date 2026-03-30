"""Parameter optimization sweep for grid strategy.

Tests all combinations of grid parameters across DOGE, PEPE, ETH at 365 days.
Uses multiprocessing to parallelize across CPU cores.
"""

import csv
import itertools
import os
import time
from datetime import datetime, timedelta
from multiprocessing import Pool, cpu_count

from exchange.coinbase_client import CoinbaseClient
from exchange.models import Candle
from data.candle_store import CandleStore
from strategies.grid_strategy import GridStrategy
from engine.simulator import Simulator
from data.performance import (
    calculate_win_rate,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_total_pnl,
)

DB_PATH = "data/candles.db"
STARTING_BALANCE = 3000.0
MAKER_FEE = 0.004
TAKER_FEE = 0.006
SLIPPAGE = 0.001
DAYS = 365

PAIRS = {
    "doge": "DOGE-USD",
    "pepe": "PEPE-USD",
    "eth": "ETH-USD",
}

# Parameter grid
GRID_COUNTS = [5, 8, 10, 15, 20]
LOOKBACK_DAYS = [7, 14, 21, 30]
RECALC_HOURS = [6, 12, 24, 48]
MIN_SPACING = [0.01, 0.015, 0.02, 0.03, 0.05]
MAX_TRADES = [10, 20, 50, 0]  # 0 = unlimited

ALL_COMBOS = list(itertools.product(
    GRID_COUNTS, LOOKBACK_DAYS, RECALC_HOURS, MIN_SPACING, MAX_TRADES
))


def load_candles(pair: str, days: int) -> list[Candle]:
    end = datetime.now()
    start = end - timedelta(days=days)
    store = CandleStore(DB_PATH)
    cached = store.get_candles(pair, "ONE_HOUR", start, end)
    expected = int(days * 24 * 0.9)
    if cached and len(cached) >= expected:
        return cached
    print(f"  Fetching {days}d of {pair}...")
    client = CoinbaseClient()
    candles = client.get_candles(pair, "ONE_HOUR", start, end)
    if candles:
        store.save_candles(pair, "ONE_HOUR", candles)
    return store.get_candles(pair, "ONE_HOUR", start, end) or candles


def auto_fit_grid(candles: list[Candle]) -> tuple[float, float]:
    lows = [c.low for c in candles]
    highs = [c.high for c in candles]
    return min(lows) * 0.95, max(highs) * 1.05


def run_single_backtest(args: tuple) -> dict:
    """Run one backtest. Designed to be called via multiprocessing."""
    pair_key, pair, candle_data, combo = args
    num_grids, lookback, recalc_hrs, min_space, max_trades = combo

    # Deserialize candle data (tuples -> Candle objects)
    candles = [
        Candle(
            pair=c[0], granularity=c[1],
            timestamp=datetime.fromisoformat(c[2]),
            open=c[3], high=c[4], low=c[5], close=c[6], volume=c[7],
        )
        for c in candle_data
    ]

    lower, upper = auto_fit_grid(candles)

    config = {
        "pair": pair,
        "granularity": "ONE_HOUR",
        "lower_price": lower,
        "upper_price": upper,
        "num_grids": num_grids,
        "total_investment_usd": 1000,
        "stop_loss_pct": 0.15,
        "take_profit_pct": 0.10,
        "adaptive_range": True,
        "range_lookback_days": lookback,
        "recalc_interval_hours": recalc_hrs,
        "min_spacing_pct": min_space,
        "max_trades_per_day": max_trades,
        "range_only_filter": True,
        "ema_convergence_pct": 3.0,
        "ema_fast_period": 50,
        "ema_slow_period": 200,
    }

    strategy = GridStrategy()
    strategy.configure(config)

    simulator = Simulator(
        starting_balance_usd=STARTING_BALANCE,
        maker_fee=MAKER_FEE,
        taker_fee=TAKER_FEE,
        slippage=SLIPPAGE,
    )

    for candle in candles:
        signals = strategy.on_candle(candle)
        for signal in signals:
            price = signal.limit_price if signal.order_type == "limit" and signal.limit_price else candle.close
            simulator.execute(signal, price, candle.timestamp)
        simulator.snapshot_equity({pair: candle.close})

    final_equity = simulator.get_equity({pair: candles[-1].close}) if candles else STARTING_BALANCE

    return {
        "pair": pair,
        "num_grids": num_grids,
        "lookback_days": lookback,
        "recalc_hours": recalc_hrs,
        "min_spacing_pct": min_space,
        "max_trades_per_day": max_trades,
        "pnl": calculate_total_pnl(STARTING_BALANCE, final_equity),
        "pnl_pct": ((final_equity - STARTING_BALANCE) / STARTING_BALANCE) * 100,
        "max_drawdown": calculate_max_drawdown(simulator.equity_curve) * 100,
        "trades": len(simulator.trades),
        "win_rate": calculate_win_rate(simulator.trades) * 100,
        "sharpe": calculate_sharpe_ratio(simulator.equity_curve),
    }


def run_sweep_for_pair(pair_key: str, pair: str) -> list[dict]:
    """Run all parameter combinations for one pair using multiprocessing."""
    print(f"\n  Loading candles for {pair}...")
    candles = load_candles(pair, DAYS)
    if not candles or len(candles) < 500:
        print(f"  ERROR: Not enough candles for {pair}")
        return []

    print(f"  Loaded {len(candles)} candles. Running {len(ALL_COMBOS)} combinations...")

    # Serialize candles to tuples for multiprocessing (Candle objects aren't picklable by default)
    candle_data = [
        (c.pair, c.granularity, c.timestamp.isoformat(), c.open, c.high, c.low, c.close, c.volume)
        for c in candles
    ]

    # Build args for each combo
    args_list = [(pair_key, pair, candle_data, combo) for combo in ALL_COMBOS]

    cores = max(1, cpu_count() - 2)  # Leave 2 cores for system
    print(f"  Using {cores} cores...")

    t0 = time.time()
    with Pool(processes=cores) as pool:
        results = pool.map(run_single_backtest, args_list, chunksize=20)
    elapsed = time.time() - t0

    print(f"  Done in {elapsed:.1f}s ({len(results)} backtests, {elapsed/len(results)*1000:.1f}ms each)")
    return results


def print_top_bottom(results: list[dict], pair: str, n: int = 10):
    """Print top N and bottom N results ranked by P&L."""
    sorted_results = sorted(results, key=lambda r: r["pnl"], reverse=True)

    print(f"\n  {'='*110}")
    print(f"  TOP {n} configs for {pair} (365-day, ${STARTING_BALANCE:,.0f} starting balance)")
    print(f"  {'='*110}")
    print(f"  {'#':<4} {'Grids':<6} {'Look':<6} {'Recalc':<7} {'Spc%':<6} {'MaxTr':<6} {'P&L':>10} {'P&L%':>7} {'DD%':>7} {'Trades':>7} {'WR%':>6} {'Sharpe':>7}")
    print(f"  {'-'*4} {'-'*6} {'-'*6} {'-'*7} {'-'*6} {'-'*6} {'-'*10} {'-'*7} {'-'*7} {'-'*7} {'-'*6} {'-'*7}")

    for i, r in enumerate(sorted_results[:n]):
        sign = "+" if r["pnl"] >= 0 else ""
        mt = str(r["max_trades_per_day"]) if r["max_trades_per_day"] > 0 else "inf"
        print(
            f"  {i+1:<4} {r['num_grids']:<6} {r['lookback_days']:<6} {r['recalc_hours']:<7} "
            f"{r['min_spacing_pct']:<6} {mt:<6} "
            f"{sign}${r['pnl']:>8,.2f} {sign}{r['pnl_pct']:>5.1f}% "
            f"{-r['max_drawdown']:>6.1f}% {r['trades']:>7} {r['win_rate']:>5.1f}% {r['sharpe']:>6.2f}"
        )

    print(f"\n  BOTTOM {n} configs for {pair}")
    print(f"  {'-'*4} {'-'*6} {'-'*6} {'-'*7} {'-'*6} {'-'*6} {'-'*10} {'-'*7} {'-'*7} {'-'*7} {'-'*6} {'-'*7}")

    for i, r in enumerate(sorted_results[-n:]):
        rank = len(sorted_results) - n + i + 1
        sign = "+" if r["pnl"] >= 0 else ""
        mt = str(r["max_trades_per_day"]) if r["max_trades_per_day"] > 0 else "inf"
        print(
            f"  {rank:<4} {r['num_grids']:<6} {r['lookback_days']:<6} {r['recalc_hours']:<7} "
            f"{r['min_spacing_pct']:<6} {mt:<6} "
            f"{sign}${r['pnl']:>8,.2f} {sign}{r['pnl_pct']:>5.1f}% "
            f"{-r['max_drawdown']:>6.1f}% {r['trades']:>7} {r['win_rate']:>5.1f}% {r['sharpe']:>6.2f}"
        )


def save_csv(all_results: list[dict], path: str):
    if not all_results:
        return
    fieldnames = list(all_results[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    print(f"\n  Saved {len(all_results)} results to {path}")


def main():
    print("\n  PARAMETER OPTIMIZATION SWEEP")
    print(f"  {len(ALL_COMBOS)} combinations x {len(PAIRS)} pairs = {len(ALL_COMBOS) * len(PAIRS)} total backtests")
    print(f"  Grid counts: {GRID_COUNTS}")
    print(f"  Lookback days: {LOOKBACK_DAYS}")
    print(f"  Recalc hours: {RECALC_HOURS}")
    print(f"  Min spacing: {MIN_SPACING}")
    print(f"  Max trades/day: {MAX_TRADES}")

    all_results = []
    t0 = time.time()

    for pair_key, pair in PAIRS.items():
        results = run_sweep_for_pair(pair_key, pair)
        if results:
            print_top_bottom(results, pair)
            all_results.extend(results)

    total_time = time.time() - t0
    print(f"\n  Total time: {total_time:.1f}s ({len(all_results)} backtests)")

    os.makedirs("data", exist_ok=True)
    save_csv(all_results, "data/param_sweep_results.csv")


if __name__ == "__main__":
    main()
