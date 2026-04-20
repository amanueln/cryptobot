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


def test_candles_live_aggregates_5m_from_1m(monkeypatch, tmp_path):
    from dashboard.api import app as app_mod

    candles_path = tmp_path / "candles.db"
    tape_path = tmp_path / "market_tape.db"

    # 10 minutes of 1m bars: two complete 5m buckets (15:20-15:24 and 15:25-15:29),
    # plus an in-progress 15:30 bucket via ws_matches.
    _make_candles_db(str(candles_path), [
        ("F-USD", "2026-04-20T15:20:00", 1.00, 1.02, 0.99, 1.01, 1.0),
        ("F-USD", "2026-04-20T15:21:00", 1.01, 1.03, 1.00, 1.02, 1.0),
        ("F-USD", "2026-04-20T15:22:00", 1.02, 1.04, 1.01, 1.03, 1.0),
        ("F-USD", "2026-04-20T15:23:00", 1.03, 1.05, 1.02, 1.04, 1.0),
        ("F-USD", "2026-04-20T15:24:00", 1.04, 1.06, 1.03, 1.05, 1.0),
        ("F-USD", "2026-04-20T15:25:00", 1.05, 1.07, 1.04, 1.06, 1.0),
        ("F-USD", "2026-04-20T15:26:00", 1.06, 1.08, 1.05, 1.07, 1.0),
        ("F-USD", "2026-04-20T15:27:00", 1.07, 1.09, 1.06, 1.08, 1.0),
        ("F-USD", "2026-04-20T15:28:00", 1.08, 1.10, 1.07, 1.09, 1.0),
        ("F-USD", "2026-04-20T15:29:00", 1.09, 1.11, 1.08, 1.10, 1.0),
    ])
    _make_tape_db(str(tape_path), [
        ("F-USD", "2026-04-20T15:30:10", 1.10, 1.0),
        ("F-USD", "2026-04-20T15:30:20", 1.12, 1.0),
    ])

    monkeypatch.setattr(app_mod, "DB_PATH", str(candles_path))
    frozen = datetime(2026, 4, 20, 15, 30, 25, tzinfo=timezone.utc)
    monkeypatch.setattr(app_mod, "_utcnow", lambda: frozen)

    client = app_mod.app.test_client()
    resp = client.get("/api/candles/live?pair=F-USD&tf=5m&limit=50")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["tf"] == "5m"
    assert len(data["bars"]) == 2

    # First bucket: 15:20 open=1.00, max high=1.06, min low=0.99, close=1.05
    b0 = data["bars"][0]
    assert b0["open"] == 1.00
    assert b0["high"] == 1.06
    assert b0["low"] == 0.99
    assert b0["close"] == 1.05

    # Second bucket: 15:25 open=1.05, close=1.10
    b1 = data["bars"][1]
    assert b1["open"] == 1.05
    assert b1["close"] == 1.10

    # Live bucket built from ws_matches @ 15:30
    assert data["live"]["open"] == 1.10
    assert data["live"]["close"] == 1.12
