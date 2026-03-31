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
from intelligence.strategy_orchestrator import StrategyOrchestrator
from intelligence.pair_selector import PairSelector, load_pair_selector_config
from intelligence.ml_predictor import MLPredictor, load_ml_config
from engine.backtester import Backtester
from engine.bot_engine import BotEngine


def auto_fit_grid_config(pair: str, candles: list[Candle], starting_balance: float) -> dict:
    """Auto-configure grid strategy from actual price data.

    Uses optimized adaptive params: grids=15, lookback=21d, recalc=12h,
    min_spacing=1%, max_trades=20, adaptive_range=true.
    Trend filter and range-only filter are OFF so the grid always trades —
    ML gating is the comparison, not trend filter vs no filter.
    """
    closes = [c.close for c in candles]
    # Initial range from full data so the grid is in-range from candle #1
    low = min(c.low for c in candles)
    high = max(c.high for c in candles)
    pad = 0.02  # 2% padding
    current_price = closes[-1]

    print(f"  Auto-fit grid for {pair}:")
    print(f"    Price range (365d): ${low:.6f} – ${high:.6f}  (current: ${current_price:.6f})")
    print(f"    Grid range: ${low * (1 - pad):.6f} – ${high * (1 + pad):.6f}  (±2% pad)")
    print(f"    Params: grids=15, adaptive=true, lookback=21d, recalc=12h, spacing>=1%")

    return {
        "pair": pair,
        "granularity": "ONE_HOUR",
        "upper_price": high * (1 + pad),
        "lower_price": low * (1 - pad),
        "num_grids": 15,
        "total_investment_usd": starting_balance,
        "stop_loss_pct": 0.15,
        "take_profit_pct": 0.10,
        "adaptive_range": True,
        "range_lookback_days": 21,
        "recalc_interval_hours": 12,
        "min_spacing_pct": 0.01,
        "max_trades_per_day": 20,
        "range_only_filter": False,
        "use_trend_filter": False,
    }


STRATEGY_MAP = {
    "grid": GridStrategy,
    "mean_reversion": MeanReversionStrategy,
    "dca_safety": DCASafetyStrategy,
    "intelligent": StrategyOrchestrator,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CryptoBot — Backtest & Simulate")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backtest", action="store_true", help="Run in backtest mode")
    mode.add_argument("--simulate", action="store_true", help="Run in simulation mode (live prices, virtual balance)")
    mode.add_argument("--scan", action="store_true", help="Scan all Coinbase pairs and rank them")
    parser.add_argument("--strategy", type=str, default=None, help="Strategy name (e.g. grid, mean_reversion)")
    parser.add_argument("--pair", type=str, default=None, help="Trading pair (overrides strategy config)")
    parser.add_argument("--days", type=int, default=90, help="Number of days to backtest")
    parser.add_argument("--poll", type=int, default=60, help="Poll interval in seconds for simulate mode")
    parser.add_argument("--warmup", type=int, default=30, help="Days of historical data for strategy warmup")
    parser.add_argument("--top", type=int, default=20, help="Number of top pairs to show in scan results")
    parser.add_argument("--ml", action="store_true", help="Enable ML predictions for position sizing")
    parser.add_argument("--hyperopt", action="store_true", help="Run Optuna hyperparameter optimization for ML model")
    parser.add_argument("--auto-fit", action="store_true", dest="auto_fit",
                        help="Auto-fit grid range from price data (grid strategy only)")
    parser.add_argument("--auto-tune-ml", action="store_true", dest="auto_tune_ml",
                        help="Auto-tune ML config (horizons, windows, thresholds) per pair")
    return parser.parse_args(argv)


def run_backtest(
    strategy_name: str,
    strategy_config: dict,
    candles: list[Candle],
    starting_balance: float,
    maker_fee: float = 0.004,
    taker_fee: float = 0.006,
    slippage: float = 0.001,
    use_ml: bool = False,
) -> BacktestResult:
    strategy_cls = STRATEGY_MAP[strategy_name]
    strategy = strategy_cls()
    strategy.configure(strategy_config)

    if not use_ml:
        backtester = Backtester()
        return backtester.run(
            strategy, candles, starting_balance,
            maker_fee=maker_fee, taker_fee=taker_fee, slippage=slippage,
        )

    # ML-enhanced backtest: train on first 60%, predict on remaining 40%
    return _run_ml_backtest(
        strategy, candles, starting_balance,
        strategy_config.get("pair", "BTC-USD"),
        maker_fee, taker_fee, slippage,
    )


