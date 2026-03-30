from datetime import datetime

from exchange.models import Candle


GRID_CONFIG = {
    "pair": "BTC-USD",
    "granularity": "ONE_HOUR",
    "upper_price": 90000,
    "lower_price": 80000,
    "num_grids": 10,
    "total_investment_usd": 1000,
    "stop_loss_pct": 0.15,
    "take_profit_pct": 0.10,
}


def make_candle(
    open_: float, high: float, low: float, close: float, hour: int = 0
) -> Candle:
    return Candle(
        pair="BTC-USD",
        granularity="ONE_HOUR",
        timestamp=datetime(2026, 1, 1, hour, 0),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
    )


def test_grid_configure():
    from strategies.grid_strategy import GridStrategy

    gs = GridStrategy()
    gs.configure(GRID_CONFIG)
    state = gs.get_state()
    assert state["num_grids"] == 10
    assert len(state["grid_levels"]) == 10


def test_first_candle_buys_below_open():
    from strategies.grid_strategy import GridStrategy

    gs = GridStrategy()
    gs.configure(GRID_CONFIG)
    # Grid levels with 10 grids between 80000-90000:
    # 80000, 81111.11, 82222.22, 83333.33, 84444.44, 85555.56, 86666.67, 87777.78, 88888.89, 90000
    # Open at 85000, low at 83000 => should buy at levels 84444.44 and 83333.33
    candle = make_candle(open_=85000, high=85500, low=83000, close=84000)
    signals = gs.on_candle(candle)

    buy_signals = [s for s in signals if s.action == "buy"]
    assert len(buy_signals) >= 2  # at least 84444 and 83333 levels
    for s in buy_signals:
        assert s.order_type == "limit"
        assert s.amount_usd == 1000 / 10  # total_investment / num_grids


def test_sell_on_upward_crossing():
    from strategies.grid_strategy import GridStrategy

    gs = GridStrategy()
    gs.configure(GRID_CONFIG)
    # First candle: buy at some levels
    c1 = make_candle(open_=85000, high=85000, low=83000, close=83500, hour=0)
    gs.on_candle(c1)

    # Second candle: price rises above next grid level => sell
    c2 = make_candle(open_=83500, high=86000, low=83500, close=85500, hour=1)
    signals = gs.on_candle(c2)

    sell_signals = [s for s in signals if s.action == "sell"]
    assert len(sell_signals) > 0
    for s in sell_signals:
        assert s.order_type == "limit"
        assert s.amount_crypto is not None
        assert s.amount_crypto > 0


def test_stop_loss_triggers():
    from strategies.grid_strategy import GridStrategy

    gs = GridStrategy()
    gs.configure(GRID_CONFIG)
    c1 = make_candle(open_=85000, high=85000, low=82000, close=83000, hour=0)
    gs.on_candle(c1)

    # Stop loss at 80000 * (1 - 0.15) = 68000
    c2 = make_candle(open_=83000, high=83000, low=67000, close=68000, hour=1)
    signals = gs.on_candle(c2)

    sell_signals = [s for s in signals if s.action == "sell"]
    assert len(sell_signals) > 0


def test_take_profit_triggers():
    from strategies.grid_strategy import GridStrategy

    gs = GridStrategy()
    gs.configure(GRID_CONFIG)
    c1 = make_candle(open_=85000, high=85000, low=82000, close=83000, hour=0)
    gs.on_candle(c1)

    # Take profit at 90000 * (1 + 0.10) = 99000
    c2 = make_candle(open_=83000, high=100000, low=83000, close=99000, hour=1)
    signals = gs.on_candle(c2)

    sell_signals = [s for s in signals if s.action == "sell"]
    assert len(sell_signals) > 0


def test_no_signals_when_paused():
    from strategies.grid_strategy import GridStrategy

    gs = GridStrategy()
    gs.configure(GRID_CONFIG)
    c1 = make_candle(open_=85000, high=85000, low=82000, close=83000, hour=0)
    gs.on_candle(c1)
    c2 = make_candle(open_=83000, high=83000, low=67000, close=68000, hour=1)
    gs.on_candle(c2)

    c3 = make_candle(open_=70000, high=75000, low=69000, close=74000, hour=2)
    signals = gs.on_candle(c3)
    assert signals == []


def test_get_state():
    from strategies.grid_strategy import GridStrategy

    gs = GridStrategy()
    gs.configure(GRID_CONFIG)
    state = gs.get_state()
    assert "grid_levels" in state
    assert "paused" in state
    assert state["paused"] is False
