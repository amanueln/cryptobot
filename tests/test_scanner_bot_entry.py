# tests/test_scanner_bot_entry.py
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

from engine.scanner_bot_schema import init_schema
from engine.scanner_bot import (
    Position, save_position, decide_entry, record_decision,
    EntryConfig,
)


def _seed_alert_table(db):
    """Create the early_scanner_alerts table the entry-poller reads from."""
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE early_scanner_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pair TEXT NOT NULL,
                price REAL NOT NULL,
                score INTEGER NOT NULL,
                signals TEXT NOT NULL,
                volume_24h REAL,
                change_1h_pct REAL,
                change_3h_pct REAL,
                notified INTEGER DEFAULT 0,
                outcome_12h_pct REAL,
                created_at TEXT NOT NULL,
                combo_key TEXT,
                score_adj INTEGER DEFAULT 0
            );
        """)


def _add_alert(db, alert_id, combo_key, pair, ts, price, score_adj=1):
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO early_scanner_alerts "
            "(id, timestamp, pair, price, score, signals, "
            " volume_24h, change_1h_pct, change_3h_pct, created_at, "
            " combo_key, score_adj) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (alert_id, ts, pair, price, 2, "[]",
             0, 0, 0, ts, combo_key, score_adj),
        )


def _cfg():
    return EntryConfig(
        eligible_combos=("mom_reversal+strong_move", "mom_reversal+squeeze"),
        position_usd=1000.0,
        max_concurrent=3,
        starting_cash_usd=3000.0,
        same_pair_cooldown_hours=4,
        stop_pct=15.0,
        hold_hours=24,
    )


def _no_candles(*_a, **_kw):
    """Stub candle fetcher that forces fallback to fixed stop_pct."""
    return None


def test_entry_skips_non_target_combo():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert_table(db)
        _add_alert(db, 1, "accumulation+bottom_bounce", "HIGH-USD",
                   "2026-04-29T10:00:00+00:00", 1.0)
        decision = decide_entry(db, alert_id=1, cfg=_cfg(), candles_fetcher=_no_candles)
        assert decision.action == "skip"
        assert "combo_not_eligible" in decision.reason


def test_entry_skips_at_capacity():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert_table(db)
        _add_alert(db, 1, "mom_reversal+strong_move", "HIGH-USD",
                   "2026-04-29T10:00:00+00:00", 1.0)
        # Pre-fill 3 open positions
        for i in range(3):
            save_position(db, Position(
                alert_id=100 + i, combo_key="mom_reversal+strong_move", pair=f"X{i}-USD",
                entry_ts="2026-04-29T09:00:00+00:00", entry_price=1.0,
                position_usd=1000.0, shares=1000.0, stop_price=0.85,
                hard_close_ts="2026-04-30T09:00:00+00:00",
            ))
        decision = decide_entry(db, alert_id=1, cfg=_cfg(), candles_fetcher=_no_candles)
        assert decision.action == "skip"
        assert "at_capacity" in decision.reason


def test_entry_skips_same_pair_cooldown():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert_table(db)
        # Insert a recent trade on HIGH-USD (1 hour ago)
        recent_exit = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO scanner_bot_trades (alert_id, combo_key, pair, entry_ts, entry_price, "
                "exit_ts, exit_price, position_usd, shares, gross_pnl_usd, fees_usd, net_pnl_usd, "
                "pct, peak_pct, exit_reason) VALUES "
                "(99, 'mom_reversal+strong_move', 'HIGH-USD', '2026-04-29T05:00:00+00:00', 1.0, "
                f"'{recent_exit}', 1.05, 1000.0, 1000.0, 50, 12, 38, 5.0, 5.0, 'manual')"
            )
        _add_alert(db, 1, "mom_reversal+strong_move", "HIGH-USD",
                   datetime.now(timezone.utc).isoformat(), 1.0)
        decision = decide_entry(db, alert_id=1, cfg=_cfg(), candles_fetcher=_no_candles)
        assert decision.action == "skip"
        assert "same_pair_cooldown" in decision.reason


def test_entry_accepted_clean_path():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert_table(db)
        _add_alert(db, 1, "mom_reversal+strong_move", "HIGH-USD",
                   "2026-04-29T10:00:00+00:00", 1.0)
        decision = decide_entry(db, alert_id=1, cfg=_cfg(), candles_fetcher=_no_candles)
        assert decision.action == "open"
        # entry_price comes from alert
        assert decision.entry_price == 1.0
        # stop = 1.0 * (1 - 0.15) = 0.85
        assert abs(decision.stop_price - 0.85) < 1e-6
        # shares = 1000 / 1.0
        assert decision.shares == 1000.0


def test_record_decision_writes_row():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db)
        record_decision(db, alert_id=42, ts="2026-04-29T10:00:00+00:00",
                        combo_key="mom_reversal+strong_move", pair="HIGH-USD",
                        decision="open", reason=None)
        with sqlite3.connect(db) as conn:
            r = conn.execute("SELECT decision, alert_id FROM scanner_bot_alert_decisions").fetchone()
        assert r == ("open", 42)
