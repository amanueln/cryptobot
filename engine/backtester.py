from exchange.models import Candle, BacktestResult
from strategies.base_strategy import BaseStrategy
from engine.simulator import Simulator
from data.performance import (
    calculate_win_rate,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_total_pnl,
)


class Backtester:
    def run(
        self,
        strategy: BaseStrategy,
        candles: list[Candle],
        starting_balance: float,
        maker_fee: float = 0.004,
        taker_fee: float = 0.006,
        slippage: float = 0.001,
    ) -> BacktestResult:
        simulator = Simulator(
            starting_balance_usd=starting_balance,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            slippage=slippage,
        )

        for candle in candles:
            signals = strategy.on_candle(candle)
            for signal in signals:
                if signal.order_type == "limit" and signal.limit_price is not None:
                    simulator.execute(signal, signal.limit_price, candle.timestamp)
                else:
                    simulator.execute(signal, candle.close, candle.timestamp)
            simulator.snapshot_equity({candle.pair: candle.close})

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
