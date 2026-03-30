"""Compare mean reversion vs grid strategy across pairs and time windows."""

import yaml
import os
from datetime import datetime, timedelta

from exchange.coinbase_client import CoinbaseClient
from data.candle_store import CandleStore
from main import run_backtest


DB_PATH = "data/candles.db"
PAIRS = {
    "doge": "DOGE-USD",
    "pepe": "PEPE-USD",
    "eth": "ETH-USD",
    "sol": "SOL-USD",
    "btc": "BTC-USD",
}


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


def run_one(pair_key: str, days: int, strategy: str) -> dict | None:
    pair = PAIRS[pair_key]
    granularity = "ONE_HOUR"

    candles = ensure_candles(pair, granularity, days)
    if not candles or len(candles) < 100:
        return None

    bot_config_path = os.path.join("config", "bot_config.yaml")
    with open(bot_config_path) as f:
        bot_config = yaml.safe_load(f)

    starting_balance = bot_config.get("starting_balance_usd", 3000)
    sim = bot_config.get("simulation", {})

    if strategy == "mean_reversion":
        config = {
            "pair": pair,
            "granularity": granularity,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "bb_period": 20,
            "bb_std_dev": 2,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "require_macd_confirm": True,
            "risk_reward_ratio": 2.0,
            "atr_period": 14,
            "position_size_usd": 500,
        }
        strat_name = "mean_reversion"
    else:
        # Load grid config for this pair, auto-fit range
        config_path = os.path.join("config", "strategies", f"{pair_key}.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        config["pair"] = pair
        config = auto_fit_grid(candles, config)
        strat_name = pair_key

    result = run_backtest(
        strategy_name=strat_name,
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
        "strategy": strategy,
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
        f"  {r['pair']:<10} {r['strategy']:<18} "
        f"{sign}${r['pnl']:>10,.2f} {sign}{r['pnl_pct']:>6.1f}% "
        f"{-r['drawdown']:>7.1f}% {r['trades']:>8} {r['win_rate']:>7.1f}% {r['sharpe']:>8.2f}"
    )


HEADER = f"  {'Pair':<10} {'Strategy':<18} {'P&L':>12} {'P&L%':>8} {'DD%':>8} {'Trades':>8} {'WR%':>8} {'Sharpe':>8}"
DIVIDER = f"  {'-'*10} {'-'*18} {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}"


def main():
    for days in [90, 365]:
        print(f"\n{'='*90}")
        print(f"  {days}-DAY BACKTEST: Mean Reversion vs Grid (best config per pair)")
        print(f"{'='*90}")
        print(HEADER)
        print(DIVIDER)

        for pair_key in PAIRS:
            for strat in ["grid", "mean_reversion"]:
                r = run_one(pair_key, days, strat)
                if r:
                    print(fmt(r))
            print()


if __name__ == "__main__":
    main()
