# tests/test_scanner_bot_loop.py
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from engine.scanner_bot_schema import init_schema
from engine.scanner_bot import ScannerBot, EntryConfig
from tests.test_scanner_bot_entry import _seed_alert_table, _add_alert


def _cfg():
    return EntryConfig(
        eligible_combos=("mom_reversal+strong_move",),
        position_usd=1000.0, max_concurrent=3, starting_cash_usd=3000.0,
        same_pair_cooldown_hours=4, stop_pct=15.0, hold_hours=24,
    )


def test_tick_opens_position_from_new_alert():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert_table(db)

        # Bot is constructed BEFORE the alert exists — mirrors the real flow
        # where the bot starts at MAX(id) and only reacts to alerts that arrive
        # after that point. Tests would fail under the new init behavior if we
        # added the alert first (cursor would skip it).
        bot = ScannerBot(db_path=db, cfg=_cfg(), discord_webhook=None,
                         price_fn=MagicMock(return_value=1.0),
                         candles_fetcher=lambda *a, **k: None)
        _add_alert(db, 1, "mom_reversal+strong_move", "HIGH-USD",
                   datetime.now(timezone.utc).isoformat(), 1.0)
        bot.tick(now=datetime.now(timezone.utc))

        with sqlite3.connect(db) as conn:
            n_open = conn.execute("SELECT COUNT(*) FROM scanner_bot_positions").fetchone()[0]
            n_dec = conn.execute(
                "SELECT COUNT(*) FROM scanner_bot_alert_decisions WHERE decision='open'"
            ).fetchone()[0]
        assert n_open == 1
        assert n_dec == 1


def test_tick_closes_position_on_stop():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert_table(db)

        price = MagicMock(side_effect=[1.0, 0.80])  # open at 1.0, then drop to 0.80
        bot = ScannerBot(db_path=db, cfg=_cfg(), discord_webhook=None, price_fn=price,
                         candles_fetcher=lambda *a, **k: None)
        _add_alert(db, 1, "mom_reversal+strong_move", "HIGH-USD",
                   datetime.now(timezone.utc).isoformat(), 1.0)
        bot.tick(now=datetime.now(timezone.utc))
        # Second tick: price below stop
        bot.tick(now=datetime.now(timezone.utc) + timedelta(minutes=5))

        with sqlite3.connect(db) as conn:
            n_open = conn.execute("SELECT COUNT(*) FROM scanner_bot_positions").fetchone()[0]
            r = conn.execute(
                "SELECT exit_reason, exit_price FROM scanner_bot_trades"
            ).fetchone()
        assert n_open == 0
        assert r[0] == "stop_15pct"
        assert r[1] == 0.85   # filled at stop, not lower


def test_startup_seeds_cursor_to_max_alert_id_skipping_history():
    """Historical alerts that already fired Discord pings must NOT be replayed."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert_table(db)
        # 5 historical alerts already in the DB (e.g., from days ago, already
        # consumed via Discord pings).
        for i in range(1, 6):
            _add_alert(db, i, "mom_reversal+strong_move", f"OLD{i}-USD",
                       datetime.now(timezone.utc).isoformat(), 1.0)

        bot = ScannerBot(db_path=db, cfg=_cfg(), discord_webhook=None,
                         price_fn=MagicMock(return_value=1.0),
                         candles_fetcher=lambda *a, **k: None)
        # Cursor must be seeded to 5, not 0.
        assert bot._last_alert_check_id == 5
        bot.tick(now=datetime.now(timezone.utc))

        with sqlite3.connect(db) as conn:
            n_open = conn.execute("SELECT COUNT(*) FROM scanner_bot_positions").fetchone()[0]
        assert n_open == 0  # zero replayed historical alerts


def test_freshness_filter_skips_stale_alerts():
    """Even past the cursor, alerts older than alert_max_age_minutes are skipped."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert_table(db)

        bot = ScannerBot(db_path=db, cfg=_cfg(), discord_webhook=None,
                         price_fn=MagicMock(return_value=1.0),
                         candles_fetcher=lambda *a, **k: None,
                         alert_max_age_minutes=5)

        # Insert a stale alert (10 minutes old).
        stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        _add_alert(db, 1, "mom_reversal+strong_move", "STALE-USD", stale_ts, 1.0)

        bot.tick(now=datetime.now(timezone.utc))

        with sqlite3.connect(db) as conn:
            n_open = conn.execute("SELECT COUNT(*) FROM scanner_bot_positions").fetchone()[0]
        assert n_open == 0


def test_tick_writes_equity_snapshot():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        init_schema(db); _seed_alert_table(db)
        bot = ScannerBot(db_path=db, cfg=_cfg(), discord_webhook=None,
                         price_fn=MagicMock(return_value=1.0),
                         candles_fetcher=lambda *a, **k: None)
        bot.tick(now=datetime(2026, 4, 29, 10, 0, tzinfo=timezone.utc))
        with sqlite3.connect(db) as conn:
            r = conn.execute(
                "SELECT cash_usd, total_equity_usd, open_positions FROM scanner_bot_equity"
            ).fetchone()
        assert r[0] == 3000.0  # all cash
        assert r[1] == 3000.0
        assert r[2] == 0
