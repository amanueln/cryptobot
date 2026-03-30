from datetime import datetime, timedelta

from exchange.models import Candle


def make_candles(n: int, base_price: float = 85000.0) -> list[Candle]:
    """Generate n candles with slight oscillation to trigger grid buys/sells."""
    candles = []
    for i in range(n):
        if i % 2 == 0:
            o, h, l, c = base_price, base_price + 500, base_price - 1500, base_price - 500
        else:
            o, h, l, c = base_price - 500, base_price + 1500, base_price - 500, base_price + 500
        candles.append(Candle(
            pair="BTC-USD",
            granularity="ONE_HOUR",
            timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
            open=o, high=h, low=l, close=c,
            volume=100.0,
        ))
    return candles


def test_backtester_returns_result():
    from engine.backtester import Backtester
    from strategies.grid_strategy import GridStrategy

    strategy = GridStrategy()
    strategy.configure({
        "pair": "BTC-USD",
        "granularity": "ONE_HOUR",
        "upper_price": 90000,
        "lower_price": 80000,
        "num_grids": 10,
        "total_investment_usd": 1000,
        "stop_loss_pct": 0.15,
        "take_profit_pct": 0.10,
    })

    candles = make_candles(20)
    bt = Backtester()
    result = bt.run(strategy, candles, starting_balance=10000.0)

    assert result.total_trades >= 0
    assert 0.0 <= result.win_rate <= 1.0
    assert isinstance(result.total_pnl, float)
    assert isinstance(result.max_drawdown, float)
    assert isinstance(result.sharpe_ratio, float)
    assert len(result.equity_curve) == 20
    assert len(result.trades) == result.total_trades


def test_backtester_no_trades_flat_market():
    from engine.backtester import Backtester
    from strategies.grid_strategy import GridStrategy

    strategy = GridStrategy()
    strategy.configure({
        "pair": "BTC-USD",
        "granularity": "ONE_HOUR",
        "upper_price": 90000,
        "lower_price": 80000,
        "num_grids": 10,
        "total_investment_usd": 1000,
        "stop_loss_pct": 0.15,
        "take_profit_pct": 0.10,
    })

    candles = [
        Candle(
            pair="BTC-USD", granularity="ONE_HOUR",
            timestamp=datetime(2026, 1, 1) + timedelta(hours=i),
            open=95000, high=95000, low=95000, close=95000, volume=100.0,
        )
        for i in range(10)
    ]
    bt = Backtester()
    result = bt.run(strategy, candles, starting_balance=10000.0)
    assert result.total_trades == 0
    assert result.total_pnl == 0.0


def test_backtester_equity_curve_length():
    from engine.backtester import Backtester
    from strategies.grid_strategy import GridStrategy

    strategy = GridStrategy()
    strategy.configure({
        "pair": "BTC-USD",
        "granularity": "ONE_HOUR",
        "upper_price": 90000,
        "lower_price": 80000,
        "num_grids": 5,
        "total_investment_usd": 500,
        "stop_loss_pct": 0.15,
        "take_profit_pct": 0.10,
    })

    candles = make_candles(50)
    bt = Backtester()
    result = bt.run(strategy, candles, starting_balance=5000.0)
    assert len(result.equity_curve) == 50
