"""DCA with Safety Orders (Martingale-style) strategy.

All order sizes and levels are calculated dynamically from account balance,
pair volatility (ATR), and recent price action. Nothing is hardcoded.
"""

import math
from datetime import datetime

import pandas as pd
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator

from exchange.models import Candle, Signal
from strategies.base_strategy import BaseStrategy


class DCASafetyStrategy(BaseStrategy):
    name = "dca_safety"

    def __init__(self):
        self.pair: str = ""
        self.risk_per_deal_pct: float = 0.35
        self.volume_scale: float = 1.5
        self.step_scale: float = 1.5
        self.max_safety_orders: int = 5
        self.atr_period: int = 14
        self.bounce_lookback_days: int = 30
        self.min_take_profit_pct: float = 0.8
        self.max_take_profit_pct: float = 3.0
        self.max_portfolio_drawdown_pct: float = 0.10
        self.cooldown_candles: int = 5
        self.starting_balance: float = 3000.0

        # Price history for indicators
        self._closes: list[float] = []
        self._highs: list[float] = []
        self._lows: list[float] = []
        self._candles_processed: int = 0

        # Minimum candles before indicators are valid
        self._min_candles: int = 0

        # Indicator state
        self._last_atr: float | None = None
        self._last_rsi: float | None = None
        self._rsi_history: list[tuple[int, float, float]] = []  # (candle_idx, rsi, close)

        # Deal tracking
        self._deals: list[dict] = []
        self._completed_deals: list[dict] = []
        self._cooldown_remaining: int = 0
        self._available_balance: float = 0.0

    def configure(self, config: dict) -> None:
        self.pair = config["pair"]
        self.risk_per_deal_pct = float(config.get("risk_per_deal_pct", 0.35))
        self.volume_scale = float(config.get("volume_scale", 1.5))
        self.step_scale = float(config.get("step_scale", 1.5))
        self.max_safety_orders = int(config.get("max_safety_orders", 5))
        self.atr_period = int(config.get("atr_period", 14))
        self.bounce_lookback_days = int(config.get("bounce_lookback_days", 30))
        self.min_take_profit_pct = float(config.get("min_take_profit_pct", 0.8))
        self.max_take_profit_pct = float(config.get("max_take_profit_pct", 3.0))
        self.max_portfolio_drawdown_pct = float(config.get("max_portfolio_drawdown_pct", 0.10))
        self.cooldown_candles = int(config.get("cooldown_candles", 5))
        self.starting_balance = float(config.get("starting_balance", 3000))
        self._available_balance = self.starting_balance

        self._min_candles = max(self.atr_period + 5, 20)

    # --- Dynamic calculation methods (no hardcoded values) ---

    def _calc_base_order_usd(self, available_balance: float) -> float:
        """Base order = (balance * risk%) / (1 + sum of SO multipliers).

        This guarantees total deal exposure never exceeds risk allocation.
        """
        so_multiplier_sum = sum(self.volume_scale ** i for i in range(1, self.max_safety_orders + 1))
        return (available_balance * self.risk_per_deal_pct) / (1 + so_multiplier_sum)

    def _calc_safety_order_levels(self, entry_price: float, atr: float) -> list[float]:
        """Safety order levels based on ATR. Volatile coins get wider spacing automatically."""
        levels = []
        cumulative_atr = 0.0
        step_mult = 1.0
        for _ in range(self.max_safety_orders):
            cumulative_atr += step_mult * atr
            levels.append(entry_price - cumulative_atr)
            step_mult *= self.step_scale
        return levels

    def _calc_safety_order_sizes(self, base_order_usd: float) -> list[float]:
        """Each SO is volume_scale * previous. Base of calculation is the dynamic base order."""
        sizes = []
        size = base_order_usd
        for _ in range(self.max_safety_orders):
            size *= self.volume_scale
            sizes.append(size)
        return sizes

    def _calc_take_profit_pct(self, avg_bounce_pct: float) -> float:
        """TP from average bounce size. Conservative: 75% of average bounce, clamped."""
        tp = avg_bounce_pct * 0.75
        return max(self.min_take_profit_pct, min(tp, self.max_take_profit_pct))

    def _calc_max_deals(self, available_balance: float) -> int:
        """Max concurrent deals = floor(1 / risk_per_deal_pct)."""
        if self.risk_per_deal_pct <= 0:
            return 0
        return max(1, math.floor(1.0 / self.risk_per_deal_pct))

    def _calc_avg_bounce_pct(self) -> float:
        """Calculate average bounce from RSI < 35 oversold events in recent history."""
        if not self._rsi_history:
            return 2.0  # Default 2% if no data

        # Find oversold events (RSI < 35)
        oversold_events = []
        in_oversold = False
        oversold_low = 0.0

        for idx, rsi, close in self._rsi_history:
            if rsi < 35 and not in_oversold:
                in_oversold = True
                oversold_low = close
            elif rsi < 35 and in_oversold:
                oversold_low = min(oversold_low, close)
            elif rsi >= 35 and in_oversold:
                # Recovery — measure bounce
                bounce_pct = ((close - oversold_low) / oversold_low) * 100 if oversold_low > 0 else 0
                if bounce_pct > 0:
                    oversold_events.append(bounce_pct)
                in_oversold = False

        if not oversold_events:
            return 2.0  # Default

        return sum(oversold_events) / len(oversold_events)

    # --- Indicator updates ---

    def _update_indicators(self) -> None:
        window = max(self.atr_period, 14) + 50
        close = pd.Series(self._closes[-window:])
        high = pd.Series(self._highs[-window:])
        low = pd.Series(self._lows[-window:])

        # ATR
        atr = AverageTrueRange(high=high, low=low, close=close, window=self.atr_period)
        atr_val = atr.average_true_range().iloc[-1]
        self._last_atr = None if pd.isna(atr_val) else float(atr_val)

        # RSI (for bounce calculation and entry timing)
        rsi = RSIIndicator(close=close, window=14)
        rsi_val = rsi.rsi().iloc[-1]
        self._last_rsi = None if pd.isna(rsi_val) else float(rsi_val)

        # Track RSI history for bounce calculation
        if self._last_rsi is not None:
            self._rsi_history.append((self._candles_processed, self._last_rsi, self._closes[-1]))
            # Keep only last bounce_lookback_days worth (assume hourly candles)
            max_entries = self.bounce_lookback_days * 24
            if len(self._rsi_history) > max_entries:
                self._rsi_history = self._rsi_history[-max_entries:]

    # --- Deal management ---

    def _open_deal(self, price: float, timestamp: datetime) -> Signal | None:
        """Open a new deal: calculate everything dynamically."""
        if self._last_atr is None or self._last_atr <= 0:
            return None

        base_order_usd = self._calc_base_order_usd(self._available_balance)
        if base_order_usd < 1.0:
            return None

        safety_levels = self._calc_safety_order_levels(price, self._last_atr)
        safety_sizes = self._calc_safety_order_sizes(base_order_usd)

        avg_bounce = self._calc_avg_bounce_pct()
        tp_pct = self._calc_take_profit_pct(avg_bounce)
        tp_price = price * (1 + tp_pct / 100)

        # Stop-loss: max portfolio drawdown applied to this deal's allocation
        max_deal_capital = self._available_balance * self.risk_per_deal_pct
        stop_loss_usd = max_deal_capital * self.max_portfolio_drawdown_pct
        # Convert to price level: if base order amount at entry, what price = stop_loss_usd loss
        crypto_amount = base_order_usd / price if price > 0 else 0
        if crypto_amount > 0:
            stop_loss_price = price - (stop_loss_usd / crypto_amount)
        else:
            stop_loss_price = price * 0.8

        deal = {
            "entry_price": price,
            "avg_entry_price": price,
            "total_invested_usd": base_order_usd,
            "total_crypto": crypto_amount,
            "safety_levels": safety_levels,
            "safety_sizes": safety_sizes,
            "safety_orders_filled": 0,
            "take_profit_price": tp_price,
            "take_profit_pct": tp_pct,
            "stop_loss_price": stop_loss_price,
            "open_candle": self._candles_processed,
            "open_timestamp": timestamp,
        }
        self._deals.append(deal)
        self._available_balance -= base_order_usd

        return Signal(
            action="buy",
            pair=self.pair,
            price=price,
            order_type="market",
            amount_usd=base_order_usd,
            reason=f"DCA deal opened: base=${base_order_usd:.2f}, TP={tp_pct:.1f}%, ATR={self._last_atr:.2f}",
        )

    def _check_safety_orders(self, candle: Candle, deal: dict) -> list[Signal]:
        """Check if price dropped to any unfilled safety order levels."""
        signals = []
        filled = deal["safety_orders_filled"]

        while filled < len(deal["safety_levels"]):
            level = deal["safety_levels"][filled]
            if candle.low <= level:
                size_usd = deal["safety_sizes"][filled]

                # Check balance
                if size_usd > self._available_balance:
                    break

                fill_price = level
                crypto_amount = size_usd / fill_price if fill_price > 0 else 0

                # Update deal
                total_cost = deal["total_invested_usd"] + size_usd
                total_crypto = deal["total_crypto"] + crypto_amount
                deal["avg_entry_price"] = total_cost / total_crypto if total_crypto > 0 else deal["entry_price"]
                deal["total_invested_usd"] = total_cost
                deal["total_crypto"] = total_crypto
                deal["safety_orders_filled"] = filled + 1
                self._available_balance -= size_usd

                # Recalculate take-profit based on new avg entry
                deal["take_profit_price"] = deal["avg_entry_price"] * (1 + deal["take_profit_pct"] / 100)

                # Recalculate stop-loss based on total invested
                max_loss = deal["total_invested_usd"] * self.max_portfolio_drawdown_pct
                if deal["total_crypto"] > 0:
                    deal["stop_loss_price"] = deal["avg_entry_price"] - (max_loss / deal["total_crypto"])

                signals.append(Signal(
                    action="buy",
                    pair=self.pair,
                    price=fill_price,
                    order_type="limit",
                    limit_price=fill_price,
                    amount_usd=size_usd,
                    reason=f"Safety order #{filled + 1} filled at ${fill_price:.2f}",
                ))

                filled = deal["safety_orders_filled"]
            else:
                break

        return signals

    def _check_take_profit(self, candle: Candle, deal: dict) -> Signal | None:
        """Check if price reached take-profit level."""
        if candle.high >= deal["take_profit_price"]:
            return Signal(
                action="sell",
                pair=self.pair,
                price=deal["take_profit_price"],
                order_type="limit",
                limit_price=deal["take_profit_price"],
                amount_crypto=deal["total_crypto"],
                reason=f"take-profit at ${deal['take_profit_price']:.2f} (+{deal['take_profit_pct']:.1f}%)",
            )
        return None

    def _check_stop_loss(self, candle: Candle, deal: dict) -> Signal | None:
        """Check if unrealized loss exceeds threshold."""
        if candle.low <= deal["stop_loss_price"]:
            return Signal(
                action="sell",
                pair=self.pair,
                price=candle.close,
                order_type="market",
                amount_crypto=deal["total_crypto"],
                reason=f"stop-loss: price ${candle.close:.2f} < ${deal['stop_loss_price']:.2f}",
            )
        return None

    def _close_deal(self, deal: dict, reason: str) -> None:
        """Move deal from active to completed, restore balance."""
        deal["close_candle"] = self._candles_processed
        deal["close_reason"] = reason
        deal["duration_candles"] = self._candles_processed - deal["open_candle"]
        self._completed_deals.append(deal)
        self._deals.remove(deal)
        self._cooldown_remaining = self.cooldown_candles

    # --- Main entry point ---

    def on_candle(self, candle: Candle) -> list[Signal]:
        self._closes.append(candle.close)
        self._highs.append(candle.high)
        self._lows.append(candle.low)
        self._candles_processed += 1

        if self._candles_processed < self._min_candles:
            return []

        self._update_indicators()

        signals: list[Signal] = []

        # Tick cooldown at the start (before deal processing)
        deal_closed_this_candle = False

        # Process active deals (check TP/SL/SO first)
        for deal in list(self._deals):
            # Check stop-loss
            sl_signal = self._check_stop_loss(candle, deal)
            if sl_signal:
                signals.append(sl_signal)
                self._available_balance += deal["total_invested_usd"]
                self._close_deal(deal, "stop-loss")
                deal_closed_this_candle = True
                continue

            # Check take-profit
            tp_signal = self._check_take_profit(candle, deal)
            if tp_signal:
                signals.append(tp_signal)
                self._available_balance += deal["total_invested_usd"]
                self._close_deal(deal, "take-profit")
                deal_closed_this_candle = True
                continue

            # Check safety orders
            so_signals = self._check_safety_orders(candle, deal)
            signals.extend(so_signals)

        # Open new deal if conditions met (check before cooldown tick)
        if self._cooldown_remaining == 0 and not self._deals and not deal_closed_this_candle:
            max_deals = self._calc_max_deals(self._available_balance)
            if len(self._deals) < max_deals and self._available_balance > 10:
                signal = self._open_deal(candle.close, candle.timestamp)
                if signal:
                    signals.append(signal)

        # Tick cooldown after open check (skip on candle that closed a deal)
        if self._cooldown_remaining > 0 and not deal_closed_this_candle:
            self._cooldown_remaining -= 1

        return signals

    def get_state(self) -> dict:
        deal_summaries = []
        for d in self._deals:
            deal_summaries.append({
                "entry_price": d["entry_price"],
                "avg_entry_price": d["avg_entry_price"],
                "safety_orders_filled": d["safety_orders_filled"],
                "total_invested_usd": d["total_invested_usd"],
                "total_crypto": d["total_crypto"],
                "take_profit_price": d["take_profit_price"],
                "stop_loss_price": d["stop_loss_price"],
            })

        return {
            "atr": self._last_atr,
            "rsi": self._last_rsi,
            "active_deals": len(self._deals),
            "completed_deals": len(self._completed_deals),
            "deals": deal_summaries,
            "available_balance": self._available_balance,
            "candles_processed": self._candles_processed,
            "cooldown_remaining": self._cooldown_remaining,
        }
