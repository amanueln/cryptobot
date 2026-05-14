"""Regression test for donchian_shadow insert path.

The bug this guards: the INSERT statement specifies 22 columns but the tuple
appended to rows_to_insert had 23 values (one extra None between `replayed`
and `kept_in_queue`). Result: every momentum tick raised
`sqlite3.ProgrammingError: Incorrect number of bindings supplied. The current
statement uses 22, and there are 23 supplied.` — silently swallowed by the
catch-all in maybe_log_signals, so the table stayed empty for days while the
dashboard showed "shadow mode just started" forever.

A unit test of maybe_log_signals against a tmp DB catches the off-by-one
because executemany raises immediately on bind-count mismatch.
"""
import os
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock


def _build_breakout_engine():
    """Fake engine with a clean Donchian 20h breakout setup."""
    engine = MagicMock()
    engine.pairs = ["BTC-USD"]
    # 21 closes — first 20 flat at 100, last one breaks above
    engine._closes = {"BTC-USD": [100.0] * 20 + [105.0]}
    now = datetime.now(timezone.utc)
    engine._timestamps = {
        "BTC-USD": [now - timedelta(hours=20 - i) for i in range(21)],
    }
    engine.holdings = {}
    engine._rsi_cache = {}
    engine._adx_cache = {}
    engine._accel_scores = {}
    return engine


def test_maybe_log_signals_inserts_row_on_breakout():
    """The INSERT tuple must match the column list. Catches off-by-one Nones."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "test.db")
        # Reset module-global so _ensure_schema runs against the tmp DB
        from engine import donchian_shadow
        donchian_shadow._schema_initialized = False

        engine = _build_breakout_engine()
        n_logged = donchian_shadow.maybe_log_signals(engine, db)

        # 1 row should have been logged
        assert n_logged == 1, f"expected 1 row logged, got {n_logged}"

        # Verify the actual row landed in the table
        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                "SELECT pair, entry_price, rolling_20h_high, breakout_pct, replayed, kept_in_queue "
                "FROM donchian_shadow"
            ).fetchall()
        assert len(rows) == 1
        pair, entry, prior_high, bo_pct, replayed, kept = rows[0]
        assert pair == "BTC-USD"
        assert entry == 105.0
        assert prior_high == 100.0
        assert bo_pct == 5.0
        assert replayed == 0  # not yet replayed by daily script
        assert kept == 0


def test_maybe_log_signals_no_breakout_returns_zero():
    """Sanity: when current close <= prior 20h high, no row is logged."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "test.db")
        from engine import donchian_shadow
        donchian_shadow._schema_initialized = False

        engine = _build_breakout_engine()
        # Replace last close with one BELOW prior high — no breakout
        engine._closes["BTC-USD"][-1] = 99.0

        n_logged = donchian_shadow.maybe_log_signals(engine, db)
        assert n_logged == 0


def test_maybe_log_signals_dedupes_within_window():
    """Don't log the same pair twice within DEDUP_WINDOW_SEC (1h)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "test.db")
        from engine import donchian_shadow
        donchian_shadow._schema_initialized = False

        engine = _build_breakout_engine()
        first = donchian_shadow.maybe_log_signals(engine, db)
        second = donchian_shadow.maybe_log_signals(engine, db)
        assert first == 1
        assert second == 0  # deduped, current_ts == last_logged_ts
