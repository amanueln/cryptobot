"""Backtest Intelligent (regime-aware) system vs dumb grid across pairs and time windows."""

import yaml
import os
from datetime import datetime, timedelta

from exchange.coinbase_client import CoinbaseClient
from data.candle_store import CandleStore
from main import run_backtest


DB_PATH = "data/candles.db"
PAIRS = {
    "doge": "DOGE-USD",
    "eth": "ETH-USD",
    "sol": "SOL-USD",
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
    if not candles or len(candles) < 250:
        return None

    bot_config_path = os.path.join("config", "bot_config.yaml")
    with open(bot_config_path) as f:
        bot_config = yaml.safe_load(f)

    starting_balance = bot_config.get("starting_balance_usd", 3000)
    sim = bot_config.get("simulation", {})

    if strategy == "intelligent":
        # Load the pair's grid config for the grid sub-strategy
        grid_config_path = os.path.join("config", "strategies", f"{pair_key}.yaml")
        if not os.path.exists(grid_config_path):
            grid_config_path = os.path.join("config", "strategies", "grid.yaml")
        with open(grid_config_path) as f:
            grid_config = yaml.safe_load(f)
        grid_config["pair"] = pair
        grid_config = auto_fit_grid(candles, grid_config)

        # Load intelligence config
        intel_config_path = os.path.join("config", "intelligence.yaml")
        with open(intel_config_path) as f:
            intel_config = yaml.safe_load(f)

        # DCA sub-strategy config
        dca_config = {
            "pair": pair,
            "granularity": granularity,
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
            "starting_balance": starting_balance,
        }

        config = {
            "pair": pair,
            "detector": intel_config,
            "grid": grid_config,
            "dca": dca_config,
            "starting_balance": starting_balance,
        }
        strat_name = "intelligent"
    else:
        # Dumb grid — load pair config, auto-fit
        config_path = os.path.join("config", "strategies", f"{pair_key}.yaml")
        if not os.path.exists(config_path):
            return None
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
        f"  {r['pair']:<10} {r['strategy']:<14} "
        f"{sign}${r['pnl']:>10,.2f} {sign}{r['pnl_pct']:>6.1f}% "
        f"{-r['drawdown']:>7.1f}% {r['trades']:>8} {r['win_rate']:>7.1f}% {r['sharpe']:>8.2f}"
    )


HEADER = f"  {'Pair':<10} {'Strategy':<14} {'P&L':>12} {'P&L%':>8} {'DD%':>8} {'Trades':>8} {'WR%':>8} {'Sharpe':>8}"
DIVIDER = f"  {'-'*10} {'-'*14} {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}"


def main():
    for days in [90, 365]:
        print(f"\n{'='*100}")
        print(f"  {days}-DAY BACKTEST: Intelligent (regime-aware) vs Dumb Grid")
        print(f"{'='*100}")
        print(HEADER)
        print(DIVIDER)

        for pair_key in PAIRS:
            for strat in ["grid", "intelligent"]:
                r = run_one(pair_key, days, strat)
                if r:
                    print(fmt(r))
                else:
                    print(f"  {PAIRS[pair_key]:<10} {strat:<14}  -- no data --")
            print()


if __name__ == "__main__":
    main()
