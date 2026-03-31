from datetime import datetime

from exchange.models import Signal, Trade, Position


class Simulator:
    def __init__(
        self,
        starting_balance_usd: float,
        maker_fee: float = 0.004,
        taker_fee: float = 0.006,
        slippage: float = 0.001,
    ):
        self.balance_usd = starting_balance_usd
        self.starting_balance = starting_balance_usd
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage = slippage
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[float] = []

    def execute(self, signal: Signal, current_price: float, timestamp: datetime) -> Trade | None:
        if signal.action == "buy":
            return self._execute_buy(signal, current_price, timestamp)
        elif signal.action == "sell":
            return self._execute_sell(signal, current_price, timestamp)
        return None

    def _execute_buy(self, signal: Signal, current_price: float, timestamp: datetime) -> Trade | None:
        amount_usd = signal.amount_usd
        if amount_usd is None or amount_usd > self.balance_usd:
            return None

        if signal.order_type == "limit" and signal.limit_price is not None:
            fill_price = signal.limit_price
            fee = amount_usd * self.maker_fee
        else:
            fill_price = current_price * (1 + self.slippage)
            fee = amount_usd * self.taker_fee

        crypto_amount = (amount_usd - fee) / fill_price
        self.balance_usd -= amount_usd

        pos = self.positions.get(signal.pair)
        if pos is None:
            self.positions[signal.pair] = Position(
                pair=signal.pair,
                amount=crypto_amount,
                avg_entry_price=fill_price,
                cost_basis=amount_usd,
            )
        else:
            total_cost = pos.cost_basis + amount_usd
            total_amount = pos.amount + crypto_amount
            pos.avg_entry_price = total_cost / total_amount if total_amount > 0 else 0
            pos.amount = total_amount
            pos.cost_basis = total_cost

        trade = Trade(
            timestamp=timestamp,
            pair=signal.pair,
            side="buy",
            price=fill_price,
            amount=crypto_amount,
            cost_usd=amount_usd,
            fee=fee,
            strategy="grid",
            reason=signal.reason,
            regime=getattr(signal, 'regime', ''),
            adx=getattr(signal, 'adx', 0.0),
            rsi=getattr(signal, 'rsi', 0.0),
            atr_multiplier=getattr(signal, 'atr_multiplier', 1.0),
        )
        self.trades.append(trade)
        return trade

    def _execute_sell(self, signal: Signal, current_price: float, timestamp: datetime) -> Trade | None:
        amount_crypto = signal.amount_crypto
        pos = self.positions.get(signal.pair)
        if amount_crypto is None or pos is None or pos.amount < amount_crypto - 1e-12:
            return None

        if signal.order_type == "limit" and signal.limit_price is not None:
            fill_price = signal.limit_price
            fee_rate = self.maker_fee
        else:
            fill_price = current_price * (1 - self.slippage)
            fee_rate = self.taker_fee

        gross_usd = amount_crypto * fill_price
        fee = gross_usd * fee_rate
        net_usd = gross_usd - fee

        self.balance_usd += net_usd

        pos.amount -= amount_crypto
        if pos.amount < 1e-12:
            pos.amount = 0.0

        trade = Trade(
            timestamp=timestamp,
            pair=signal.pair,
            side="sell",
            price=fill_price,
            amount=amount_crypto,
            cost_usd=net_usd,
            fee=fee,
            strategy="grid",
            reason=signal.reason,
            regime=getattr(signal, 'regime', ''),
            adx=getattr(signal, 'adx', 0.0),
            rsi=getattr(signal, 'rsi', 0.0),
            atr_multiplier=getattr(signal, 'atr_multiplier', 1.0),
        )
        self.trades.append(trade)
        return trade

    def get_equity(self, current_prices: dict[str, float]) -> float:
        equity = self.balance_usd
        for pair, pos in self.positions.items():
            if pair in current_prices:
                equity += pos.amount * current_prices[pair]
        return equity

    def snapshot_equity(self, current_prices: dict[str, float]) -> None:
        self.equity_curve.append(self.get_equity(current_prices))
