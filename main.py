import argparse
import os
from datetime import datetime, timedelta

import yaml

from exchange.models import Candle, BacktestResult, Trade
from exchange.coinbase_client import CoinbaseClient
from data.candle_store import CandleStore
from strategies.grid_strategy import GridStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.dca_safety import DCASafetyStrategy
from engine.backtester import Backtester
from engine.bot_engine import BotEngine


STRATEGY_MAP = {
    "grid": GridStrategy,
    "sol": GridStrategy,
    "avax": GridStrategy,
    "doge": GridStrategy,
    "ada": GridStrategy,
    "link": GridStrategy,
    "dot": GridStrategy,
    "pepe": GridStrategy,
    "btc": GridStrategy,
    "eth": GridStrategy,
    "mean_reversion": MeanReversionStrategy,
    "dca_safety": DCASafetyStrategy,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CryptoBot — Backtest & Simulate")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backtest", action="store_true", help="Run in backtest mode")
    mode.add_argument("--simulate", action="store_true", help="Run in simulation mode (live prices, virtual balance)")
    parser.add_argument("--strategy", type=str, required=True, help="Strategy name (e.g. grid, doge, mean_reversion)")
    parser.add_argument("--pair", type=str, default=None, help="Trading pair (overrides strategy config)")
    parser.add_argument("--days", type=int, default=90, help="Number of days to backtest")
    parser.add_argument("--poll", type=int, default=60, help="Poll interval in seconds for simulate mode")
    parser.add_argument("--warmup", type=int, default=30, help="Days of historical data for strategy warmup")
    return parser.parse_args(argv)


def run_backtest(
    strategy_name: str,
    strategy_config: dict,
    candles: list[Candle],
    starting_balance: float,
    maker_fee: float = 0.004,
    taker_fee: float = 0.006,
    slippage: float = 0.001,
) -> BacktestResult:
    strategy_cls = STRATEGY_MAP[strategy_name]
    strategy = strategy_cls()
    strategy.configure(strategy_config)

    backtester = Backtester()
    return backtester.run(
        strategy, candles, starting_balance,
        maker_fee=maker_fee, taker_fee=taker_fee, slippage=slippage,
    )


def format_results(
    result: BacktestResult,
    strategy_name: str,
    pair: str,
    starting_balance: float,
    days: int,
) -> str:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    final_equity = starting_balance + result.total_pnl
    pnl_pct = (result.total_pnl / starting_balance) * 100 if starting_balance > 0 else 0
    pnl_sign = "+" if result.total_pnl >= 0 else ""

    lines = [
        "",
        "=" * 50,
        f"  BACKTEST RESULTS: {strategy_name.title()} Strategy | {pair}",
        f"  Period: {start_date.strftime('%Y-%m-%d')} -> {end_date.strftime('%Y-%m-%d')} ({days} days)",
        "=" * 50,
        f"  Starting Balance:  ${starting_balance:,.2f}",
        f"  Final Equity:      ${final_equity:,.2f}",
        f"  Total P&L:         {pnl_sign}${result.total_pnl:,.2f} ({pnl_sign}{pnl_pct:.1f}%)",
        f"  Win Rate:          {result.win_rate * 100:.1f}% ({_count_wins(result.trades)}/{result.total_trades} trades)",
        f"  Max Drawdown:      -{result.max_drawdown * 100:.1f}%",
        f"  Sharpe Ratio:      {result.sharpe_ratio:.2f}",
        "=" * 50,
    ]

    # Trade log (last 10)
    if result.trades:
        lines.append("")
        show_trades = result.trades[-10:]
        lines.append(f"  TRADE LOG (last {len(show_trades)} of {result.total_trades}):")
        lines.append(f"  {'Time':<16} {'Side':<6} {'Price':<12} {'Amount':<12} {'Fee':<10}")
        lines.append(f"  {'-'*16} {'-'*6} {'-'*12} {'-'*12} {'-'*10}")
        for t in show_trades:
            lines.append(
                f"  {t.timestamp.strftime('%m-%d %H:%M'):<16} "
                f"{t.side.upper():<6} "
                f"${t.price:>10,.2f} "
                f"{t.amount:>10.6f} "
                f"${t.fee:>8.2f}"
            )

    # ASCII equity curve
    if result.equity_curve and len(result.equity_curve) > 1:
        lines.append("")
        lines.extend(_ascii_equity_curve(result.equity_curve))

    lines.append("")
    return "\n".join(lines)


