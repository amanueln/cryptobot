from datetime import datetime

from exchange.models import Trade


def make_trade(side: str, price: float, amount: float, cost_usd: float, fee: float = 0.5) -> Trade:
    return Trade(
        timestamp=datetime(2026, 1, 1),
        pair="BTC-USD",
        side=side,
        price=price,
        amount=amount,
        cost_usd=cost_usd,
        fee=fee,
        strategy="grid",
    )


def test_win_rate_all_winners():
    from data.performance import calculate_win_rate

    trades = [
        make_trade("buy", 84000.0, 0.001, 84.34),
        make_trade("sell", 85000.0, 0.001, 84.49),
        make_trade("buy", 83000.0, 0.001, 83.33),
        make_trade("sell", 84000.0, 0.001, 83.49),
    ]
    assert calculate_win_rate(trades) == 1.0


def test_win_rate_mixed():
    from data.performance import calculate_win_rate

    trades = [
        make_trade("buy", 84000.0, 0.001, 84.34),
        make_trade("sell", 85000.0, 0.001, 84.49),  # win
        make_trade("buy", 86000.0, 0.001, 86.34),
        make_trade("sell", 85000.0, 0.001, 84.49),  # loss
    ]
    assert calculate_win_rate(trades) == 0.5


def test_win_rate_no_trades():
    from data.performance import calculate_win_rate

    assert calculate_win_rate([]) == 0.0


def test_max_drawdown():
    from data.performance import calculate_max_drawdown

    # equity goes 100 -> 110 -> 90 -> 105
    # peak at 110, trough at 90 => drawdown = 20/110 = 0.1818...
    curve = [100.0, 110.0, 90.0, 105.0]
    dd = calculate_max_drawdown(curve)
    assert abs(dd - (20.0 / 110.0)) < 1e-9


def test_max_drawdown_no_drawdown():
    from data.performance import calculate_max_drawdown

    curve = [100.0, 110.0, 120.0, 130.0]
    assert calculate_max_drawdown(curve) == 0.0


def test_max_drawdown_empty():
    from data.performance import calculate_max_drawdown

    assert calculate_max_drawdown([]) == 0.0


def test_sharpe_ratio():
    from data.performance import calculate_sharpe_ratio

    curve = [100.0, 101.0, 102.0, 103.0]
    sharpe = calculate_sharpe_ratio(curve)
    assert isinstance(sharpe, float)


def test_sharpe_ratio_empty():
    from data.performance import calculate_sharpe_ratio

    assert calculate_sharpe_ratio([]) == 0.0


def test_sharpe_ratio_single_point():
    from data.performance import calculate_sharpe_ratio

    assert calculate_sharpe_ratio([100.0]) == 0.0


def test_total_pnl():
    from data.performance import calculate_total_pnl

    assert calculate_total_pnl(3000.0, 3142.5) == 142.5
