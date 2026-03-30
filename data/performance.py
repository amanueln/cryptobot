import math

from exchange.models import Trade


def calculate_win_rate(trades: list[Trade]) -> float:
    sells = [t for t in trades if t.side == "sell"]
    if not sells:
        return 0.0

    buys = [t for t in trades if t.side == "buy"]
    wins = 0
    buy_idx = 0
    for sell_idx, sell in enumerate(sells):
        # Find the buy that precedes this sell in the original trade list
        # by counting how many buys appeared before this sell's position
        sell_pos = next(
            i for i, t in enumerate(trades) if t.side == "sell" and t is sell
        )
        paired_buys = [t for i, t in enumerate(trades) if t.side == "buy" and i < sell_pos]
        if paired_buys and sell.price > paired_buys[-1].price:
            wins += 1

    return wins / len(sells)


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for equity in equity_curve:
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak if peak > 0 else 0.0
        if drawdown > max_dd:
            max_dd = drawdown
    return max_dd


def calculate_sharpe_ratio(equity_curve: list[float], periods_per_year: int = 365) -> float:
    if len(equity_curve) < 2:
        return 0.0

    returns = []
    for i in range(1, len(equity_curve)):
        if equity_curve[i - 1] != 0:
            returns.append((equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1])

    if not returns:
        return 0.0

    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    std_ret = math.sqrt(variance)

    if std_ret < 1e-12:
        return 0.0

    return (mean_ret / std_ret) * math.sqrt(periods_per_year)


def calculate_total_pnl(starting_balance: float, final_equity: float) -> float:
    return final_equity - starting_balance
