# tests/test_scanner_bot_exit.py
import os
import tempfile
from datetime import datetime, timedelta, timezone

from engine.scanner_bot_schema import init_schema
from engine.scanner_bot import Position, save_position, tick_position, ExitDecision


def _make_position(**overrides):
    base = dict(
        alert_id=1, combo_key="mom_reversal+strong_move", pair="HIGH-USD",
        entry_ts="2026-04-29T10:00:00+00:00", entry_price=1.0,
        position_usd=1000.0, shares=1000.0, stop_price=0.85,
        hard_close_ts="2026-04-30T10:00:00+00:00",
    )
    base.update(overrides)
    return Position(id=1, **base)


def test_exit_manual_takes_priority():
    p = _make_position()
    p.manual_sell_requested = 1
    d = tick_position(p, current_price=1.20, now=datetime(2026, 4, 29, 12, tzinfo=timezone.utc))
    assert d.action == "close"
    assert d.exit_reason == "manual"
    assert d.exit_price == 1.20


def test_exit_stop_fires_at_stop_price():
    p = _make_position()
    d = tick_position(p, current_price=0.84, now=datetime(2026, 4, 29, 12, tzinfo=timezone.utc))
    assert d.action == "close"
    assert d.exit_reason == "stop_15pct"
    assert d.exit_price == 0.85   # at stop, not lower


def test_exit_time_cap_fires():
    p = _make_position()
    d = tick_position(
        p, current_price=0.95,
        now=datetime(2026, 4, 30, 10, 1, tzinfo=timezone.utc),  # 1m past hard_close
    )
    assert d.action == "close"
    assert d.exit_reason == "time_24h"
    assert d.exit_price == 0.95


def test_exit_holds_when_no_trigger():
    p = _make_position()
    d = tick_position(p, current_price=1.05, now=datetime(2026, 4, 29, 12, tzinfo=timezone.utc))
    assert d.action == "hold"
    assert d.exit_reason is None


def test_tick_updates_peak_and_pct():
    p = _make_position()
    d = tick_position(p, current_price=1.10, now=datetime(2026, 4, 29, 12, tzinfo=timezone.utc))
    assert d.action == "hold"
    assert p.current_price == 1.10
    assert abs(p.current_pct - 10.0) < 1e-6
    assert p.peak_price == 1.10
    # second tick lower — peak preserved
    tick_position(p, current_price=1.05, now=datetime(2026, 4, 29, 13, tzinfo=timezone.utc))
    assert p.peak_price == 1.10
    assert abs(p.current_pct - 5.0) < 1e-6


def test_priority_manual_beats_stop():
    p = _make_position()
    p.manual_sell_requested = 1
    # current price below stop AND manual flag set → manual wins
    d = tick_position(p, current_price=0.80, now=datetime(2026, 4, 29, 12, tzinfo=timezone.utc))
    assert d.exit_reason == "manual"
    assert d.exit_price == 0.80   # manual exits at current, not stop
