"""Tests for the /api/candles/live live-chart endpoint."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta

import pytest


def _make_tape_db(path: str, ticks: list[tuple[str, str, float, float]]) -> None:
    """ticks: list of (pair, ts_iso_naive_utc, price, size)."""
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE ws_matches (
            pair TEXT, ts TEXT, price REAL, size REAL, side TEXT
        )"""
    )
    conn.executemany(
        "INSERT INTO ws_matches (pair, ts, price, size, side) VALUES (?,?,?,?,'buy')",
        ticks,
    )
    conn.commit()
    conn.close()


def test_build_live_bar_aggregates_ticks_in_current_bucket():
    from dashboard.api.app import _build_live_bar

    with tempfile.TemporaryDirectory() as tmp:
        tape_path = os.path.join(tmp, "market_tape.db")
        # Bucket starts at 2026-04-20 15:30:00 UTC
        bucket_start = datetime(2026, 4, 20, 15, 30, 0, tzinfo=timezone.utc)
        ticks = [
            ("FARTCOIN-USD", "2026-04-20T15:30:05", 0.200, 10.0),
            ("FARTCOIN-USD", "2026-04-20T15:30:17", 0.205, 5.0),
            ("FARTCOIN-USD", "2026-04-20T15:30:29", 0.199, 7.0),
            ("FARTCOIN-USD", "2026-04-20T15:30:50", 0.203, 3.0),
        ]
        _make_tape_db(tape_path, ticks)

        bar = _build_live_bar(tape_path, "FARTCOIN-USD", bucket_start)

        assert bar is not None
        assert bar["open"] == 0.200
        assert bar["high"] == 0.205
        assert bar["low"] == 0.199
        assert bar["close"] == 0.203
        assert bar["t"] == int(bucket_start.timestamp() * 1000)


def test_build_live_bar_returns_none_when_no_ticks():
    from dashboard.api.app import _build_live_bar

    with tempfile.TemporaryDirectory() as tmp:
        tape_path = os.path.join(tmp, "market_tape.db")
        _make_tape_db(tape_path, [])
        bucket_start = datetime(2026, 4, 20, 15, 30, 0, tzinfo=timezone.utc)

        bar = _build_live_bar(tape_path, "FARTCOIN-USD", bucket_start)
        assert bar is None


def test_build_live_bar_excludes_ticks_before_bucket_start():
    from dashboard.api.app import _build_live_bar

    with tempfile.TemporaryDirectory() as tmp:
        tape_path = os.path.join(tmp, "market_tape.db")
        bucket_start = datetime(2026, 4, 20, 15, 30, 0, tzinfo=timezone.utc)
        ticks = [
            # BEFORE bucket — must be ignored
            ("FARTCOIN-USD", "2026-04-20T15:29:55", 0.190, 10.0),
            # Inside bucket
            ("FARTCOIN-USD", "2026-04-20T15:30:05", 0.200, 10.0),
            ("FARTCOIN-USD", "2026-04-20T15:30:15", 0.202, 5.0),
        ]
        _make_tape_db(tape_path, ticks)

        bar = _build_live_bar(tape_path, "FARTCOIN-USD", bucket_start)
        assert bar["open"] == 0.200  # not 0.190
        assert bar["high"] == 0.202
        assert bar["low"] == 0.200
