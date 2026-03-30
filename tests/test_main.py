import sys
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from io import StringIO

from exchange.models import Candle, BacktestResult


def make_test_candles(n: int = 10) -> list[Candle]:
    return [
        Candle(
            pair="BTC-USD", granularity="ONE_HOUR",
            timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
            open=85000, high=85500, low=84500, close=85000, volume=100,
        )
        for i in range(n)
    ]


def test_main_backtest_runs(tmp_path):
    from main import run_backtest

    candles = make_test_candles(20)

    config = {
        "pair": "BTC-USD",
        "granularity": "ONE_HOUR",
        "upper_price": 90000,
        "lower_price": 80000,
        "num_grids": 10,
        "total_investment_usd": 1000,
        "stop_loss_pct": 0.15,
        "take_profit_pct": 0.10,
    }

    result = run_backtest(
        strategy_name="grid",
        strategy_config=config,
        candles=candles,
        starting_balance=3000.0,
    )

    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == 20


def test_format_results():
    from main import format_results

    result = BacktestResult(
        total_trades=47,
        win_rate=0.723,
        total_pnl=142.5,
        max_drawdown=0.032,
        sharpe_ratio=1.84,
        equity_curve=[3000 + i * 3 for i in range(90)],
        trades=[],
    )

    output = format_results(result, "grid", "BTC-USD", 3000.0, 90)
    assert "BACKTEST RESULTS" in output
    assert "Grid" in output or "grid" in output
    assert "142.50" in output or "142.5" in output
    assert "72.3%" in output
    assert "Sharpe" in output


def test_parse_args():
    from main import parse_args

    args = parse_args(["--backtest", "--strategy", "grid", "--pair", "BTC-USD", "--days", "90"])
    assert args.backtest is True
    assert args.strategy == "grid"
    assert args.pair == "BTC-USD"
    assert args.days == 90
