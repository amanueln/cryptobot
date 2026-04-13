from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from exchange.models import Candle, Signal
from strategies.base_strategy import BaseStrategy


@dataclass
class GridLevel:
    price: float
    holding: bool = False
    crypto_amount: float = 0.0
    entry_price: float = 0.0  # actual fill price when bought
    active: bool = True       # False if filtered out by profit check


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
        self.original_investment_usd: float = 0  # for compounding limits
        self.stop_loss_pct: float = 0
        self.take_profit_pct: float = 0
        self.grid_levels: list[GridLevel] = []
        self.grid_spacing: float = 0
        self.grid_spacing_pct: float = 0  # percentage between levels
        self.investment_per_grid: float = 0
        self.prev_price: float | None = None
        self._last_price: float = 0.0
        self.paused: bool = False

        # Grid mode: "geometric" or "arithmetic"
        self.grid_mode: str = "geometric"
        self.auto_grid_mode: bool = True

        # Trailing grid
        self.trailing_enabled: bool = True
        self.trailing_buffer_pct: float = 0.02

        # Profit filter
        self.fee_pct: float = 0.40           # per-side fee %
        self.slippage_pct: float = 0.10      # additional slippage %
        self.min_profit_multiplier: float = 1.5  # min profit = fee * this
        self.active_grid_count: int = 0      # levels that passed profit filter
        self.filtered_count: int = 0         # levels skipped

        # Position limit
        self.max_position_pct: float = 0.85  # max 85% of allocation in open buys
        self.position_limit_hit: bool = False

        # Compounding
        self.compound_enabled: bool = True
        self.compound_floor_pct: float = 0.50
        self.compound_cap_pct: float = 2.0

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
        self.min_spacing_pct: float = 0.02
        self._candle_history: deque[Candle] = deque()
        self._candles_since_recalc: int = 0
        self._recalc_interval_candles: int = 0

        # Daily trade cap
        self.max_trades_per_day: int = 0
        self._trade_timestamps: deque[float] = deque()
        self._trade_cap_paused: bool = False

        # ATR-based volatility adaptation
        self.atr_period: int = 14
        self.atr_spacing_multiplier: float = 2.0
        self._atr_values: deque[float] = deque(maxlen=14)
        self._atr_current: float = 0.0
        self._atr_mean: float = 0.0
        self._atr_history: deque[float] = deque(maxlen=336)
        self._prev_close_for_atr: float | None = None

        # Volatility-based spacing adjustment (ML layer)
        self._vol_spacing_multiplier: float = 1.0
        self._vol_ml_override: bool = False
        self._vol_regime: str = "unknown"
        self._learned_spacing_multiplier: float = 1.0

        # Indicator snapshot
        self._last_adx: float = 0.0
        self._last_rsi: float = 0.0

        # Event logging
        self._prev_atr_mult: float = 1.0
        self._trade_logger = None

    def configure(self, config: dict) -> None:
        self.pair = config["pair"]
        self.upper_price = float(config["upper_price"])
        self.lower_price = float(config["lower_price"])
        self.num_grids = int(config["num_grids"])
        self.total_investment_usd = float(config["total_investment_usd"])
        self.original_investment_usd = self.total_investment_usd
        self.stop_loss_pct = float(config["stop_loss_pct"])
        self.take_profit_pct = float(config["take_profit_pct"])

        # Grid mode (Improvement 1 + 4)
        self.grid_mode = config.get("grid_mode", "geometric")
        self.auto_grid_mode = bool(config.get("auto_grid_mode", True))

        # Trailing (Improvement 2)
        self.trailing_enabled = bool(config.get("trailing_enabled", True))
        self.trailing_buffer_pct = float(config.get("trailing_buffer_pct", 0.02))

        # Profit filter (Improvement 3)
        self.fee_pct = float(config.get("fee_pct", 0.40))
        self.slippage_pct = float(config.get("slippage_pct", 0.10))
        self.min_profit_multiplier = float(config.get("min_profit_multiplier", 1.5))

        # Position limit (Improvement 5)
        self.max_position_pct = float(config.get("max_position_pct", 0.60))

        # Compounding (Improvement 6)
        self.compound_enabled = bool(config.get("compound_enabled", True))
        self.compound_floor_pct = float(config.get("compound_floor_pct", 0.50))
        self.compound_cap_pct = float(config.get("compound_cap_pct", 2.0))

        # Calculate grid levels
        self._calculate_grid_levels()
        self._filter_unprofitable_levels()
        self.investment_per_grid = self.total_investment_usd / max(self.active_grid_count, 1)

        # Trend filter config
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

        # ATR spacing config
        self.atr_period = int(config.get("atr_period", 14))
        self.atr_spacing_multiplier = float(config.get("atr_spacing_multiplier", 2.0))
        self._atr_values = deque(maxlen=self.atr_period)
        self._atr_history = deque(maxlen=max(336, int(self.range_lookback_days * 24) if self.adaptive_range else 336))

    # ------------------------------------------------------------------
    # Grid level calculation (Improvement 1: Geometric)
    # ------------------------------------------------------------------

    def _calculate_grid_levels(self):
        """Calculate grid levels using geometric or arithmetic spacing."""
        if self.lower_price <= 0 or self.upper_price <= self.lower_price or self.num_grids < 2:
            self.grid_spacing = 0
            self.grid_spacing_pct = 0
            self.grid_levels = []
            return

        if self.grid_mode == "geometric":
            # Equal percentage steps: each level = lower * ratio^i
            ratio = (self.upper_price / self.lower_price) ** (1.0 / (self.num_grids - 1))
            self.grid_spacing_pct = (ratio - 1.0) * 100
            prices = [self.lower_price * (ratio ** i) for i in range(self.num_grids)]
            # grid_spacing stored as average dollar spacing for compatibility
            self.grid_spacing = (self.upper_price - self.lower_price) / (self.num_grids - 1)
        else:
            # Equal dollar steps (original behavior)
            self.grid_spacing = (self.upper_price - self.lower_price) / (self.num_grids - 1)
            self.grid_spacing_pct = (self.grid_spacing / self.lower_price) * 100 if self.lower_price > 0 else 0
            prices = [self.lower_price + i * self.grid_spacing for i in range(self.num_grids)]

        self.grid_levels = [GridLevel(price=p) for p in prices]
        self.active_grid_count = len(self.grid_levels)
        self.filtered_count = 0

    def _filter_unprofitable_levels(self):
        """Improvement 3: Remove grid levels where profit < fee threshold."""
        if not self.grid_levels or len(self.grid_levels) < 2:
            return

        round_trip_fee_pct = (self.fee_pct + self.slippage_pct) * 2
        min_spacing_pct = round_trip_fee_pct * self.min_profit_multiplier

        # Mark levels that are too close to the previous active level
        prev_active_price = self.grid_levels[0].price
        self.grid_levels[0].active = True

        for level in self.grid_levels[1:]:
            spacing_pct = (level.price - prev_active_price) / prev_active_price * 100
            if spacing_pct >= min_spacing_pct:
                level.active = True
                prev_active_price = level.price
            else:
                level.active = False

        self.active_grid_count = sum(1 for l in self.grid_levels if l.active)
        self.filtered_count = len(self.grid_levels) - self.active_grid_count

    def _get_sell_price(self, level: GridLevel) -> float:
        """Get the sell target for a filled level — next active level above."""
        if self.grid_mode == "geometric":
            # Geometric: sell at entry * (1 + spacing_pct/100)
            return level.entry_price * (1 + self.grid_spacing_pct / 100) if level.entry_price > 0 else level.price * (1 + self.grid_spacing_pct / 100)
        else:
            return level.price + self.grid_spacing

    # ------------------------------------------------------------------
    # Trailing grid (Improvement 2)
    # ------------------------------------------------------------------

    def _check_trailing(self, candle: Candle) -> bool:
        """Shift grid up/down if price exits the range."""
        if not self.trailing_enabled:
            return False

        current_price = candle.close
        min_overshoot = self.grid_spacing_pct / 100 / 2 if self.grid_spacing_pct > 0 else 0.01

        if current_price > self.upper_price:
            overshoot_pct = (current_price - self.upper_price) / self.upper_price
            if overshoot_pct > min_overshoot:
                return self._trail_grid(candle, direction="up")

        elif current_price < self.lower_price:
            overshoot_pct = (self.lower_price - current_price) / self.lower_price
            if overshoot_pct > min_overshoot:
                return self._trail_grid(candle, direction="down")

        return False

    def _trail_grid(self, candle: Candle, direction: str) -> bool:
        """Shift the entire grid, preserving open positions."""
        old_lower = self.lower_price
        old_upper = self.upper_price
        current_price = candle.close

        # Maintain same range width in percentage terms
        if self.grid_mode == "geometric":
            range_ratio = old_upper / old_lower if old_lower > 0 else 2.0
        else:
            range_pct = (old_upper - old_lower) / old_lower if old_lower > 0 else 0.5

        if direction == "up":
            self.upper_price = current_price * (1 + self.trailing_buffer_pct)
            if self.grid_mode == "geometric":
                self.lower_price = self.upper_price / range_ratio
            else:
                self.lower_price = self.upper_price / (1 + range_pct)
        else:
            self.lower_price = current_price * (1 - self.trailing_buffer_pct)
            if self.grid_mode == "geometric":
                self.upper_price = self.lower_price * range_ratio
            else:
                self.upper_price = self.lower_price * (1 + range_pct)

        # Snapshot holdings before rebuilding
        old_holdings: list[tuple[float, float, float]] = []  # (entry_price, amount, old_level_price)
        for level in self.grid_levels:
            if level.holding and level.crypto_amount > 0:
                old_holdings.append((level.entry_price, level.crypto_amount, level.price))

        # Rebuild grid
        self._calculate_grid_levels()
        self._filter_unprofitable_levels()
        self.investment_per_grid = self.total_investment_usd / max(self.active_grid_count, 1)

        # Remap holdings to nearest new levels
        for entry_price, amount, old_price in old_holdings:
            # Find nearest active new level
            best = min(
                (l for l in self.grid_levels if l.active and not l.holding),
                key=lambda l: abs(l.price - old_price),
                default=None,
            )
            if best:
                best.holding = True
                best.crypto_amount = amount
                best.entry_price = entry_price

        # Log trail event
        if hasattr(self, '_trade_logger') and self._trade_logger:
            name = self.pair.replace("-USD", "")
            self._trade_logger.log_event(
                "trail",
                f"{name} grid trailed {direction} — price {'broke above' if direction == 'up' else 'dropped below'} range",
                f"Old: ${old_lower:.6g}-${old_upper:.6g} → New: ${self.lower_price:.6g}-${self.upper_price:.6g}",
                pair=self.pair,
            )

        return True

    # ------------------------------------------------------------------
    # Position limit (Improvement 5)
    # ------------------------------------------------------------------

    def _check_position_limit(self) -> bool:
        """Returns True if we can still buy (within position limit)."""
        total_invested = sum(
            level.entry_price * level.crypto_amount
            for level in self.grid_levels
            if level.holding and level.crypto_amount > 0
        )
        max_invested = self.total_investment_usd * self.max_position_pct
        self.position_limit_hit = total_invested >= max_invested
        return not self.position_limit_hit

    def _get_buy_size(self) -> float:
        """Calculate buy size, respecting position limit."""
        total_invested = sum(
            level.entry_price * level.crypto_amount
            for level in self.grid_levels
            if level.holding and level.crypto_amount > 0
        )
        max_invested = self.total_investment_usd * self.max_position_pct
        remaining = max_invested - total_invested
        if remaining <= 0:
            return 0
        return min(self.investment_per_grid, remaining)

    # ------------------------------------------------------------------
    # Compounding (Improvement 6)
    # ------------------------------------------------------------------

    def apply_cycle_profit(self, net_profit: float):
        """Reinvest cycle profit into allocation (or absorb loss)."""
        if not self.compound_enabled:
            return

        old_alloc = self.total_investment_usd
        new_alloc = old_alloc + net_profit

        # Clamp to floor/cap
        floor = self.original_investment_usd * self.compound_floor_pct
        cap = self.original_investment_usd * self.compound_cap_pct
        new_alloc = max(floor, min(cap, new_alloc))

        self.total_investment_usd = new_alloc
        self.investment_per_grid = new_alloc / max(self.active_grid_count, 1)

    # ------------------------------------------------------------------
    # Regime-driven mode (Improvement 4)
    # ------------------------------------------------------------------

    def _select_grid_mode(self, regime: str, atr_ratio: float) -> str:
        """Auto-select grid mode based on market conditions."""
        if not self.auto_grid_mode:
            return self.grid_mode

        if regime.lower() in ("ranging", "squeeze") and atr_ratio < 0.8:
            return "arithmetic"
        return "geometric"

    # ------------------------------------------------------------------
    # ATR and volatility
    # ------------------------------------------------------------------

    def _update_atr(self, candle: Candle) -> None:
        if self._prev_close_for_atr is not None:
            tr = max(
                candle.high - candle.low,
                abs(candle.high - self._prev_close_for_atr),
                abs(candle.low - self._prev_close_for_atr),
            )
            self._atr_values.append(tr)
            if len(self._atr_values) >= self.atr_period:
                self._atr_current = sum(self._atr_values) / len(self._atr_values)
                self._atr_history.append(self._atr_current)
                if len(self._atr_history) >= self.atr_period:
                    self._atr_mean = sum(self._atr_history) / len(self._atr_history)
        self._prev_close_for_atr = candle.close

    def _compute_atr_spacing_multiplier(self) -> float:
        if self._atr_current <= 0 or self._atr_mean <= 0:
            return 1.0
        ratio = self._atr_current / self._atr_mean
        if 0.95 <= ratio <= 1.05:
            return 1.0
        return max(0.5, min(2.0, ratio))

    def apply_volatility_adjustment(self, spacing_multiplier: float, vol_regime: str,
                                       recommended_grids: int = 0) -> None:
        self._vol_spacing_multiplier = max(0.5, min(2.0, spacing_multiplier))
        self._vol_ml_override = True
        self._vol_regime = vol_regime

    def apply_learned_spacing(self, multiplier: float) -> None:
        self._learned_spacing_multiplier = max(0.7, min(1.3, multiplier))

    # ------------------------------------------------------------------
    # Trend / EMA filters
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Adaptive range recalculation
    # ------------------------------------------------------------------

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

        # Auto-select grid mode based on regime (Improvement 4)
        atr_ratio = self._atr_current / self._atr_mean if self._atr_mean > 0 else 1.0
        regime = getattr(self, '_vol_regime', 'unknown')
        new_mode = self._select_grid_mode(regime, atr_ratio)
        mode_changed = new_mode != self.grid_mode
        if mode_changed:
            old_mode = self.grid_mode
            self.grid_mode = new_mode
            if hasattr(self, '_trade_logger') and self._trade_logger:
                name = self.pair.replace("-USD", "")
                self._trade_logger.log_event(
                    "mode_switch",
                    f"{name} switched to {new_mode} spacing — market is {regime}",
                    f"Was {old_mode}, now {new_mode} (ATR ratio: {atr_ratio:.2f})",
                    pair=self.pair,
                )

        # Volatility spacing adjustment
        if self._vol_ml_override:
            spacing_mult = self._vol_spacing_multiplier
        else:
            spacing_mult = self._compute_atr_spacing_multiplier()
            self._vol_spacing_multiplier = spacing_mult

        if hasattr(self, '_trade_logger') and self._trade_logger:
            old_mult = getattr(self, '_prev_atr_mult', 1.0)
            new_mult = self._vol_spacing_multiplier
            if abs(new_mult - old_mult) > 0.05:
                direction = "widened" if new_mult > old_mult else "narrowed"
                self._trade_logger.log_event(
                    "atr_adjust",
                    f"{self.pair.replace('-USD', '')} spacing {direction} to {new_mult:.1f}x",
                    f"ATR moved from ${self._atr_mean:.6f} avg to ${self._atr_current:.6f} current",
                    pair=self.pair,
                )
                self._prev_atr_mult = new_mult

        # Apply feedback-loop learned spacing preference
        learned_mult = getattr(self, '_learned_spacing_multiplier', 1.0)
        combined_mult = spacing_mult * learned_mult

        if combined_mult != 1.0:
            mid = (new_lower + new_upper) / 2
            half_range = (new_upper - new_lower) / 2
            adjusted_half = half_range * combined_mult
            new_lower = mid - adjusted_half
            new_upper = mid + adjusted_half

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

        if not mode_changed and new_lower == self.lower_price and new_upper == self.upper_price:
            return []

        # Handle positions outside new range
        liquidation_signals: list[Signal] = []
        for level in self.grid_levels:
            if level.holding and level.crypto_amount > 0:
                if level.price < new_lower or level.price > new_upper:
                    entry = level.entry_price if level.entry_price > 0 else level.price
                    loss_pct = (candle.close - entry) / entry if entry > 0 else 0

                    if loss_pct < -0.10:
                        liquidation_signals.append(Signal(
                            action="sell",
                            pair=self.pair,
                            price=candle.close,
                            order_type="market",
                            amount_crypto=level.crypto_amount,
                            reason=f"adaptive stop-loss: {loss_pct*100:.1f}% below entry {entry:.4f}",
                            regime=getattr(self, '_vol_regime', ''),
                            adx=getattr(self, '_last_adx', 0.0),
                            rsi=getattr(self, '_last_rsi', 0.0),
                            atr_multiplier=getattr(self, '_vol_spacing_multiplier', 1.0),
                        ))
                        level.holding = False
                        level.crypto_amount = 0.0
                    else:
                        sell_target = entry
                        # Keep holding — will remap below

        # Snapshot in-range holdings
        old_holdings: dict[float, tuple[bool, float, float]] = {}
        for level in self.grid_levels:
            if level.holding:
                old_holdings[level.price] = (True, level.crypto_amount, level.entry_price)

        # Rebuild grid with new boundaries
        self.lower_price = new_lower
        self.upper_price = new_upper
        self._calculate_grid_levels()
        self._filter_unprofitable_levels()
        self.investment_per_grid = self.total_investment_usd / max(self.active_grid_count, 1)

        # Restore holdings for levels close to old held positions
        tolerance = max(self.grid_spacing * 0.15, 0.001)
        mapped: set[float] = set()
        for new_level in self.grid_levels:
            for old_price, (holding, amount, entry) in old_holdings.items():
                if old_price not in mapped and abs(new_level.price - old_price) <= tolerance:
                    new_level.holding = holding
                    new_level.crypto_amount = amount
                    new_level.entry_price = entry
                    mapped.add(old_price)
                    break

        # Unmapped positions: hold with limit sell or park on nearest level
        for old_price, (holding, amount, entry) in old_holdings.items():
            if old_price not in mapped and amount > 0:
                entry = entry if entry > 0 else old_price
                loss_pct = (candle.close - entry) / entry if entry > 0 else 0

                if loss_pct < -0.10:
                    liquidation_signals.append(Signal(
                        action="sell",
                        pair=self.pair,
                        price=candle.close,
                        order_type="market",
                        amount_crypto=amount,
                        reason=f"adaptive stop-loss: unmapped {old_price:.4f}, {loss_pct*100:.1f}% below entry",
                        regime=getattr(self, '_vol_regime', ''),
                        adx=getattr(self, '_last_adx', 0.0),
                        rsi=getattr(self, '_last_rsi', 0.0),
                        atr_multiplier=getattr(self, '_vol_spacing_multiplier', 1.0),
                    ))
                else:
                    best_level = min(
                        (l for l in self.grid_levels if not l.holding),
                        key=lambda gl: abs(gl.price - old_price),
                        default=None,
                    )
                    if best_level:
                        best_level.holding = True
                        best_level.crypto_amount = amount
                        best_level.entry_price = entry

        return liquidation_signals

    # ------------------------------------------------------------------
    # Main candle processing
    # ------------------------------------------------------------------

    def on_candle(self, candle: Candle, warmup: bool = False) -> list[Signal]:
        if self.paused:
            return []

        # ATR updates on every candle
        self._update_atr(candle)
        self._last_price = candle.close

        # During warmup: update indicators only
        if warmup:
            if self.adaptive_range:
                self._candle_history.append(candle)
                self._candles_since_recalc += 1
            self._update_trend_filter(candle.close)
            self.prev_price = candle.close
            return []

        signals: list[Signal] = []

        # Trailing grid check (Improvement 2) — before recalc
        self._check_trailing(candle)

        # Adaptive range recalculation
        signals.extend(self._maybe_recalc_range(candle))

        # Update trend / range-only filter
        self._update_trend_filter(candle.close)

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

        # Daily trade cap check
        ts = candle.timestamp.timestamp()
        if self.max_trades_per_day > 0:
            cutoff = ts - 86400
            while self._trade_timestamps and self._trade_timestamps[0] < cutoff:
                self._trade_timestamps.popleft()
            self._trade_cap_paused = len(self._trade_timestamps) >= self.max_trades_per_day

        # Buy detection: downward crossings
        can_buy = (
            not self.buys_blocked
            and not self.grid_paused_divergence
            and not self._trade_cap_paused
            and self._check_position_limit()  # Improvement 5
        )
        if can_buy:
            buy_size = self._get_buy_size()
            for level in self.grid_levels:
                if not level.active:
                    continue  # Improvement 3: skip filtered levels
                if not level.holding and candle.low <= level.price <= ref_price:
                    if buy_size <= 0:
                        break  # position limit reached
                    crypto_amount = buy_size / level.price if level.price > 0 else 0
                    signals.append(Signal(
                        action="buy",
                        pair=self.pair,
                        price=candle.close,
                        order_type="limit",
                        amount_usd=buy_size,
                        limit_price=level.price,
                        reason=f"grid buy at {level.price:.6g}",
                        regime=getattr(self, '_vol_regime', ''),
                        adx=getattr(self, '_last_adx', 0.0),
                        rsi=getattr(self, '_last_rsi', 0.0),
                        atr_multiplier=getattr(self, '_vol_spacing_multiplier', 1.0),
                    ))
                    level.holding = True
                    level.crypto_amount = crypto_amount
                    level.entry_price = level.price
                    # Recalculate remaining buy capacity
                    buy_size = self._get_buy_size()

        # Sell detection: upward crossings
        if not self.grid_paused_divergence and not self._trade_cap_paused:
            for level in self.grid_levels:
                if not level.holding or level.crypto_amount <= 0:
                    continue
                sell_price = self._get_sell_price(level)
                if candle.high >= sell_price and ref_price <= sell_price:
                    signals.append(Signal(
                        action="sell",
                        pair=self.pair,
                        price=candle.close,
                        order_type="limit",
                        amount_crypto=level.crypto_amount,
                        limit_price=sell_price,
                        reason=f"grid sell at {sell_price:.6g}",
                        regime=getattr(self, '_vol_regime', ''),
                        adx=getattr(self, '_last_adx', 0.0),
                        rsi=getattr(self, '_last_rsi', 0.0),
                        atr_multiplier=getattr(self, '_vol_spacing_multiplier', 1.0),
                    ))
                    level.holding = False
                    level.crypto_amount = 0.0

        # Record trade timestamps for cap tracking
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
                    regime=getattr(self, '_vol_regime', ''),
                    adx=getattr(self, '_last_adx', 0.0),
                    rsi=getattr(self, '_last_rsi', 0.0),
                    atr_multiplier=getattr(self, '_vol_spacing_multiplier', 1.0),
                ))
                level.holding = False
                level.crypto_amount = 0.0
        return signals

    def has_open_positions(self) -> bool:
        return any(level.holding for level in self.grid_levels)

    def get_state(self) -> dict:
        state = {
            "num_grids": self.num_grids,
            "grid_mode": self.grid_mode,
            "grid_spacing_pct": round(self.grid_spacing_pct, 2),
            "active_grid_count": self.active_grid_count,
            "filtered_count": self.filtered_count,
            "grid_levels": [
                {"price": gl.price, "holding": gl.holding, "crypto_amount": gl.crypto_amount, "active": gl.active}
                for gl in self.grid_levels
            ],
            "paused": self.paused,
            "prev_price": self.prev_price,
            "position_limit_hit": self.position_limit_hit,
            "max_position_pct": self.max_position_pct,
            "total_investment_usd": round(self.total_investment_usd, 2),
            "original_investment_usd": round(self.original_investment_usd, 2),
            "compound_enabled": self.compound_enabled,
            "trailing_enabled": self.trailing_enabled,
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
        state["atr_current"] = round(self._atr_current, 8)
        state["atr_mean"] = round(self._atr_mean, 8)
        state["atr_spacing_multiplier"] = self.atr_spacing_multiplier
        state["vol_spacing_multiplier"] = self._vol_spacing_multiplier
        state["vol_ml_override"] = self._vol_ml_override
        state["vol_regime"] = self._vol_regime
        return state
