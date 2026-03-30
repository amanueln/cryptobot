import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.trend import MACD

from exchange.models import Candle, Signal
from strategies.base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def __init__(self):
        self.pair: str = ""
        self.rsi_period: int = 14
        self.rsi_oversold: float = 30
        self.rsi_overbought: float = 70
        self.bb_period: int = 20
        self.bb_std_dev: float = 2.0
        self.macd_fast: int = 12
        self.macd_slow: int = 26
        self.macd_signal: int = 9
        self.require_macd_confirm: bool = True
        self.risk_reward_ratio: float = 2.0
        self.atr_period: int = 14
        self.position_size_usd: float = 500

        # Candle history for indicator calculation
        self._closes: list[float] = []
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._candles_processed: int = 0

        # Minimum candles needed before indicators are valid
        self._min_candles: int = 0

        # Latest indicator values
        self._last_rsi: float | None = None
        self._last_bb_upper: float | None = None
        self._last_bb_lower: float | None = None
        self._last_bb_mid: float | None = None
        self._last_macd_hist: float | None = None
        self._prev_macd_hist: float | None = None
        self._last_atr: float | None = None

        # Position tracking (one position at a time)
        self._position: dict | None = None

    def configure(self, config: dict) -> None:
        self.pair = config["pair"]
        self.rsi_period = int(config.get("rsi_period", 14))
        self.rsi_oversold = float(config.get("rsi_oversold", 30))
        self.rsi_overbought = float(config.get("rsi_overbought", 70))
        self.bb_period = int(config.get("bb_period", 20))
        self.bb_std_dev = float(config.get("bb_std_dev", 2.0))
        self.macd_fast = int(config.get("macd_fast", 12))
        self.macd_slow = int(config.get("macd_slow", 26))
        self.macd_signal = int(config.get("macd_signal", 9))
        self.require_macd_confirm = bool(config.get("require_macd_confirm", True))
        self.risk_reward_ratio = float(config.get("risk_reward_ratio", 2.0))
        self.atr_period = int(config.get("atr_period", 14))
        self.position_size_usd = float(config.get("position_size_usd", 500))

        # Need enough candles for the slowest indicator
        self._min_candles = self.macd_slow + self.macd_signal

    def _update_indicators(self) -> None:
        # Use a rolling window to avoid recalculating over entire history
        # Need enough data for the slowest indicator + some buffer
        window = max(self.macd_slow + self.macd_signal, self.bb_period, self.rsi_period, self.atr_period) + 50
        close = pd.Series(self._closes[-window:])
        high = pd.Series(self._highs[-window:])
        low = pd.Series(self._lows[-window:])

        # RSI
        rsi = RSIIndicator(close=close, window=self.rsi_period)
        rsi_val = rsi.rsi().iloc[-1]
        self._last_rsi = None if pd.isna(rsi_val) else float(rsi_val)

        # Bollinger Bands
        bb = BollingerBands(close=close, window=self.bb_period, window_dev=self.bb_std_dev)
        bb_u = bb.bollinger_hband().iloc[-1]
        bb_l = bb.bollinger_lband().iloc[-1]
        bb_m = bb.bollinger_mavg().iloc[-1]
        self._last_bb_upper = None if pd.isna(bb_u) else float(bb_u)
        self._last_bb_lower = None if pd.isna(bb_l) else float(bb_l)
        self._last_bb_mid = None if pd.isna(bb_m) else float(bb_m)

        # MACD
        macd = MACD(close=close, window_slow=self.macd_slow, window_fast=self.macd_fast, window_sign=self.macd_signal)
        hist = macd.macd_diff().iloc[-1]
        self._prev_macd_hist = self._last_macd_hist
        self._last_macd_hist = None if pd.isna(hist) else float(hist)

        # ATR
        atr = AverageTrueRange(high=high, low=low, close=close, window=self.atr_period)
        atr_val = atr.average_true_range().iloc[-1]
        self._last_atr = None if pd.isna(atr_val) else float(atr_val)

    def _check_buy(self, candle: Candle) -> Signal | None:
        if self._position is not None:
            return None

        if (
            self._last_rsi is None
            or self._last_bb_lower is None
            or self._last_atr is None
        ):
            return None

        rsi_ok = self._last_rsi < self.rsi_oversold
        # Allow 1% tolerance above lower BB (band shifts during sharp moves)
        bb_ok = candle.close <= self._last_bb_lower * 1.01

        macd_ok = True
        if self.require_macd_confirm:
            if self._last_macd_hist is None or self._prev_macd_hist is None:
                macd_ok = False
            else:
                # Histogram turning positive: current > previous (improving)
                macd_ok = self._last_macd_hist > self._prev_macd_hist

        if not (rsi_ok and bb_ok and macd_ok):
            return None

        # Calculate stop-loss and take-profit
        stop_loss = candle.close - self._last_atr
        risk = candle.close - stop_loss  # = 1 ATR
        take_profit = candle.close + risk * self.risk_reward_ratio

        amount = self.position_size_usd / candle.close if candle.close > 0 else 0
        if amount <= 0:
            return None

        self._position = {
            "entry_price": candle.close,
            "amount": amount,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }

        return Signal(
            action="buy",
            pair=self.pair,
            price=candle.close,
            order_type="market",
            amount_usd=self.position_size_usd,
            reason=f"mean reversion buy: RSI={self._last_rsi:.1f}, close<BB_lower",
        )

    def _check_sell(self, candle: Candle) -> Signal | None:
        if self._position is None:
            return None

        pos = self._position
        reason = ""

        # Stop-loss: candle low pierces stop level
        if candle.low <= pos["stop_loss"]:
            reason = "stop-loss"
        # Take-profit: candle high reaches target
        elif candle.high >= pos["take_profit"]:
            reason = "take-profit"
        # RSI overbought
        elif self._last_rsi is not None and self._last_rsi > self.rsi_overbought:
            reason = f"RSI overbought ({self._last_rsi:.1f})"
        # Price at or above upper Bollinger Band
        elif self._last_bb_upper is not None and candle.close >= self._last_bb_upper:
            reason = "price >= BB upper"

        if not reason:
            return None

        signal = Signal(
            action="sell",
            pair=self.pair,
            price=candle.close,
            order_type="market",
            amount_crypto=pos["amount"],
            reason=reason,
        )
        self._position = None
        return signal

    def on_candle(self, candle: Candle) -> list[Signal]:
        self._closes.append(candle.close)
        self._highs.append(candle.high)
        self._lows.append(candle.low)
        self._candles_processed += 1

        if self._candles_processed < self._min_candles:
            return []

        self._update_indicators()

        signals: list[Signal] = []

        # Check sell first (exit before entry)
        sell = self._check_sell(candle)
        if sell:
            signals.append(sell)

        # Check buy
        buy = self._check_buy(candle)
        if buy:
            signals.append(buy)

        return signals

    def get_state(self) -> dict:
        return {
            "rsi": self._last_rsi,
            "bb_upper": self._last_bb_upper,
            "bb_lower": self._last_bb_lower,
            "bb_mid": self._last_bb_mid,
            "macd_histogram": self._last_macd_hist,
            "atr": self._last_atr,
            "position": self._position,
            "candles_processed": self._candles_processed,
        }
