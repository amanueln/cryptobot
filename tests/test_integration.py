"""End-to-end integration test: strategy -> backtester -> results."""
from datetime import datetime, timedelta

from exchange.models import Candle


def test_full_backtest_pipeline():
    from strategies.grid_strategy import GridStrategy
    from engine.backtester import Backtester

    candles = []
    base = 85000.0
    for i in range(100):
        import math
        offset = 2000 * math.sin(i * 0.3)
        price = base + offset
        candles.append(Candle(
            pair="BTC-USD",
            granularity="ONE_HOUR",
            timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
            open=price - 100,
            high=price + 500,
            low=price - 500,
            close=price + 100,
            volume=50.0,
        ))

    strategy = GridStrategy()
    strategy.configure({
        "pair": "BTC-USD",
        "granularity": "ONE_HOUR",
        "upper_price": 88000,
        "lower_price": 82000,
        "num_grids": 12,
        "total_investment_usd": 1200,
        "stop_loss_pct": 0.15,
        "take_profit_pct": 0.10,
    })

    bt = Backtester()
    result = bt.run(strategy, candles, starting_balance=5000.0)

    assert result.total_trades > 0
    assert len(result.equity_curve) == 100
    assert result.max_drawdown >= 0.0
    assert result.max_drawdown <= 1.0
    assert isinstance(result.sharpe_ratio, float)
    assert result.win_rate > 0.0

    sides = {t.side for t in result.trades}
    assert "buy" in sides
    assert "sell" in sides


def test_format_results_integration():
    """Ensure format_results doesn't crash on real backtest output."""
    from strategies.grid_strategy import GridStrategy
    from engine.backtester import Backtester
    from main import format_results

    candles = []
    for i in range(50):
        import math
        price = 85000 + 1500 * math.sin(i * 0.2)
        candles.append(Candle(
            pair="BTC-USD", granularity="ONE_HOUR",
            timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
            open=price, high=price + 300, low=price - 300, close=price, volume=100,
        ))

    strategy = GridStrategy()
    strategy.configure({
        "pair": "BTC-USD", "granularity": "ONE_HOUR",
        "upper_price": 88000, "lower_price": 82000,
        "num_grids": 10, "total_investment_usd": 1000,
        "stop_loss_pct": 0.15, "take_profit_pct": 0.10,
    })

    result = Backtester().run(strategy, candles, starting_balance=3000.0)
    output = format_results(result, "grid", "BTC-USD", 3000.0, 2)

    assert "BACKTEST RESULTS" in output
    assert "Grid" in output
    assert "Sharpe" in output