def _run_ml_backtest(
    strategy,
    candles: list[Candle],
    starting_balance: float,
    pair: str,
    maker_fee: float,
    taker_fee: float,
    slippage: float,
) -> BacktestResult:
    """Backtest with sliding-window ML retraining gating position sizing.

    Trains on first train_period candles, then retrains every retrain_every
    candles using a sliding window. ML predictions gate ALL buy signals
    from the first training point onward.
    """
    from engine.simulator import Simulator
    from data.performance import (
        calculate_win_rate, calculate_max_drawdown,
        calculate_sharpe_ratio, calculate_total_pnl,
    )

    ml_config = load_ml_config()

    # Load per-pair tuned config if available (from --auto-tune-ml)
    safe = pair.replace("-", "_").lower()
    tuned_path = os.path.join("config", "ml_tuned", f"{safe}.yaml")
    if os.path.exists(tuned_path):
        with open(tuned_path) as f:
            tuned = yaml.safe_load(f) or {}
        for key in ("label_period_candles", "train_period_days", "size_half_threshold",
                     "size_full_threshold"):
            if key in tuned:
                ml_config[key] = tuned[key]
        if "n_estimators" in tuned:
            ml_config.setdefault("lgb_params", {})["n_estimators"] = tuned["n_estimators"]
        print(f"  Loaded tuned ML config for {pair}: horizon={tuned.get('label_period_candles')}h "
              f"window={tuned.get('train_period_days')}d n_est={tuned.get('n_estimators')} "
              f"R2={tuned.get('best_r2', '?')}")

    train_period = int(ml_config.get("train_period_days", 30)) * 24  # hours
    retrain_every = int(ml_config.get("expiration_hours", 168))  # retrain interval
    predictor = MLPredictor(config={**ml_config, "min_training_candles": 100}, models_dir="models/backtest_tmp")

    # Initial training on first train_period candles
    if len(candles) < train_period + 100:
        print(f"  Not enough candles for ML backtest ({len(candles)} < {train_period + 100})")
        train_period = max(200, len(candles) // 4)

    train_candles = candles[:train_period]
    meta = predictor.train(pair, train_candles)
    last_train_idx = train_period
    retrain_count = 0

    if meta:
        print(f"  ML initial train on {train_period} candles "
              f"(RMSE: {meta.validation_rmse:.4f}  R2: {meta.validation_r2:.3f}  "
              f"pred_std: {meta.pred_std:.3f})")
        print(f"  ML active from candle {train_period}, retrain every {retrain_every} candles")
    else:
        print(f"  ML training failed -- running standard backtest")

    simulator = Simulator(
        starting_balance_usd=starting_balance,
        maker_fee=maker_fee,
        taker_fee=taker_fee,
        slippage=slippage,
    )

    ml_trades_skipped = 0
    ml_trades_sized = 0
    ml_trades_full = 0
    ml_predictions_total = 0

    for i, candle in enumerate(candles):
        # Sliding window retrain check
        if meta and i > train_period and (i - last_train_idx) >= retrain_every:
            window_start = max(0, i - train_period)
            retrain_meta = predictor.train(pair, candles[window_start:i])
            if retrain_meta:
                meta = retrain_meta
                last_train_idx = i
                retrain_count += 1

        signals = strategy.on_candle(candle)

        # Get ML size multiplier for this candle
        size_multiplier = 1.0
        if meta and i >= train_period:
            pred = predictor.predict(pair, candles[max(0, i - train_period):i + 1])
            if pred:
                size_multiplier = predictor.get_size_multiplier(pred)
                ml_predictions_total += 1

        for signal in signals:
            # Apply ML sizing to buy signals
            if signal.action == "buy" and signal.amount_usd and meta and i >= train_period:
                if size_multiplier == 0.0:
                    ml_trades_skipped += 1
                    continue
                elif size_multiplier < 1.0:
                    signal.amount_usd = signal.amount_usd * size_multiplier
                    ml_trades_sized += 1
                else:
                    ml_trades_full += 1

            if signal.order_type == "limit" and signal.limit_price is not None:
                simulator.execute(signal, signal.limit_price, candle.timestamp)
            else:
                simulator.execute(signal, candle.close, candle.timestamp)

        simulator.snapshot_equity({candle.pair: candle.close})

    if meta:
        print(f"  ML retrained {retrain_count}x | {ml_predictions_total} predictions | "
              f"skipped {ml_trades_skipped}, resized {ml_trades_sized}, full {ml_trades_full}")

    final_equity = simulator.get_equity(
        {candles[-1].pair: candles[-1].close} if candles else {}
    )

    return BacktestResult(
        total_trades=len(simulator.trades),
        win_rate=calculate_win_rate(simulator.trades),
        total_pnl=calculate_total_pnl(starting_balance, final_equity),
        max_drawdown=calculate_max_drawdown(simulator.equity_curve),
        sharpe_ratio=calculate_sharpe_ratio(simulator.equity_curve),
        equity_curve=simulator.equity_curve,
        trades=simulator.trades,
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


def run_scan(top: int = 20) -> None:
    """Scan all Coinbase USD pairs and print ranked results."""
    bot_config_path = os.path.join("config", "bot_config.yaml")
    with open(bot_config_path) as f:
        bot_config = yaml.safe_load(f)

    starting_balance = bot_config.get("starting_balance_usd", 3000)
    db_path = bot_config.get("data", {}).get("db_path", "data/candles.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    ps_config = load_pair_selector_config()
    selector = PairSelector(ps_config, db_path=db_path)

    print(f"\nScanning all Coinbase USD pairs...")
    print(f"Starting balance: ${starting_balance:,.0f}")
    print(f"Max active pairs: {selector.max_active_pairs}")
    print()

    result = selector.full_scan(starting_balance)

    if not result.ranked:
        print("No pairs could be scored. Check your internet connection.")
        return

    # Print ranked table
    show = result.ranked[:top]
    print(f"{'Rank':<5} {'Pair':<12} {'Score':>6} {'Vol%':>6} {'Range%':>7} "
          f"{'Liq':>5} {'FeeCl':>6} {'Regime':<15} {'BT P&L':>10} {'Status':<8}")
    print("-" * 90)

    active_set = {s.pair for s in result.selected}
    for i, s in enumerate(show, 1):
        status = "ACTIVE" if s.pair in active_set else ""
        regime = s.regime.value.upper()
        sign = "+" if s.backtest_pnl >= 0 else ""
        print(
            f"{i:<5} {s.pair:<12} {s.composite_score * 100:>5.1f} "
            f"{s.volatility:>5.1f}% {s.range_bound:>6.0f}% "
            f"{s.liquidity:>5.1f} {s.fee_clearance:>5.1f}x "
            f"{regime:<15} {sign}${abs(s.backtest_pnl):>8.2f} {status:<8}"
        )

    print()
    print(selector.generate_explanation(result))
    print()

    # Show optimized configs for selected pairs
    configs = selector.get_active_configs()
    if configs:
        print("=" * 50)
        print("  OPTIMIZED CONFIGS FOR SELECTED PAIRS")
        print("=" * 50)
        for pair, config in configs.items():
            print(f"\n  {pair}:")
            print(f"    Grids: {config.get('num_grids')}")
            print(f"    Range: ${config.get('lower_price', 0):.6f} - ${config.get('upper_price', 0):.6f}")
            print(f"    Spacing floor: {config.get('min_spacing_pct', 0) * 100:.1f}%")
            print(f"    Lookback: {config.get('range_lookback_days')} days")


def main() -> None:
    args = parse_args()

    if args.scan:
        run_scan(top=args.top)
        return

    # Backtest and simulate require --strategy
    if not args.strategy:
        print("Error: --strategy is required for --backtest and --simulate modes.")
        return

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

    # Hyperopt mode: optimize ML hyperparameters then exit
    if args.hyperopt:
        ml_config = load_ml_config()
        hp_cfg = ml_config.get("hyperopt", {})
        predictor = MLPredictor(config=ml_config, models_dir="models")
        print(f"Running Optuna hyperopt on {pair} with {len(candles)} candles...")
        result_hp = predictor.hyperopt(
            pair, candles,
            n_trials=hp_cfg.get("n_trials", 50),
            timeout=hp_cfg.get("timeout_seconds", 300),
        )
        print(f"\n  Best RMSE: {result_hp.get('best_rmse', '?'):.4f}")
        print(f"  Best params: {result_hp.get('lgb_params', {})}")
        print(f"  Best n_estimators: {result_hp.get('n_estimators', '?')}")
        return

    # Auto-tune ML: grid-search over horizons, windows, thresholds, n_estimators
    if args.auto_tune_ml:
        import time as _time
        ml_config = load_ml_config()
        predictor = MLPredictor(config=ml_config, models_dir="models")
        print(f"Auto-tuning ML config for {pair} with {len(candles)} candles...")
        print(f"  Testing: horizons=[4,6,8,12,24] x windows=[30,60,90,120]d x n_est=[100,200,400]")
        print(f"  Total combos: {5*4*3} model fits, each tested with 4 confidence thresholds")
        t0 = _time.time()
        result_tune = predictor.auto_tune(pair, candles)
        elapsed = _time.time() - t0
        if "error" in result_tune:
            print(f"\n  Auto-tune failed: {result_tune['error']}")
        else:
            bc = result_tune["best_config"]
            print(f"\n  === Best Config for {pair} (R2={bc['r2']:.4f}) ===")
            print(f"  Prediction horizon: {bc['label_period_candles']}h")
            print(f"  Training window:    {bc['train_period_days']}d")
            print(f"  N estimators:       {bc['n_estimators']}")
            print(f"  Conf threshold:     {bc['size_half_threshold']:.2f} / {bc['size_full_threshold']:.2f}")
            print(f"  RMSE:               {bc['rmse']:.4f}")
            print(f"  Pred std:           {bc['pred_std']:.3f}")
            print(f"  Saved to:           {result_tune['saved_to']}")
            print(f"  Completed in {elapsed:.1f}s")
        return

    # Auto-fit grid config from price data
    if args.auto_fit and args.strategy == "grid":
        strategy_config = auto_fit_grid_config(pair, candles, starting_balance)

    print(f"Running backtest with {len(candles)} candles...")

    result = run_backtest(
        strategy_name=args.strategy,
        strategy_config=strategy_config,
        candles=candles,
        starting_balance=starting_balance,
        maker_fee=sim_config.get("maker_fee", 0.004),
        taker_fee=sim_config.get("taker_fee", 0.006),
        slippage=sim_config.get("slippage", 0.001),
        use_ml=args.ml,
    )

    print(format_results(result, args.strategy, pair, starting_balance, args.days))


if __name__ == "__main__":
    main()
