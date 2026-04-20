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
            id INTEGER PRIMARY KEY,
            pair TEXT, ts TEXT, ts_epoch REAL,
            price REAL, size REAL, side TEXT
        )"""
    )
    rows = [
        (pair, ts, datetime.fromisoformat(ts).replace(tzinfo=timezone.utc).timestamp(),
         price, size)
        for (pair, ts, price, size) in ticks
    ]
    conn.executemany(
        "INSERT INTO ws_matches (pair, ts, ts_epoch, price, size, side) "
        "VALUES (?,?,?,?,?,'buy')",
        rows,
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


def _make_candles_db(path: str, candles: list[tuple[str, str, float, float, float, float, float]]) -> None:
    """candles: list of (pair, timestamp, open, high, low, close, volume). granularity='ONE_MINUTE'."""
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE candles (
            pair TEXT, granularity TEXT, timestamp TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL
        )"""
    )
    conn.executemany(
        "INSERT INTO candles (pair, granularity, timestamp, open, high, low, close, volume) "
        "VALUES (?, 'ONE_MINUTE', ?, ?, ?, ?, ?, ?)",
        candles,
    )
    conn.commit()
    conn.close()


def test_candles_live_returns_historical_and_live_bars(monkeypatch, tmp_path):
    from dashboard.api import app as app_mod

    candles_path = tmp_path / "candles.db"
    tape_path = tmp_path / "market_tape.db"

    # 3 historical 1m bars ending at 15:29
    _make_candles_db(str(candles_path), [
        ("FARTCOIN-USD", "2026-04-20T15:27:00", 0.195, 0.196, 0.194, 0.196, 100.0),
        ("FARTCOIN-USD", "2026-04-20T15:28:00", 0.196, 0.198, 0.195, 0.198, 120.0),
        ("FARTCOIN-USD", "2026-04-20T15:29:00", 0.198, 0.199, 0.197, 0.199, 90.0),
    ])
    # Live-forming bucket @ 15:30
    _make_tape_db(str(tape_path), [
        ("FARTCOIN-USD", "2026-04-20T15:30:05", 0.199, 10.0),
        ("FARTCOIN-USD", "2026-04-20T15:30:20", 0.201, 5.0),
    ])

    monkeypatch.setattr(app_mod, "DB_PATH", str(candles_path))
    # Freeze "now" at 15:30:25 so the current bucket is 15:30:00.
    frozen = datetime(2026, 4, 20, 15, 30, 25, tzinfo=timezone.utc)
    monkeypatch.setattr(app_mod, "_utcnow", lambda: frozen)

    client = app_mod.app.test_client()
    resp = client.get("/api/candles/live?pair=FARTCOIN-USD&tf=1m&limit=200")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["pair"] == "FARTCOIN-USD"
    assert data["tf"] == "1m"
    assert len(data["bars"]) == 3
    assert data["bars"][0]["close"] == 0.196
    assert data["bars"][-1]["close"] == 0.199

    live = data["live"]
    assert live is not None
    assert live["open"] == 0.199
    assert live["high"] == 0.201
    assert live["close"] == 0.201
