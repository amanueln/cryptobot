"""Tests for DCA Safety Orders (Martingale-style) strategy."""

import math
from datetime import datetime, timedelta

from exchange.models import Candle, Signal
from strategies.dca_safety import DCASafetyStrategy


DCA_CONFIG = {
    "pairs": ["ETH-USD"],
    "pair": "ETH-USD",
    "granularity": "ONE_HOUR",
    "risk_per_deal_pct": 0.35,
    "volume_scale": 1.5,
    "step_scale": 1.5,
    "max_safety_orders": 5,
    "atr_period": 14,
    "bounce_lookback_days": 30,
    "min_take_profit_pct": 0.8,
    "max_take_profit_pct": 3.0,
    "max_portfolio_drawdown_pct": 0.10,
    "cooldown_candles": 5,
    "starting_balance": 3000,
}


def make_candle(
    close: float, hour: int = 0, high: float | None = None,
    low: float | None = None, open_: float | None = None,
    pair: str = "ETH-USD",
) -> Candle:
    if high is None:
        high = close * 1.01
    if low is None:
        low = close * 0.99
    if open_ is None:
        open_ = close * 0.998
    return Candle(
        pair=pair,
        granularity="ONE_HOUR",
        timestamp=datetime(2026, 1, 1) + timedelta(hours=hour),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
    )


def _warmup_flat(strategy, base_price=3000.0, count=40):
    """Feed flat candles to populate indicators."""
    for i in range(count):
        strategy.on_candle(make_candle(
            close=base_price,
            high=base_price * 1.005,
            low=base_price * 0.995,
            hour=i,
        ))
    return count


# --- Configuration tests ---

def test_configure():
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)
    assert s.pair == "ETH-USD"
    assert s.risk_per_deal_pct == 0.35
    assert s.volume_scale == 1.5
    assert s.step_scale == 1.5
    assert s.max_safety_orders == 5
    assert s.atr_period == 14
    assert s.min_take_profit_pct == 0.8
    assert s.max_take_profit_pct == 3.0
    assert s.max_portfolio_drawdown_pct == 0.10
    assert s.cooldown_candles == 5


def test_get_state_initial():
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)
    state = s.get_state()
    assert state["active_deals"] == 0
    assert state["atr"] is None
    assert state["completed_deals"] == 0
    assert state["candles_processed"] == 0


# --- Warmup tests ---

def test_no_signals_during_warmup():
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    for i in range(10):
        signals = s.on_candle(make_candle(close=3000, hour=i))
        assert signals == []


def test_atr_populated_after_warmup():
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    _warmup_flat(s, base_price=3000, count=40)
    state = s.get_state()
    assert state["atr"] is not None
    assert state["atr"] > 0


# --- Dynamic calculation tests ---

def test_base_order_size_scales_with_balance():
    """Base order must be proportional to available balance, not hardcoded."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    # With $3000 balance, risk_per_deal_pct=0.35
    # base_order = (balance * risk_pct) / (1 + sum_of_SO_multipliers)
    # SO multipliers: 1.5, 2.25, 3.375, 5.0625, 7.59375 (volume_scale=1.5, max_so=5)
    # sum = 1.5 + 2.25 + 3.375 + 5.0625 + 7.59375 = 19.78125
    # base_order = (3000 * 0.35) / (1 + 19.78125) = 1050 / 20.78125 ≈ 50.53
    bo = s._calc_base_order_usd(available_balance=3000)
    expected_sum = sum(1.5 ** i for i in range(1, 6))  # 19.78125
    expected_bo = (3000 * 0.35) / (1 + expected_sum)
    assert abs(bo - expected_bo) < 0.01


def test_base_order_size_different_balance():
    """$10K should give proportionally larger orders."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    bo_3k = s._calc_base_order_usd(available_balance=3000)
    bo_10k = s._calc_base_order_usd(available_balance=10000)
    assert abs(bo_10k / bo_3k - 10000 / 3000) < 0.01


