# tests/test_scanner_bot_close.py
import os
import sqlite3
import tempfile

from engine.scanner_bot_schema import init_schema
from engine.scanner_bot import Position, save_position, close_position


def _make_position(db, **overrides):
    defaults = dict(
        alert_id=1, combo_key="mom_reversal+strong_move", pair="HIGH-USD",
        entry_ts="2026-04-29T10:00:00+00:00", entry_price=1.0,
        position_usd=1000.0, shares=1000.0, stop_price=0.85,
        hard_close_ts="2026-04-30T10:00:00+00:00",
    )
    defaults.update(overrides)
    p = Position(**defaults)
    pid = save_position(db, p)
    p.id = pid
    return p


def test_close_position_writes_trade_and_removes_from_open():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db)
        p = _make_position(db)
        p.peak_price = 1.18

        close_position(
            db, p,
            exit_ts="2026-04-29T14:00:00+00:00",
            exit_price=1.10,
            exit_reason="manual",
            fee_pct_per_side=0.6,
        )

        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            opens = conn.execute("SELECT COUNT(*) FROM scanner_bot_positions").fetchone()[0]
            trades = conn.execute("SELECT * FROM scanner_bot_trades").fetchall()

        assert opens == 0
        assert len(trades) == 1
        t = trades[0]
        assert t["pair"] == "HIGH-USD"
        assert t["exit_reason"] == "manual"
        # gross = (1.10 - 1.0) * 1000 = 100
        assert abs(t["gross_pnl_usd"] - 100.0) < 1e-6
        # fees = 1000 * 0.006 * 2 = 12
        assert abs(t["fees_usd"] - 12.0) < 1e-6
        # net = 100 - 12 = 88
        assert abs(t["net_pnl_usd"] - 88.0) < 1e-6
        # pct = 10%
        assert abs(t["pct"] - 10.0) < 1e-6
        # peak_pct = 18%
        assert abs(t["peak_pct"] - 18.0) < 1e-6


def test_close_position_loss():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db)
        p = _make_position(db)
        p.peak_price = 1.02
        close_position(
            db, p,
            exit_ts="2026-04-29T14:00:00+00:00",
            exit_price=0.85,
            exit_reason="stop_15pct",
            fee_pct_per_side=0.6,
        )
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            t = conn.execute("SELECT * FROM scanner_bot_trades").fetchone()
        # gross = (0.85 - 1.0) * 1000 = -150
        assert abs(t["gross_pnl_usd"] - (-150.0)) < 1e-6
        # net = -150 - 12 = -162
        assert abs(t["net_pnl_usd"] - (-162.0)) < 1e-6
        assert t["exit_reason"] == "stop_15pct"