def _count_wins(trades: list[Trade]) -> int:
    wins = 0
    last_buy_price = 0.0
    for t in trades:
        if t.side == "buy":
            last_buy_price = t.price
        elif t.side == "sell" and t.price > last_buy_price:
            wins += 1
    return wins


def _ascii_equity_curve(curve: list[float], width: int = 50, height: int = 8) -> list[str]:
    min_val = min(curve)
    max_val = max(curve)
    val_range = max_val - min_val if max_val != min_val else 1.0

    step = max(1, len(curve) // width)
    sampled = [curve[i] for i in range(0, len(curve), step)][:width]

    lines = ["  EQUITY CURVE:"]
    for row in range(height - 1, -1, -1):
        threshold = min_val + (row / (height - 1)) * val_range
        label = f"${threshold:>10,.0f} |"
        chars = []
        for val in sampled:
            if val >= threshold:
                chars.append("*")
            else:
                chars.append(" ")
        lines.append(f"  {label}{''.join(chars)}")

    lines.append(f"  {' ' * 12}+{'-' * len(sampled)}")
    return lines


def load_candles(pair: str, granularity: str, days: int, db_path: str) -> list[Candle]:
    end = datetime.now()
    start = end - timedelta(days=days)

    store = CandleStore(db_path)
    cached = store.get_candles(pair, granularity, start, end)

    # Estimate expected candle count for this window
    granularity_hours = {"ONE_HOUR": 1, "TWO_HOUR": 2, "SIX_HOUR": 6, "ONE_DAY": 24}
    hours_per_candle = granularity_hours.get(granularity, 1)
    expected = int(days * 24 / hours_per_candle * 0.9)  # 90% threshold

    if cached and len(cached) >= expected:
        return cached

    print(f"Fetching {days} days of {granularity} candles for {pair} from Coinbase...")
    client = CoinbaseClient()
    candles = client.get_candles(pair, granularity, start, end)

    if candles:
        store.save_candles(pair, granularity, candles)
        print(f"Cached {len(candles)} candles to {db_path}")

    # Merge fetched with any existing cached data
    all_candles = store.get_candles(pair, granularity, start, end)
    return all_candles if all_candles else candles


def main() -> None:
    args = parse_args()

    bot_config_path = os.path.join("config", "bot_config.yaml")
    with open(bot_config_path) as f:
        bot_config = yaml.safe_load(f)

    strategy_config_path = os.path.join("config", "strategies", f"{args.strategy}.yaml")
    with open(strategy_config_path) as f:
        strategy_config = yaml.safe_load(f)

    pair = args.pair or strategy_config.get("pair", bot_config.get("default_pair", "BTC-USD"))
    strategy_config["pair"] = pair
    granularity = strategy_config.get("granularity", bot_config.get("default_granularity", "ONE_HOUR"))
    starting_balance = bot_config.get("starting_balance_usd", 3000)
    sim_config = bot_config.get("simulation", {})
    db_path = bot_config.get("data", {}).get("db_path", "data/candles.db")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    if args.simulate:
        engine = BotEngine(
            strategy_name=args.strategy,
            strategy_config=strategy_config,
            starting_balance=starting_balance,
            maker_fee=sim_config.get("maker_fee", 0.004),
            taker_fee=sim_config.get("taker_fee", 0.006),
            slippage=sim_config.get("slippage", 0.001),
            db_path=db_path,
            poll_seconds=args.poll,
            warmup_days=args.warmup,
        )
        engine.run()
        return

    # Backtest mode
    candles = load_candles(pair, granularity, args.days, db_path)
    if not candles:
        print("No candle data available. Check your connection and try again.")
        return

    print(f"Running backtest with {len(candles)} candles...")

    result = run_backtest(
        strategy_name=args.strategy,
        strategy_config=strategy_config,
        candles=candles,
        starting_balance=starting_balance,
        maker_fee=sim_config.get("maker_fee", 0.004),
        taker_fee=sim_config.get("taker_fee", 0.006),
        slippage=sim_config.get("slippage", 0.001),
    )

    print(format_results(result, args.strategy, pair, starting_balance, args.days))


if __name__ == "__main__":
    main()
