"""Run backtests across multiple time windows comparing static vs adaptive grid."""

import yaml
import os
from datetime import datetime, timedelta

from exchange.coinbase_client import CoinbaseClient
from data.candle_store import CandleStore
from main import run_backtest, STRATEGY_MAP


PAIRS = ["doge", "pepe", "avax", "link", "ada", "dot", "sol", "eth", "btc"]
DB_PATH = "data/candles.db"


def ensure_candles(pair: str, granularity: str, days: int) -> list:
    end = datetime.now()
    start = end - timedelta(days=days)
    store = CandleStore(DB_PATH)
    cached = store.get_candles(pair, granularity, start, end)
    expected = int(days * 24 * 0.9)
    if cached and len(cached) >= expected:
        return cached

    print(f"  Fetching {days}d of {pair}...")
    client = CoinbaseClient()
    candles = client.get_candles(pair, granularity, start, end)
    if candles:
        store.save_candles(pair, granularity, candles)
    return store.get_candles(pair, granularity, start, end) or candles


def auto_fit_grid(candles, base_config: dict) -> dict:
    """Widen grid range to cover the actual price range in the candle data."""
    lows = [c.low for c in candles]
    highs = [c.high for c in candles]
    config = dict(base_config)
    config["lower_price"] = min(lows) * 0.95
    config["upper_price"] = max(highs) * 1.05
    return config


def run_window(strategy_name: str, days: int, mode: str) -> dict | None:
    """
    mode: "static" | "trend_filter" | "adaptive"
      static:       no filter, auto-fitted static grid
      trend_filter:  death cross filter ON, auto-fitted static grid
      adaptive:     adaptive range + range-only filter
    """
    config_path = os.path.join("config", "strategies", f"{strategy_name}.yaml")
    with open(config_path) as f:
        base_config = yaml.safe_load(f)

    pair = base_config["pair"]
    granularity = base_config.get("granularity", "ONE_HOUR")

    candles = ensure_candles(pair, granularity, days)
    if not candles or len(candles) < 100:
        return None

    if mode == "adaptive":
        # Adaptive range: start with auto-fitted range, let strategy recalculate
        config = auto_fit_grid(candles, base_config)
        config["adaptive_range"] = True
        config["range_lookback_days"] = 14
        config["recalc_interval_hours"] = 24
        config["range_only_filter"] = True
        config["ema_convergence_pct"] = 3.0
        config["ema_fast_period"] = 50
        config["ema_slow_period"] = 200
        config["use_trend_filter"] = False
    elif mode == "trend_filter":
        config = auto_fit_grid(candles, base_config)
        config["use_trend_filter"] = True
        config["ema_fast_period"] = 50
        config["ema_slow_period"] = 200
        config["adaptive_range"] = False
        config["range_only_filter"] = False
    else:  # static
        config = auto_fit_grid(candles, base_config)
        config["use_trend_filter"] = False
        config["adaptive_range"] = False
        config["range_only_filter"] = False

    bot_config_path = os.path.join("config", "bot_config.yaml")
    with open(bot_config_path) as f:
        bot_config = yaml.safe_load(f)

    starting_balance = bot_config.get("starting_balance_usd", 3000)
    sim = bot_config.get("simulation", {})

    result = run_backtest(
        strategy_name=strategy_name,
        strategy_config=config,
        candles=candles,
        starting_balance=starting_balance,
        maker_fee=sim.get("maker_fee", 0.004),
        taker_fee=sim.get("taker_fee", 0.006),
        slippage=sim.get("slippage", 0.001),
    )

    return {
        "pair": pair,
        "days": days,
        "mode": mode,
        "candles": len(candles),
        "pnl": result.total_pnl,
        "pnl_pct": (result.total_pnl / starting_balance) * 100,
        "drawdown": result.max_drawdown * 100,
        "trades": result.total_trades,
        "win_rate": result.win_rate * 100,
        "sharpe": result.sharpe_ratio,
    }


def fmt(r):
    sign = "+" if r["pnl"] >= 0 else ""
    return (
        f"  {r['pair']:<10} {r['mode']:<14} "
        f"{sign}${r['pnl']:>10,.2f} {sign}{r['pnl_pct']:>6.1f}% "
        f"{-r['drawdown']:>7.1f}% {r['trades']:>8} {r['win_rate']:>7.1f}% {r['sharpe']:>8.2f}"
    )


def main():
    windows = [90, 180, 365]
    modes = ["static", "trend_filter", "adaptive"]
    mode_labels = {"static": "Static Grid", "trend_filter": "Death Cross", "adaptive": "Adaptive+RO"}

    for days in windows:
        print(f"\n{'='*80}")
        print(f"  {days}-DAY BACKTEST — Static vs Death Cross vs Adaptive+Range-Only")
        print(f"{'='*80}")
        print(f"  {'Pair':<10} {'Mode':<14} {'P&L':>12} {'P&L%':>8} {'DD%':>8} {'Trades':>8} {'WR%':>8} {'Sharpe':>8}")
        print(f"  {'-'*10} {'-'*14} {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

        for strat in PAIRS:
            for mode in modes:
                r = run_window(strat, days, mode)
                if r is None:
                    print(f"  {strat.upper():<10} {mode_labels[mode]:<14} {'(no data)':>12}")
                    continue
                print(fmt(r))
            print()


if __name__ == "__main__":
    main()
