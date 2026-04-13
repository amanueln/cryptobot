from __future__ import annotations

"""Market Regime Detector — the brain layer above all strategies.

Reads ADX, Bollinger Band width, volume, OBV, RSI, and EMA relationship
to classify the current market as TRENDING_UP, TRENDING_DOWN, RANGING,
VOLATILE, or SQUEEZE. Strategies then adapt behavior to the regime.
"""

from enum import Enum

import pandas as pd
from ta.trend import ADXIndicator, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.momentum import RSIIndicator
from ta.volume import OnBalanceVolumeIndicator

from exchange.models import Candle


class MarketRegime(Enum):
    TRENDING_UP = "trending_up"       # ADX > 25, price > EMA50 > EMA200
    TRENDING_DOWN = "trending_down"   # ADX > 25, price < EMA50 < EMA200
    RANGING = "ranging"               # ADX < 20, EMAs converging, BB narrow
    VOLATILE = "volatile"             # BB wide, volume spike, ADX fluctuating
    SQUEEZE = "squeeze"               # BB extremely narrow, ADX dropping — breakout imminent
    UNKNOWN = "unknown"               # Not enough data


class RegimeDetector:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.adx_period: int = int(config.get("adx_period", 14))
        self.adx_trend_threshold: float = float(config.get("adx_trend_threshold", 25))
        self.adx_range_threshold: float = float(config.get("adx_range_threshold", 20))
        self.bb_period: int = int(config.get("bb_period", 20))
        self.bb_std_dev: float = float(config.get("bb_std_dev", 2))
        self.bb_squeeze_percentile: float = float(config.get("bb_squeeze_percentile", 10))
        self.volume_spike_threshold: float = float(config.get("volume_spike_threshold", 1.5))
        self.ema_fast_period: int = int(config.get("ema_fast", 50))
        self.ema_slow_period: int = int(config.get("ema_slow", 200))
        self.ema_convergence_pct: float = float(config.get("ema_convergence_pct", 3.0))
        self.atr_period: int = int(config.get("atr_period", 14))
        self.atr_multiplier: float = float(config.get("atr_multiplier", 2.0))
        self.risk_per_trade_pct: float = float(config.get("risk_per_trade_pct", 0.02))
        self.regime_lookback: int = int(config.get("regime_lookback_candles", 5))

        # Price history
        self._closes: list[float] = []
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._volumes: list[float] = []
        self._candles_processed: int = 0

        # Need enough data for the slowest indicator (EMA 200)
        self._min_candles: int = self.ema_slow_period + 10

        # Indicator state
        self._last_adx: float | None = None
        self._last_bb_width_pct: float | None = None
        self._last_bb_width_history: list[float] = []  # for percentile calc
        self._last_volume_ratio: float | None = None
        self._last_obv: float | None = None
        self._prev_obv: float | None = None
        self._last_rsi: float | None = None
        self._last_ema_fast: float | None = None
        self._last_ema_slow: float | None = None
        self._last_ema_divergence_pct: float | None = None
        self._last_atr: float | None = None

        # Regime history for confirmation
        self._regime_history: list[MarketRegime] = []
        self._current_regime: MarketRegime = MarketRegime.UNKNOWN

    def update(self, candle: Candle) -> MarketRegime:
        """Process a new candle and return the detected market regime."""
        self._closes.append(candle.close)
        self._highs.append(candle.high)
        self._lows.append(candle.low)
        self._volumes.append(candle.volume)
        self._candles_processed += 1

        if self._candles_processed < self._min_candles:
            return MarketRegime.RANGING  # Default to ranging during warmup

        self._update_indicators()
        raw_regime = self._classify_regime()

        # Regime confirmation: only change if raw regime is consistent
        self._regime_history.append(raw_regime)
        if len(self._regime_history) > self.regime_lookback:
            self._regime_history = self._regime_history[-self.regime_lookback:]

        self._current_regime = self._confirm_regime(raw_regime)
        return self._current_regime

    def _update_indicators(self) -> None:
        window = self.ema_slow_period + 50
        close = pd.Series(self._closes[-window:])
        high = pd.Series(self._highs[-window:])
        low = pd.Series(self._lows[-window:])
        volume = pd.Series(self._volumes[-window:])

        # ADX (trend strength)
        adx = ADXIndicator(high=high, low=low, close=close, window=self.adx_period)
        adx_val = adx.adx().iloc[-1]
        self._last_adx = None if pd.isna(adx_val) else float(adx_val)

        # Bollinger Band Width as % of price
        bb = BollingerBands(close=close, window=self.bb_period, window_dev=self.bb_std_dev)
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        mid = bb.bollinger_mavg().iloc[-1]
        if not pd.isna(bb_upper) and not pd.isna(bb_lower) and mid > 0:
            width_pct = ((bb_upper - bb_lower) / mid) * 100
            self._last_bb_width_pct = width_pct
            self._last_bb_width_history.append(width_pct)
            # Keep last 100 for percentile
            if len(self._last_bb_width_history) > 100:
                self._last_bb_width_history = self._last_bb_width_history[-100:]
        else:
            self._last_bb_width_pct = None

        # Volume ratio vs 20-period SMA
        if len(volume) >= 20:
            vol_sma = volume.iloc[-20:].mean()
            current_vol = volume.iloc[-1]
            self._last_volume_ratio = current_vol / vol_sma if vol_sma > 0 else 1.0
        else:
            self._last_volume_ratio = None

        # OBV
        obv = OnBalanceVolumeIndicator(close=close, volume=volume)
        obv_val = obv.on_balance_volume().iloc[-1]
        self._prev_obv = self._last_obv
        self._last_obv = None if pd.isna(obv_val) else float(obv_val)

        # RSI
        rsi = RSIIndicator(close=close, window=14)
        rsi_val = rsi.rsi().iloc[-1]
        self._last_rsi = None if pd.isna(rsi_val) else float(rsi_val)

        # EMA 50 / 200
        ema_fast = EMAIndicator(close=close, window=self.ema_fast_period)
        ema_slow = EMAIndicator(close=close, window=self.ema_slow_period)
        ef = ema_fast.ema_indicator().iloc[-1]
        es = ema_slow.ema_indicator().iloc[-1]
        self._last_ema_fast = None if pd.isna(ef) else float(ef)
        self._last_ema_slow = None if pd.isna(es) else float(es)

        if self._last_ema_fast is not None and self._last_ema_slow is not None and self._last_ema_slow > 0:
            self._last_ema_divergence_pct = abs(self._last_ema_fast - self._last_ema_slow) / self._last_ema_slow * 100
        else:
            self._last_ema_divergence_pct = None

        # ATR (for position sizing)
        atr = AverageTrueRange(high=high, low=low, close=close, window=self.atr_period)
        atr_val = atr.average_true_range().iloc[-1]
        self._last_atr = None if pd.isna(atr_val) else float(atr_val)

    def _classify_regime(self) -> MarketRegime:
        """Classify the current regime from indicator values."""
        if any(v is None for v in [
            self._last_adx, self._last_bb_width_pct,
            self._last_ema_fast, self._last_ema_slow,
        ]):
            return MarketRegime.UNKNOWN

        price = self._closes[-1]
        adx = self._last_adx
        bb_width = self._last_bb_width_pct
        ema_fast = self._last_ema_fast
        ema_slow = self._last_ema_slow
        ema_div = self._last_ema_divergence_pct or 0
        vol_ratio = self._last_volume_ratio or 1.0
        rsi = self._last_rsi or 50

        # SQUEEZE: BB extremely narrow + ADX dropping
        if self._is_squeeze(bb_width, adx):
            return MarketRegime.SQUEEZE

        # VOLATILE: BB wide + volume spike
        if self._is_volatile(bb_width, vol_ratio):
            return MarketRegime.VOLATILE

        # TRENDING: ADX > threshold + EMA alignment
        if adx > self.adx_trend_threshold:
            if price > ema_fast and ema_fast > ema_slow:
                return MarketRegime.TRENDING_UP
            elif price < ema_fast and ema_fast < ema_slow:
                return MarketRegime.TRENDING_DOWN
            # ADX strong but no clear EMA alignment — could be volatile
            if vol_ratio > self.volume_spike_threshold:
                return MarketRegime.VOLATILE

        # RANGING: ADX low + EMAs converging
        if adx < self.adx_range_threshold and ema_div < self.ema_convergence_pct:
            return MarketRegime.RANGING

        # Default: if ADX between thresholds, lean toward ranging or trending
        if ema_div < self.ema_convergence_pct:
            return MarketRegime.RANGING

        # Mild trend
        if price > ema_fast and ema_fast > ema_slow:
            return MarketRegime.TRENDING_UP
        elif price < ema_fast and ema_fast < ema_slow:
            return MarketRegime.TRENDING_DOWN

        return MarketRegime.RANGING

    def _is_squeeze(self, bb_width: float, adx: float) -> bool:
        """BB width in the bottom percentile of recent history + ADX declining."""
        if len(self._last_bb_width_history) < 20:
            return False
        sorted_widths = sorted(self._last_bb_width_history)
        threshold_idx = max(0, int(len(sorted_widths) * self.bb_squeeze_percentile / 100) - 1)
        squeeze_threshold = sorted_widths[threshold_idx]
        return bb_width <= squeeze_threshold and adx < self.adx_trend_threshold

    def _is_volatile(self, bb_width: float, vol_ratio: float) -> bool:
        """BB wide (above 75th percentile) + volume above threshold."""
        if len(self._last_bb_width_history) < 20:
            return False
        sorted_widths = sorted(self._last_bb_width_history)
        wide_idx = int(len(sorted_widths) * 0.75)
        wide_threshold = sorted_widths[min(wide_idx, len(sorted_widths) - 1)]
        return bb_width >= wide_threshold and vol_ratio >= self.volume_spike_threshold

    def _confirm_regime(self, raw: MarketRegime) -> MarketRegime:
        """Only change regime if it's been consistent over lookback period."""
        if len(self._regime_history) < self.regime_lookback:
            return raw

        recent = self._regime_history[-self.regime_lookback:]

        # If the majority of recent readings agree, confirm
        from collections import Counter
        counts = Counter(recent)
        most_common, count = counts.most_common(1)[0]

        # Need majority (more than half) to confirm a regime change
        if count > self.regime_lookback // 2:
            return most_common

        # No majority — keep previous regime
        return self._current_regime if self._current_regime != MarketRegime.UNKNOWN else raw

    def calc_position_size(self, account_balance: float, price: float) -> float:
        """ATR-based position sizing. High vol = smaller positions automatically."""
        if self._last_atr is None or self._last_atr <= 0 or price <= 0:
            return 0.0

        risk_usd = account_balance * self.risk_per_trade_pct
        risk_per_unit = self._last_atr * self.atr_multiplier
        units = risk_usd / risk_per_unit
        position_usd = units * price

        # Cap at 20% of account balance
        max_position = account_balance * 0.20
        return min(position_usd, max_position)

    def get_state(self) -> dict:
        return {
            "regime": self._current_regime.value,
            "adx": self._last_adx,
            "bb_width_pct": self._last_bb_width_pct,
            "volume_ratio": self._last_volume_ratio,
            "rsi": self._last_rsi,
            "ema_fast": self._last_ema_fast,
            "ema_slow": self._last_ema_slow,
            "ema_divergence_pct": self._last_ema_divergence_pct,
            "atr": self._last_atr,
            "candles_processed": self._candles_processed,
        }
