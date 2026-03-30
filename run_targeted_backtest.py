"""Run targeted backtests: adaptive+floor for DOGE/PEPE/ETH, death cross for the rest."""

import yaml
import os
from datetime import datetime, timedelta

from exchange.coinbase_client import CoinbaseClient
from data.candle_store import CandleStore
from main import run_backtest, STRATEGY_MAP


DB_PATH = "data/candles.db"

# Pairs that went profitable with adaptive — test with floor + trade cap
ADAPTIVE_PAIRS = ["doge", "pepe", "eth"]
# Pairs that do best with death cross filter
DEATH_CROSS_PAIRS = ["avax", "link", "ada", "dot", "sol", "btc"]


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
    lows = [c.low for c in candles]
    highs = [c.high for c in candles]
    config = dict(base_config)
    config["lower_price"] = min(lows) * 0.95
    config["upper_price"] = max(highs) * 1.05
    return config


def run_one(strategy_name: str, days: int, mode: str) -> dict | None:
    config_path = os.path.join("config", "strategies", f"{strategy_name}.yaml")
    with open(config_path) as f:
        base_config = yaml.safe_load(f)

    pair = base_config["pair"]
    granularity = base_config.get("granularity", "ONE_HOUR")
    candles = ensure_candles(pair, granularity, days)
    if not candles or len(candles) < 100:
        return None

    config = auto_fit_grid(candles, base_config)

    if mode == "adaptive_floor":
        config["adaptive_range"] = True
        config["range_lookback_days"] = 14
        config["recalc_interval_hours"] = 24
        config["min_spacing_pct"] = 0.02
        config["max_trades_per_day"] = 20
        config["range_only_filter"] = True
        config["ema_convergence_pct"] = 3.0
        config["ema_fast_period"] = 50
        config["ema_slow_period"] = 200
        config["use_trend_filter"] = False
    elif mode == "adaptive_no_floor":
        config["adaptive_range"] = True
        config["range_lookback_days"] = 14
        config["recalc_interval_hours"] = 24
        config["min_spacing_pct"] = 0
        config["max_trades_per_day"] = 0
        config["range_only_filter"] = True
        config["ema_convergence_pct"] = 3.0
        config["ema_fast_period"] = 50
        config["ema_slow_period"] = 200
        config["use_trend_filter"] = False
    elif mode == "death_cross":
        config["use_trend_filter"] = True
        config["ema_fast_period"] = 50
        config["ema_slow_period"] = 200
        config["adaptive_range"] = False
        config["range_only_filter"] = False
    else:  # static
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
        f"  {r['pair']:<10} {r['mode']:<18} "
        f"{sign}${r['pnl']:>10,.2f} {sign}{r['pnl_pct']:>6.1f}% "
        f"{-r['drawdown']:>7.1f}% {r['trades']:>8} {r['win_rate']:>7.1f}% {r['sharpe']:>8.2f}"
    )


HEADER = f"  {'Pair':<10} {'Mode':<18} {'P&L':>12} {'P&L%':>8} {'DD%':>8} {'Trades':>8} {'WR%':>8} {'Sharpe':>8}"
DIVIDER = f"  {'-'*10} {'-'*18} {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}"


def main():
    windows = [90, 180, 365]

    for days in windows:
        print(f"\n{'='*90}")
        print(f"  {days}-DAY: Adaptive pairs (DOGE/PEPE/ETH) — No Floor vs Floor+Cap")
        print(f"{'='*90}")
        print(HEADER)
        print(DIVIDER)

        for strat in ADAPTIVE_PAIRS:
            for mode in ["static", "adaptive_no_floor", "adaptive_floor"]:
                r = run_one(strat, days, mode)
                if r:
                    print(fmt(r))
            print()

        print(f"\n{'-'*90}")
        print(f"  {days}-DAY: Death Cross pairs — recommended config")
        print(f"{'-'*90}")
        print(HEADER)
        print(DIVIDER)

        for strat in DEATH_CROSS_PAIRS:
            for mode in ["static", "death_cross"]:
                r = run_one(strat, days, mode)
                if r:
                    print(fmt(r))
            print()


if __name__ == "__main__":
    main()