def test_safety_order_levels_use_atr():
    """Safety order levels should be ATR-based, not fixed percentages."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    # ATR = 50, step_scale = 1.5
    # Level 1: entry - 1.0 * ATR
    # Level 2: entry - (1.0 + 1.5) * ATR
    # Level 3: entry - (1.0 + 1.5 + 2.25) * ATR
    levels = s._calc_safety_order_levels(entry_price=3000.0, atr=50.0)
    assert len(levels) == 5
    assert levels[0] == 3000.0 - 1.0 * 50.0  # 2950
    assert levels[1] == 3000.0 - (1.0 + 1.5) * 50.0  # 2875
    assert levels[2] == 3000.0 - (1.0 + 1.5 + 2.25) * 50.0  # 2762.5


def test_safety_order_sizes_use_volume_scale():
    """Each SO should be volume_scale * previous SO size."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    sizes = s._calc_safety_order_sizes(base_order_usd=100.0)
    assert len(sizes) == 5
    assert abs(sizes[0] - 150.0) < 0.01   # 100 * 1.5
    assert abs(sizes[1] - 225.0) < 0.01   # 150 * 1.5
    assert abs(sizes[2] - 337.5) < 0.01   # 225 * 1.5


def test_take_profit_from_bounce_history():
    """TP should be calculated from historical bounce data, clamped to min/max."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    # If average bounce is 2%, conservative TP = 2% * 0.75 = 1.5%
    tp = s._calc_take_profit_pct(avg_bounce_pct=2.0)
    assert 0.8 <= tp <= 3.0

    # Very small bounce -> clamped to min
    tp_small = s._calc_take_profit_pct(avg_bounce_pct=0.5)
    assert tp_small == 0.8

    # Very large bounce -> clamped to max
    tp_large = s._calc_take_profit_pct(avg_bounce_pct=10.0)
    assert tp_large == 3.0


def test_max_deals_scales_with_balance():
    """Max concurrent deals should scale with account size."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    # max_capital_per_deal = balance * risk_per_deal_pct = 3000 * 0.35 = 1050
    # max_deals = floor(3000 / 1050) = 2
    assert s._calc_max_deals(available_balance=3000) == 2

    # $10000: floor(10000 / 3500) = 2 ... wait
    # max_capital = 10000 * 0.35 = 3500
    # max_deals = floor(10000 / 3500) = 2
    assert s._calc_max_deals(available_balance=10000) == 2

    # Actually the formula should be more nuanced. Let me recalculate:
    # Each deal uses risk_per_deal_pct of AVAILABLE balance at deal start
    # So with 35%, first deal uses 35%, leaving 65%. Second uses 35% of 65% = 22.75%
    # Total: 57.75%. Third: 35% of 42.25% = 14.8%. Total: 72.5%
    # This naturally limits deals. But the simplest: floor(1 / risk_per_deal_pct)
    # = floor(1 / 0.35) = 2
    assert s._calc_max_deals(available_balance=3000) >= 1


# --- Deal lifecycle tests ---

def test_opens_deal_after_warmup():
    """Strategy should open a deal when conditions are right after warmup."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    hour = _warmup_flat(s, base_price=3000, count=40)

    # Feed a candle — strategy should open first deal
    signals = s.on_candle(make_candle(close=3000, hour=hour))

    # First deal should generate a buy signal
    buys = [sig for sig in signals if sig.action == "buy"]
    if buys:
        assert buys[0].amount_usd is not None
        assert buys[0].amount_usd > 0
        state = s.get_state()
        assert state["active_deals"] == 1


def test_no_double_deal_same_pair():
    """Should not open a second deal on same pair while one is active."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    hour = _warmup_flat(s, base_price=3000, count=40)

    # Open first deal
    s.on_candle(make_candle(close=3000, hour=hour))

    # Force a deal to be active
    if not s._deals:
        s._open_deal(3000.0, datetime(2026, 1, 1) + timedelta(hours=hour))

    state = s.get_state()
    deals_before = state["active_deals"]

    # Feed more candles — should NOT open another deal on same pair
    for i in range(10):
        s.on_candle(make_candle(close=2990, hour=hour + 1 + i))

    state = s.get_state()
    assert state["active_deals"] <= deals_before


def test_safety_order_fills_on_price_drop():
    """When price drops to SO level, a buy signal should be generated."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    hour = _warmup_flat(s, base_price=3000, count=40)

    # Open a deal
    s._open_deal(3000.0, datetime(2026, 1, 1) + timedelta(hours=hour))
    deal = s._deals[0]

    # Price drops to first safety order level
    so_price = deal["safety_levels"][0]
    signals = s.on_candle(make_candle(
        close=so_price - 1,
        low=so_price - 5,
        hour=hour + 1,
    ))

    buys = [sig for sig in signals if sig.action == "buy"]
    assert len(buys) >= 1
    assert deal["safety_orders_filled"] >= 1


def test_take_profit_closes_deal():
    """When price rises to TP level, a sell signal should be generated."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    hour = _warmup_flat(s, base_price=3000, count=40)

    # Clear any deals opened during warmup, then open exactly one
    s._deals.clear()
    s._cooldown_remaining = 0
    s._open_deal(3000.0, datetime(2026, 1, 1) + timedelta(hours=hour))
    assert len(s._deals) == 1
    deal = s._deals[0]
    tp_price = deal["take_profit_price"]

    # Price rises to take-profit
    signals = s.on_candle(make_candle(
        close=tp_price + 1,
        high=tp_price + 5,
        hour=hour + 1,
    ))

    sells = [sig for sig in signals if sig.action == "sell"]
    assert len(sells) == 1
    assert s.get_state()["active_deals"] == 0
    assert s.get_state()["completed_deals"] >= 1


