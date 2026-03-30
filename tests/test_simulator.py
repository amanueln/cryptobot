from datetime import datetime

from exchange.models import Signal


def test_market_buy():
    from engine.simulator import Simulator

    sim = Simulator(starting_balance_usd=10000.0, maker_fee=0.004, taker_fee=0.006, slippage=0.001)
    signal = Signal(action="buy", pair="BTC-USD", price=85000.0, order_type="market", amount_usd=1000.0)
    trade = sim.execute(signal, current_price=85000.0, timestamp=datetime(2026, 1, 1))

    assert trade is not None
    assert trade.side == "buy"
    # fill price = 85000 * 1.001 = 85085
    assert trade.price == 85000.0 * 1.001
    # fee = 1000 * 0.006 = 6.0
    assert trade.fee == 1000.0 * 0.006
    # crypto bought = (1000 - 6) / 85085
    expected_amount = (1000.0 - 6.0) / 85085.0
    assert abs(trade.amount - expected_amount) < 1e-10
    assert sim.balance_usd == 10000.0 - 1000.0


def test_market_sell():
    from engine.simulator import Simulator

    sim = Simulator(starting_balance_usd=10000.0, maker_fee=0.004, taker_fee=0.006, slippage=0.001)
    buy_signal = Signal(action="buy", pair="BTC-USD", price=85000.0, order_type="market", amount_usd=1000.0)
    buy_trade = sim.execute(buy_signal, current_price=85000.0, timestamp=datetime(2026, 1, 1))
    crypto_held = buy_trade.amount

    sell_signal = Signal(action="sell", pair="BTC-USD", price=86000.0, order_type="market", amount_crypto=crypto_held)
    sell_trade = sim.execute(sell_signal, current_price=86000.0, timestamp=datetime(2026, 1, 2))

    assert sell_trade is not None
    assert sell_trade.side == "sell"
    assert sell_trade.price == 86000.0 * (1 - 0.001)
    assert sim.positions.get("BTC-USD") is None or sim.positions["BTC-USD"].amount < 1e-12


def test_limit_buy():
    from engine.simulator import Simulator

    sim = Simulator(starting_balance_usd=10000.0, maker_fee=0.004, taker_fee=0.006, slippage=0.001)
    signal = Signal(
        action="buy", pair="BTC-USD", price=85000.0,
        order_type="limit", amount_usd=500.0, limit_price=84500.0,
    )
    trade = sim.execute(signal, current_price=84500.0, timestamp=datetime(2026, 1, 1))

    assert trade is not None
    assert trade.price == 84500.0
    assert trade.fee == 500.0 * 0.004


def test_limit_sell():
    from engine.simulator import Simulator

    sim = Simulator(starting_balance_usd=10000.0, maker_fee=0.004, taker_fee=0.006, slippage=0.001)
    buy_signal = Signal(action="buy", pair="BTC-USD", price=84000.0, order_type="limit", amount_usd=500.0, limit_price=84000.0)
    buy_trade = sim.execute(buy_signal, current_price=84000.0, timestamp=datetime(2026, 1, 1))

    sell_signal = Signal(
        action="sell", pair="BTC-USD", price=85000.0,
        order_type="limit", amount_crypto=buy_trade.amount, limit_price=85000.0,
    )
    sell_trade = sim.execute(sell_signal, current_price=85000.0, timestamp=datetime(2026, 1, 2))

    assert sell_trade is not None
    assert sell_trade.price == 85000.0
    assert sell_trade.fee == sell_trade.amount * 85000.0 * 0.004


def test_reject_insufficient_balance():
    from engine.simulator import Simulator

    sim = Simulator(starting_balance_usd=100.0)
    signal = Signal(action="buy", pair="BTC-USD", price=85000.0, order_type="market", amount_usd=200.0)
    trade = sim.execute(signal, current_price=85000.0, timestamp=datetime(2026, 1, 1))
    assert trade is None


def test_reject_insufficient_crypto():
    from engine.simulator import Simulator

    sim = Simulator(starting_balance_usd=10000.0)
    signal = Signal(action="sell", pair="BTC-USD", price=85000.0, order_type="market", amount_crypto=1.0)
    trade = sim.execute(signal, current_price=85000.0, timestamp=datetime(2026, 1, 1))
    assert trade is None


def test_get_equity():
    from engine.simulator import Simulator

    sim = Simulator(starting_balance_usd=10000.0)
    buy_signal = Signal(action="buy", pair="BTC-USD", price=85000.0, order_type="limit", amount_usd=1000.0, limit_price=85000.0)
    sim.execute(buy_signal, current_price=85000.0, timestamp=datetime(2026, 1, 1))

    equity = sim.get_equity({"BTC-USD": 90000.0})
    assert equity > 9000.0


def test_snapshot_equity():
    from engine.simulator import Simulator

    sim = Simulator(starting_balance_usd=10000.0)
    sim.snapshot_equity({"BTC-USD": 85000.0})
    sim.snapshot_equity({"BTC-USD": 86000.0})

    assert len(sim.equity_curve) == 2
    assert sim.equity_curve[0] == 10000.0
