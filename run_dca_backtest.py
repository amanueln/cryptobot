"""Backtest DCA Safety Orders vs Grid across pairs and time windows."""

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
    "avax": "AVAX-USD",
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

    if strategy == "dca_safety":
        config = {
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
        strat_name = "dca_safety"
    else:
        # Grid — load pair-specific config and auto-fit range
        config_path = os.path.join("config", "strategies", f"{pair_key}.yaml")
        if not os.path.exists(config_path):
            # Fall back to generic grid config
            config_path = os.path.join("config", "strategies", "grid.yaml")
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

    # Calculate DCA-specific metrics
    avg_profit_per_deal = 0
    avg_deal_duration = 0
    deals_completed = 0
    if strategy == "dca_safety":
        # Count buy/sell pairs as deals
        buy_count = sum(1 for t in result.trades if t.side == "buy")
        sell_count = sum(1 for t in result.trades if t.side == "sell")
        deals_completed = sell_count  # Each sell closes a deal (or SO buy doesn't count)
        if deals_completed > 0:
            avg_profit_per_deal = result.total_pnl / deals_completed
        # Estimate avg duration from trade timestamps
        if len(result.trades) >= 2:
            first_trade = result.trades[0].timestamp
            last_trade = result.trades[-1].timestamp
            total_hours = (last_trade - first_trade).total_seconds() / 3600
            if deals_completed > 0:
                avg_deal_duration = total_hours / deals_completed

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
        "deals_completed": deals_completed,
        "avg_profit_per_deal": avg_profit_per_deal,
        "avg_deal_duration_hrs": avg_deal_duration,
    }


def fmt(r):
    sign = "+" if r["pnl"] >= 0 else ""
    line = (
        f"  {r['pair']:<10} {r['strategy']:<12} "
        f"{sign}${r['pnl']:>10,.2f} {sign}{r['pnl_pct']:>6.1f}% "
        f"{-r['drawdown']:>7.1f}% {r['trades']:>8} {r['win_rate']:>7.1f}% {r['sharpe']:>8.2f}"
    )
    if r["strategy"] == "dca_safety":
        line += f"  deals={r['deals_completed']} avg=${r['avg_profit_per_deal']:.2f}/deal avg={r['avg_deal_duration_hrs']:.0f}h"
    return line


HEADER = f"  {'Pair':<10} {'Strategy':<12} {'P&L':>12} {'P&L%':>8} {'DD%':>8} {'Trades':>8} {'WR%':>8} {'Sharpe':>8}"
DIVIDER = f"  {'-'*10} {'-'*12} {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}"


def main():
    for days in [90, 365]:
        print(f"\n{'='*100}")
        print(f"  {days}-DAY BACKTEST: DCA Safety Orders vs Grid")
        print(f"{'='*100}")
        print(HEADER)
        print(DIVIDER)

        for pair_key in PAIRS:
            for strat in ["grid", "dca_safety"]:
                r = run_one(pair_key, days, strat)
                if r:
                    print(fmt(r))
                else:
                    print(f"  {PAIRS[pair_key]:<10} {strat:<12}  -- no data --")
            print()


if __name__ == "__main__":
    main()