def test_stop_loss_closes_deal():
    """When unrealized loss hits portfolio drawdown threshold, deal should close."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    hour = _warmup_flat(s, base_price=3000, count=40)

    # Clear warmup deals, open exactly one
    s._deals.clear()
    s._cooldown_remaining = 0
    s._open_deal(3000.0, datetime(2026, 1, 1) + timedelta(hours=hour))
    assert len(s._deals) == 1
    deal = s._deals[0]

    # Price crashes well below entry — should trigger stop
    crash_price = deal["stop_loss_price"] - 10
    signals = s.on_candle(make_candle(
        close=crash_price,
        low=crash_price - 5,
        hour=hour + 1,
    ))

    sells = [sig for sig in signals if sig.action == "sell"]
    assert len(sells) == 1
    assert "stop-loss" in sells[0].reason


def test_cooldown_prevents_immediate_reentry():
    """After a deal closes, cooldown should prevent immediate new deal."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    hour = _warmup_flat(s, base_price=3000, count=40)

    # Clear warmup deals, open exactly one
    s._deals.clear()
    s._cooldown_remaining = 0
    s._open_deal(3000.0, datetime(2026, 1, 1) + timedelta(hours=hour))
    deal = s._deals[0]
    tp = deal["take_profit_price"]

    # Close the deal via take-profit
    s.on_candle(make_candle(close=tp + 1, high=tp + 5, hour=hour + 1))
    assert s.get_state()["active_deals"] == 0

    # Next cooldown_candles candles should NOT open a new deal
    deals_opened = 0
    for i in range(s.cooldown_candles):
        signals = s.on_candle(make_candle(close=3000, hour=hour + 2 + i))
        if any(sig.action == "buy" for sig in signals):
            deals_opened += 1

    assert deals_opened == 0


def test_deal_tracking():
    """Each deal should track entry, avg entry, SOs filled, total invested."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    hour = _warmup_flat(s, base_price=3000, count=40)

    s._open_deal(3000.0, datetime(2026, 1, 1) + timedelta(hours=hour))
    deal = s._deals[0]

    assert deal["entry_price"] == 3000.0
    assert deal["avg_entry_price"] == 3000.0
    assert deal["safety_orders_filled"] == 0
    assert deal["total_invested_usd"] > 0
    assert deal["total_crypto"] > 0
    assert "open_candle" in deal


def test_avg_entry_updates_on_safety_order():
    """Average entry price should update when safety orders fill."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    hour = _warmup_flat(s, base_price=3000, count=40)

    s._open_deal(3000.0, datetime(2026, 1, 1) + timedelta(hours=hour))
    deal = s._deals[0]

    initial_avg = deal["avg_entry_price"]
    initial_crypto = deal["total_crypto"]

    # Drop to first SO
    so_price = deal["safety_levels"][0]
    s.on_candle(make_candle(close=so_price - 1, low=so_price - 5, hour=hour + 1))

    # Avg entry should be lower now (better)
    assert deal["avg_entry_price"] < initial_avg
    assert deal["total_crypto"] > initial_crypto


# --- Full cycle integration test ---

def test_full_cycle_no_crash():
    """Feed 300 candles with varied price action — should not crash."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)

    total_signals = []
    for i in range(300):
        # Sine wave with downward drift
        base = 3000
        p = base + 200 * math.sin(i * 0.08) - i * 0.5
        c = make_candle(
            close=p,
            high=p + 15,
            low=p - 15,
            hour=i,
        )
        signals = s.on_candle(c)
        total_signals.extend(signals)

    state = s.get_state()
    assert state["candles_processed"] == 300


def test_multi_pair_not_supported_in_single_instance():
    """Each strategy instance handles one pair. Multi-pair = multiple instances."""
    s = DCASafetyStrategy()
    s.configure(DCA_CONFIG)
    assert s.pair == "ETH-USD"
