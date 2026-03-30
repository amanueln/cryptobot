from collections import deque
from dataclasses import dataclass

from exchange.models import Candle, Signal
from strategies.base_strategy import BaseStrategy


@dataclass
class GridLevel:
    price: float
    holding: bool = False
    crypto_amount: float = 0.0


class EMACalculator:
    """Incremental EMA that updates one candle at a time."""

    def __init__(self, period: int):
        self.period = period
        self.multiplier = 2 / (period + 1)
        self.value: float | None = None
        self._warmup: list[float] = []

    def update(self, close: float) -> float | None:
        if self.value is None:
            self._warmup.append(close)
            if len(self._warmup) >= self.period:
                self.value = sum(self._warmup) / len(self._warmup)
                self._warmup = []
            return self.value
        self.value = (close - self.value) * self.multiplier + self.value
        return self.value


HOURS_PER_CANDLE = {
    "ONE_HOUR": 1, "TWO_HOUR": 2, "SIX_HOUR": 6, "ONE_DAY": 24,
}


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

        # Trend filter (legacy death cross)
        self.use_trend_filter: bool = False
        self.ema_fast: EMACalculator | None = None
        self.ema_slow: EMACalculator | None = None
        self.buys_blocked: bool = False

        # Range-only filter
        self.range_only_filter: bool = False
        self.ema_convergence_pct: float = 3.0
        self.grid_paused_divergence: bool = False

        # Adaptive range
        self.adaptive_range: bool = False
        self.range_lookback_days: int = 14
        self.recalc_interval_hours: int = 24
        self.min_spacing_pct: float = 0.02  # 2% of price
        self._candle_history: deque[Candle] = deque()
        self._candles_since_recalc: int = 0
        self._recalc_interval_candles: int = 0

        # Daily trade cap
        self.max_trades_per_day: int = 0  # 0 = unlimited
        self._trade_timestamps: deque[float] = deque()  # unix timestamps of recent trades
        self._trade_cap_paused: bool = False

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

        # Trend filter config (legacy death cross)
        self.use_trend_filter = bool(config.get("use_trend_filter", False))
        ema_fast_period = int(config.get("ema_fast_period", 50))
        ema_slow_period = int(config.get("ema_slow_period", 200))
        if self.use_trend_filter:
            self.ema_fast = EMACalculator(ema_fast_period)
            self.ema_slow = EMACalculator(ema_slow_period)

        # Range-only filter config
        self.range_only_filter = bool(config.get("range_only_filter", False))
        self.ema_convergence_pct = float(config.get("ema_convergence_pct", 3.0))
        if self.range_only_filter:
            if self.ema_fast is None:
                self.ema_fast = EMACalculator(ema_fast_period)
            if self.ema_slow is None:
                self.ema_slow = EMACalculator(ema_slow_period)

        # Adaptive range config
        self.adaptive_range = bool(config.get("adaptive_range", False))
        self.range_lookback_days = int(config.get("range_lookback_days", 14))
        self.recalc_interval_hours = int(config.get("recalc_interval_hours", 24))
        self.min_spacing_pct = float(config.get("min_spacing_pct", 0.02))
        if self.adaptive_range:
            granularity = config.get("granularity", "ONE_HOUR")
            hpc = HOURS_PER_CANDLE.get(granularity, 1)
            max_lookback = int(self.range_lookback_days * 24 / hpc)
            self._candle_history = deque(maxlen=max_lookback)
            self._recalc_interval_candles = int(self.recalc_interval_hours / hpc)

        # Daily trade cap
        self.max_trades_per_day = int(config.get("max_trades_per_day", 0))

    def _update_trend_filter(self, close: float) -> None:
        if self.ema_fast is None or self.ema_slow is None:
            return

        ema50 = self.ema_fast.update(close)
        ema200 = self.ema_slow.update(close)

        if ema50 is None or ema200 is None:
            self.buys_blocked = False
            self.grid_paused_divergence = False
            return

        if self.range_only_filter:
            divergence = abs(ema50 - ema200) / ema200 if ema200 != 0 else 0
            self.grid_paused_divergence = divergence >= (self.ema_convergence_pct / 100)
            self.buys_blocked = self.grid_paused_divergence
        elif self.use_trend_filter:
            if close < ema50 and close < ema200 and ema50 < ema200:
                self.buys_blocked = True
            elif close > ema50:
                self.buys_blocked = False

    def _maybe_recalc_range(self, candle: Candle) -> list[Signal]:
        if not self.adaptive_range:
            return []

        self._candle_history.append(candle)
        self._candles_since_recalc += 1

        if (
            len(self._candle_history) < self._candle_history.maxlen
            or self._candles_since_recalc < self._recalc_interval_candles
        ):
            return []

        self._candles_since_recalc = 0

        new_lower = min(c.low for c in self._candle_history)
        new_upper = max(c.high for c in self._candle_history)

        # Enforce minimum grid spacing floor
        if self.min_spacing_pct > 0 and self.num_grids > 1:
            mid_price = (new_lower + new_upper) / 2
            min_spacing = mid_price * self.min_spacing_pct
            min_range = min_spacing * (self.num_grids - 1)
            current_range = new_upper - new_lower
            if current_range < min_range:
                expand = (min_range - current_range) / 2
                new_lower -= expand
                new_upper += expand

        if new_lower == self.lower_price and new_upper == self.upper_price:
            return []

        # Liquidate positions outside new range
        liquidation_signals: list[Signal] = []
        for level in self.grid_levels:
            if level.holding and level.crypto_amount > 0:
                if level.price < new_lower or level.price > new_upper:
                    liquidation_signals.append(Signal(
                        action="sell",
                        pair=self.pair,
                        price=candle.close,
                        order_type="market",
                        amount_crypto=level.crypto_amount,
                        reason=f"adaptive liquidation: level {level.price:.2f} outside [{new_lower:.2f}, {new_upper:.2f}]",
                    ))
                    level.holding = False
                    level.crypto_amount = 0.0

        # Snapshot in-range holdings before rebuilding
        old_holdings: dict[float, tuple[bool, float]] = {}
        for level in self.grid_levels:
            if level.holding:
                old_holdings[level.price] = (True, level.crypto_amount)

        # Rebuild grid with new boundaries
        self.lower_price = new_lower
        self.upper_price = new_upper
        self.grid_spacing = (self.upper_price - self.lower_price) / (self.num_grids - 1) if self.num_grids > 1 else 0
        self.investment_per_grid = self.total_investment_usd / self.num_grids
        self.grid_levels = [
            GridLevel(price=self.lower_price + i * self.grid_spacing)
            for i in range(self.num_grids)
        ]

        # Restore holdings for levels close to old held positions
        tolerance = max(self.grid_spacing * 0.1, 0.01)
        mapped: set[float] = set()
        for new_level in self.grid_levels:
            for old_price, (holding, amount) in old_holdings.items():
                if old_price not in mapped and abs(new_level.price - old_price) <= tolerance:
                    new_level.holding = holding
                    new_level.crypto_amount = amount
                    mapped.add(old_price)
                    break

        # Liquidate old positions that couldn't map to any new level
        for old_price, (holding, amount) in old_holdings.items():
            if old_price not in mapped and amount > 0:
                liquidation_signals.append(Signal(
                    action="sell",
                    pair=self.pair,
                    price=candle.close,
                    order_type="market",
                    amount_crypto=amount,
                    reason=f"adaptive liquidation: unmapped level {old_price:.2f}",
                ))

        return liquidation_signals

    def on_candle(self, candle: Candle) -> list[Signal]:
        if self.paused:
            return []

        signals: list[Signal] = []

        # Adaptive range recalculation (before grid logic)
        signals.extend(self._maybe_recalc_range(candle))

        # Update trend / range-only filter
        self._update_trend_filter(candle.close)

        ref_price = self.prev_price if self.prev_price is not None else candle.open

        # Stop-loss check (always active, bypasses trade cap)
        stop_price = self.lower_price * (1 - self.stop_loss_pct)
        if candle.low < stop_price:
            signals.extend(self._liquidate_all(candle, reason="stop-loss"))
            self.paused = True
            self.prev_price = candle.close
            return signals

        # Take-profit check (always active, bypasses trade cap)
        tp_price = self.upper_price * (1 + self.take_profit_pct)
        if candle.high > tp_price:
            signals.extend(self._liquidate_all(candle, reason="take-profit"))
            self.paused = True
            self.prev_price = candle.close
            return signals

        # Daily trade cap check
        ts = candle.timestamp.timestamp()
        if self.max_trades_per_day > 0:
            cutoff = ts - 86400  # 24 hours
            while self._trade_timestamps and self._trade_timestamps[0] < cutoff:
                self._trade_timestamps.popleft()
            self._trade_cap_paused = len(self._trade_timestamps) >= self.max_trades_per_day

        # Buy detection: downward crossings
        if not self.buys_blocked and not self.grid_paused_divergence and not self._trade_cap_paused:
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
                        reason=f"grid buy at {level.price:.2f}",
                    ))
                    level.holding = True
                    level.crypto_amount = crypto_amount

        # Sell detection: upward crossings
        # During range-only divergence or trade cap, grid sells are paused
        # (stop-loss, take-profit, and adaptive liquidations still fire above)
        if not self.grid_paused_divergence and not self._trade_cap_paused:
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
                        reason=f"grid sell at {sell_price:.2f}",
                    ))
                    level.holding = False
                    level.crypto_amount = 0.0

        # Record trade timestamps for cap tracking and update flag
        if self.max_trades_per_day > 0:
            new_trades = len([s for s in signals if "grid" in s.reason])
            for _ in range(new_trades):
                self._trade_timestamps.append(ts)
            self._trade_cap_paused = len(self._trade_timestamps) >= self.max_trades_per_day

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
        state = {
            "num_grids": self.num_grids,
            "grid_levels": [
                {"price": gl.price, "holding": gl.holding, "crypto_amount": gl.crypto_amount}
                for gl in self.grid_levels
            ],
            "paused": self.paused,
            "prev_price": self.prev_price,
        }
        if self.use_trend_filter or self.range_only_filter:
            state["buys_blocked"] = self.buys_blocked
            state["ema_fast"] = self.ema_fast.value if self.ema_fast else None
            state["ema_slow"] = self.ema_slow.value if self.ema_slow else None
        if self.range_only_filter:
            state["range_only_filter"] = True
            state["grid_paused_divergence"] = self.grid_paused_divergence
            state["ema_convergence_pct"] = self.ema_convergence_pct
            if self.ema_fast and self.ema_slow and self.ema_fast.value and self.ema_slow.value:
                state["current_divergence_pct"] = abs(self.ema_fast.value - self.ema_slow.value) / self.ema_slow.value * 100
        if self.adaptive_range:
            state["adaptive_range"] = True
            state["current_lower"] = self.lower_price
            state["current_upper"] = self.upper_price
            state["candles_since_recalc"] = self._candles_since_recalc
            state["history_size"] = len(self._candle_history)
            state["min_spacing_pct"] = self.min_spacing_pct
        if self.max_trades_per_day > 0:
            state["max_trades_per_day"] = self.max_trades_per_day
            state["trades_in_window"] = len(self._trade_timestamps)
            state["trade_cap_paused"] = self._trade_cap_paused
        return state
