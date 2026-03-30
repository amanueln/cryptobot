from datetime import datetime


def test_candle_creation():
    from exchange.models import Candle

    c = Candle(
        pair="BTC-USD",
        granularity="ONE_HOUR",
        timestamp=datetime(2026, 1, 1, 12, 0),
        open=85000.0,
        high=85500.0,
        low=84800.0,
        close=85200.0,
        volume=123.45,
    )
    assert c.pair == "BTC-USD"
    assert c.high == 85500.0


def test_signal_defaults():
    from exchange.models import Signal

    s = Signal(action="buy", pair="BTC-USD", price=85000.0, order_type="market", amount_usd=150.0)
    assert s.limit_price is None
    assert s.amount_crypto is None
    assert s.reason == ""


def test_trade_creation():
    from exchange.models import Trade

    t = Trade(
        timestamp=datetime(2026, 1, 1, 12, 0),
        pair="BTC-USD",
        side="buy",
        price=85000.0,
        amount=0.001,
        cost_usd=85.34,
        fee=0.34,
        strategy="grid",
    )
    assert t.side == "buy"
    assert t.fee == 0.34
    assert t.reason == ""


def test_position_creation():
    from exchange.models import Position

    p = Position(pair="BTC-USD", amount=0.5, avg_entry_price=84000.0, cost_basis=42000.0)
    assert p.cost_basis == 42000.0


def test_backtest_result_creation():
    from exchange.models import BacktestResult

    r = BacktestResult(
        total_trades=10,
        win_rate=0.7,
        total_pnl=142.5,
        max_drawdown=0.032,
        sharpe_ratio=1.84,
        equity_curve=[3000.0, 3050.0, 3142.5],
        trades=[],
    )
    assert r.win_rate == 0.7
    assert len(r.equity_curve) == 3
