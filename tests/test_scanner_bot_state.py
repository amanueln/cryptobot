# tests/test_scanner_bot_state.py
import os
import sqlite3
import tempfile

from engine.scanner_bot_schema import init_schema
from engine.scanner_bot import Position, save_position, load_open_positions, update_position


def test_save_and_load_position():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db)
        p = Position(
            alert_id=1, combo_key="mom_reversal+strong_move", pair="HIGH-USD",
            entry_ts="2026-04-29T10:00:00+00:00", entry_price=1.0,
            position_usd=1000.0, shares=1000.0,
            stop_price=0.85, hard_close_ts="2026-04-30T10:00:00+00:00",
            milestones_hit=[],
            trail_stop_price=0.92,
        )
        save_position(db, p)
        opens = load_open_positions(db)
        assert len(opens) == 1
        assert opens[0].pair == "HIGH-USD"
        assert opens[0].milestones_hit == []
        assert opens[0].trail_stop_price == 0.92


def test_milestones_round_trip_as_json():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db)
        p = Position(
            alert_id=2, combo_key="mom_reversal+squeeze", pair="RAVE-USD",
            entry_ts="2026-04-29T10:00:00+00:00", entry_price=2.0,
            position_usd=1000.0, shares=500.0,
            stop_price=1.7, hard_close_ts="2026-04-30T10:00:00+00:00",
            milestones_hit=[10, 15],
        )
        save_position(db, p)
        opens = load_open_positions(db)
        assert opens[0].milestones_hit == [10, 15]


def test_update_position_persists_tick_state():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db)
        p = Position(
            alert_id=3, combo_key="mom_reversal+strong_move", pair="MEZO-USD",
            entry_ts="2026-04-29T10:00:00+00:00", entry_price=1.0,
            position_usd=1000.0, shares=1000.0,
            stop_price=0.85, hard_close_ts="2026-04-30T10:00:00+00:00",
        )
        save_position(db, p)
        opens = load_open_positions(db)
        opens[0].current_price = 1.12
        opens[0].current_pct = 12.0
        opens[0].peak_price = 1.15
        opens[0].milestones_hit = [10]
        opens[0].trail_stop_price = 1.08
        update_position(db, opens[0])
        again = load_open_positions(db)
        assert again[0].current_price == 1.12
        assert again[0].peak_price == 1.15
        assert again[0].milestones_hit == [10]
        assert again[0].trail_stop_price == 1.08
