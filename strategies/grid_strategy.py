from dataclasses import dataclass

from exchange.models import Candle, Signal
from strategies.base_strategy import BaseStrategy


@dataclass
class GridLevel:
    price: float
    holding: bool = False
    crypto_amount: float = 0.0


class GridStrategy(BaseStrategy):
    name = "grid"

    def __init__(self):
        self.pair: str = ""
        self.upper_price: float = 0
        self.lower_price: float = 0
        self.num_grids: int = 0
        self.total_investment_usd: float = 0
        self.stop_loss_pct: float = 0
        self.take_profit_pct: float = 0
        self.grid_levels: list[GridLevel] = []
        self.grid_spacing: float = 0
        self.investment_per_grid: float = 0
        self.prev_price: float | None = None
        self.paused: bool = False

    def configure(self, config: dict) -> None:
        self.pair = config["pair"]
        self.upper_price = float(config["upper_price"])
        self.lower_price = float(config["lower_price"])
        self.num_grids = int(config["num_grids"])
        self.total_investment_usd = float(config["total_investment_usd"])
        self.stop_loss_pct = float(config["stop_loss_pct"])
        self.take_profit_pct = float(config["take_profit_pct"])

        self.grid_spacing = (self.upper_price - self.lower_price) / (self.num_grids - 1) if self.num_grids > 1 else 0
        self.investment_per_grid = self.total_investment_usd / self.num_grids
        self.grid_levels = [
            GridLevel(price=self.lower_price + i * self.grid_spacing)
            for i in range(self.num_grids)
        ]

    def on_candle(self, candle: Candle) -> list[Signal]:
        if self.paused:
            return []

        signals: list[Signal] = []
        ref_price = self.prev_price if self.prev_price is not None else candle.open

        # Stop-loss check
        stop_price = self.lower_price * (1 - self.stop_loss_pct)
        if candle.low < stop_price:
            signals.extend(self._liquidate_all(candle, reason="stop-loss"))
            self.paused = True
            self.prev_price = candle.close
            return signals

        # Take-profit check
        tp_price = self.upper_price * (1 + self.take_profit_pct)
        if candle.high > tp_price:
            signals.extend(self._liquidate_all(candle, reason="take-profit"))
            self.paused = True
            self.prev_price = candle.close
            return signals

        # Buy detection: downward crossings
        for level in self.grid_levels:
            if not level.holding and candle.low <= level.price <= ref_price:
                crypto_amount = self.investment_per_grid / level.price if level.price > 0 else 0
                signals.append(Signal(
                    action="buy",
                    pair=self.pair,
                    price=candle.close,
                    order_type="limit",
                    amount_usd=self.investment_per_grid,
                    limit_price=level.price,
                    reason=f"grid buy at {level.price:.0f}",
                ))
                level.holding = True
                level.crypto_amount = crypto_amount

        # Sell detection: upward crossings
        for level in self.grid_levels:
            sell_price = level.price + self.grid_spacing
            if level.holding and level.crypto_amount > 0 and candle.high >= sell_price and ref_price <= sell_price:
                signals.append(Signal(
                    action="sell",
                    pair=self.pair,
                    price=candle.close,
                    order_type="limit",
                    amount_crypto=level.crypto_amount,
                    limit_price=sell_price,
                    reason=f"grid sell at {sell_price:.0f}",
                ))
                level.holding = False
                level.crypto_amount = 0.0

        self.prev_price = candle.close
        return signals

    def _liquidate_all(self, candle: Candle, reason: str) -> list[Signal]:
        signals = []
        for level in self.grid_levels:
            if level.holding and level.crypto_amount > 0:
                signals.append(Signal(
                    action="sell",
                    pair=self.pair,
                    price=candle.close,
                    order_type="market",
                    amount_crypto=level.crypto_amount,
                    reason=reason,
                ))
                level.holding = False
                level.crypto_amount = 0.0
        return signals

    def get_state(self) -> dict:
        return {
            "num_grids": self.num_grids,
            "grid_levels": [
                {"price": gl.price, "holding": gl.holding, "crypto_amount": gl.crypto_amount}
                for gl in self.grid_levels
            ],
            "paused": self.paused,
            "prev_price": self.prev_price,
        }
