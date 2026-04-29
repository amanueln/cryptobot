import os
import sqlite3
import tempfile

from engine.scanner_bot_schema import init_schema


EXPECTED_TABLES = {
    "scanner_bot_positions",
    "scanner_bot_trades",
    "scanner_bot_equity",
    "scanner_bot_alert_decisions",
}


def test_init_schema_creates_tables():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db)
        with sqlite3.connect(db) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        assert EXPECTED_TABLES.issubset(tables)


def test_init_schema_is_idempotent():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db)
        init_schema(db)
        with sqlite3.connect(db) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'scanner_bot_%'"
            ).fetchone()[0]
        assert n == 4
