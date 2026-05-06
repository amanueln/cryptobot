# tests/test_scanner_bot_atr.py
"""Tests for the ATR-based entry stop in scanner_bot.

The trail logic and exit priority live in test_scanner_bot_exit.py.
This file focuses on:
  - compute_atr_stop_price math + bumpers
  - decide_entry uses ATR when candles available, falls back when not
  - Position trough_price tracking + MAE persistence
"""
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

from engine.scanner_bot_schema import init_schema
from engine.scanner_bot import (
    Position, save_position, close_position,
    tick_position, decide_entry,
    compute_atr_stop_price, EntryConfig,
)


# ---------------- compute_atr_stop_price ----------------

def _candles(highs_lows: list[tuple[float, float]], close: float):
    return [{"high": h, "low": l, "close": close} for (h, l) in highs_lows]


def test_atr_basic_calc():
    """ATR = avg(high - low) / close. With multiplier 2.0, stop = 2× ATR pct."""
    # 5 candles, each with range $1, close $100 → ATR pct = 1%, * 2 = 2%
    candles = _candles([(101, 100)] * 5, close=100.0)
    stop = compute_atr_stop_price(100.0, candles, multiplier=2.0, min_pct=0.5, max_pct=15.0)
    assert abs(stop - 98.0) < 1e-6  # 2% below entry


def test_atr_clamped_to_min():
    """Tiny ATR — stop bounded by min_pct."""
    candles = _candles([(100.05, 100.0)] * 5, close=100.0)  # 0.05% ATR
    stop = compute_atr_stop_price(100.0, candles, multiplier=2.0, min_pct=3.0, max_pct=8.0)
    assert abs(stop - 97.0) < 1e-6  # 3% min applied


def test_atr_clamped_to_max():
    """Wild coin — stop capped at max_pct."""
    candles = _candles([(110, 90)] * 5, close=100.0)  # 20% ATR
    stop = compute_atr_stop_price(100.0, candles, multiplier=2.0, min_pct=3.0, max_pct=8.0)
    assert abs(stop - 92.0) < 1e-6  # 8% max applied


def test_atr_returns_none_on_no_candles():
    assert compute_atr_stop_price(100.0, None) is None
    assert compute_atr_stop_price(100.0, []) is None


def test_atr_returns_none_on_zero_entry():
    candles = _candles([(101, 100)] * 5, close=100.0)
    assert compute_atr_stop_price(0.0, candles) is None


def test_atr_skips_zero_range_candles():
    """Candles with high == low (no range) are filtered out."""
    candles = _candles([(100, 100), (100, 100), (102, 100)], close=100.0)  # only one usable
    stop = compute_atr_stop_price(100.0, candles, multiplier=2.0, min_pct=0.5, max_pct=15.0)
    # one candle with range 2, mean=2, atr_pct=2%, *2=4% → stop = 96
    assert abs(stop - 96.0) < 1e-6


# ---------------- decide_entry uses ATR ----------------

def _seed_alert(db, pair="HIGH-USD", combo="mom_reversal+strong_move"):
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS early_scanner_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL, pair TEXT NOT NULL, price REAL NOT NULL,
                score INTEGER NOT NULL, signals TEXT NOT NULL, volume_24h REAL,
                change_1h_pct REAL, change_3h_pct REAL, notified INTEGER DEFAULT 0,
                outcome_12h_pct REAL, created_at TEXT NOT NULL,
                combo_key TEXT, score_adj INTEGER DEFAULT 0
            );
        """)
        conn.execute(
            "INSERT INTO early_scanner_alerts "
            "(id, timestamp, pair, price, score, signals, "
            " volume_24h, change_1h_pct, change_3h_pct, created_at, combo_key, score_adj) "
            "VALUES (1, '2026-05-06T10:00:00+00:00', ?, 1.0, 2, '[]', 0, 0, 0, "
            "'2026-05-06T10:00:00+00:00', ?, 1)",
            (pair, combo),
        )


def _cfg(stop_pct=8.0, max_stop_pct=8.0):
    return EntryConfig(
        eligible_combos=("mom_reversal+strong_move", "mom_reversal+squeeze"),
        position_usd=1000.0, max_concurrent=3, starting_cash_usd=3000.0,
        same_pair_cooldown_hours=4, stop_pct=stop_pct, hold_hours=24,
        atr_period=14, atr_multiplier=2.0, min_stop_pct=3.0, max_stop_pct=max_stop_pct,
    )


def test_decide_entry_uses_atr_when_candles_available():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert(db)
        # Inject candles → ATR 2% per hour, * multiplier 2 = 4% stop
        candles = [{"high": 1.02, "low": 1.0, "close": 1.0} for _ in range(14)]
        decision = decide_entry(db, 1, _cfg(), candles_fetcher=lambda *a, **kw: candles)
        assert decision.action == "open"
        # 4% below entry 1.0 = 0.96
        assert abs(decision.stop_price - 0.96) < 1e-6


def test_decide_entry_falls_back_when_candles_none():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert(db)
        decision = decide_entry(db, 1, _cfg(stop_pct=8.0),
                                candles_fetcher=lambda *a, **kw: None)
        assert decision.action == "open"
        # Falls back to cfg.stop_pct = 8% → 0.92
        assert abs(decision.stop_price - 0.92) < 1e-6


# ---------------- Trough / MAE tracking ----------------

def _pos(db, entry=1.0):
    p = Position(
        alert_id=1, combo_key="mom_reversal+squeeze", pair="HIGH-USD",
        entry_ts="2026-05-06T10:00:00+00:00", entry_price=entry,
        position_usd=1000.0, shares=1000.0,
        stop_price=entry * 0.92,
        hard_close_ts="2026-05-07T10:00:00+00:00",
    )
    save_position(db, p)
    return p


def test_trough_tracks_lowest_price():
    p = Position(
        alert_id=1, combo_key="x", pair="X",
        entry_ts="2026-05-06T10:00:00+00:00", entry_price=1.0,
        position_usd=1000, shares=1000,
        stop_price=0.50,  # wide enough to never trigger in this test
        hard_close_ts="2030-01-01T00:00:00+00:00",
        id=1,
    )
    now = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
    tick_position(p, current_price=0.95, now=now)
    assert p.trough_price == 0.95
    tick_position(p, current_price=0.97, now=now)
    assert p.trough_price == 0.95  # didn't drop further, trough stays
    tick_position(p, current_price=0.90, now=now)
    assert p.trough_price == 0.90  # ratcheted down


def test_trough_capped_at_entry():
    """If price never goes below entry, trough = entry (MAE = 0)."""
    p = Position(
        alert_id=1, combo_key="x", pair="X", entry_ts="2026-05-06T10:00:00+00:00",
        entry_price=1.0, position_usd=1000, shares=1000,
        stop_price=0.85,
        hard_close_ts="2030-01-01T00:00:00+00:00",
        id=1,
    )
    now = datetime(2026, 5, 6, 10, 0, tzinfo=timezone.utc)
    tick_position(p, current_price=1.05, now=now)  # only goes up
    tick_position(p, current_price=1.10, now=now)
    assert p.trough_price == 1.0  # capped at entry, MAE will be 0


def test_close_writes_max_adverse_pct():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db)
        p = _pos(db)
        # Simulate a tick that bled to 0.92, then a recovery tick at 1.0
        now = datetime(2026, 5, 6, 11, 0, tzinfo=timezone.utc)
        tick_position(p, current_price=0.92, now=now)
        tick_position(p, current_price=1.0, now=now)
        # Persist the trough so close_position picks it up
        from engine.scanner_bot import update_position
        update_position(db, p)

        close_position(db, p, exit_ts="2026-05-06T12:00:00+00:00",
                       exit_price=1.0, exit_reason="manual")
        with sqlite3.connect(db) as conn:
            mae = conn.execute("SELECT max_adverse_pct FROM scanner_bot_trades").fetchone()[0]
        assert mae is not None
        assert abs(mae - (-8.0)) < 1e-6  # bled to 0.92 from 1.0 = -8%
