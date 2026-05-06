# tests/test_early_scanner_discord_gate.py
"""Tests for the strict Discord-notify gate added 2026-05-06.

Alerts are always saved to DB. Discord notification fires only when the
combo has total_alerts >= min_samples AND win_rate >= min_win_rate.
"""
import os
import sqlite3
import tempfile

from engine.early_scanner import EarlyScanner


def _scanner(db, min_wr=70.0, min_n=10):
    # webhook=None disables the actual HTTP call but the gate still runs.
    return EarlyScanner(
        db_path=db,
        discord_webhook=None,
        discord_min_combo_win_rate=min_wr,
        discord_min_combo_samples=min_n,
    )


def _seed_combo(db, combo_key, total_alerts, win_rate):
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO signal_combo_stats "
            "(combo_key, total_alerts, wins, avg_peak_pct, win_rate, score_adj, last_updated) "
            "VALUES (?, ?, ?, 0, ?, 0, '2026-05-06')",
            (combo_key, total_alerts, int(total_alerts * win_rate / 100), win_rate),
        )


def test_gate_blocks_unknown_combo():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        s = _scanner(db)
        allowed, reason = s._combo_passes_discord_gate("never_seen+combo")
        assert not allowed
        assert "no_track_record" in reason


def test_gate_blocks_missing_combo_key():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        s = _scanner(db)
        allowed, reason = s._combo_passes_discord_gate(None)
        assert not allowed
        assert "no_combo_key" in reason


def test_gate_blocks_insufficient_samples():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        s = _scanner(db, min_n=10)
        _seed_combo(db, "good+combo", total_alerts=5, win_rate=90.0)  # high WR but low n
        allowed, reason = s._combo_passes_discord_gate("good+combo")
        assert not allowed
        assert "insufficient_samples" in reason


def test_gate_blocks_low_win_rate():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        s = _scanner(db, min_wr=70.0)
        _seed_combo(db, "noisy+combo", total_alerts=50, win_rate=58.0)
        allowed, reason = s._combo_passes_discord_gate("noisy+combo")
        assert not allowed
        assert "58.0%" in reason and "70.0%" in reason


def test_gate_allows_proven_combo():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        s = _scanner(db, min_wr=70.0, min_n=10)
        _seed_combo(db, "winner+combo", total_alerts=50, win_rate=82.0)
        allowed, reason = s._combo_passes_discord_gate("winner+combo")
        assert allowed
        assert "82.0%" in reason


def test_gate_threshold_exact_match_passes():
    """win_rate exactly equal to threshold should pass (>=)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        s = _scanner(db, min_wr=70.0, min_n=10)
        _seed_combo(db, "edge+combo", total_alerts=10, win_rate=70.0)
        allowed, _reason = s._combo_passes_discord_gate("edge+combo")
        assert allowed


def test_gate_can_be_disabled_with_low_threshold():
    """Setting threshold to 0 + samples to 0 reverts to old loose behavior."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        db = os.path.join(d, "candles.db")
        s = _scanner(db, min_wr=0.0, min_n=0)
        _seed_combo(db, "any+combo", total_alerts=1, win_rate=10.0)
        allowed, _reason = s._combo_passes_discord_gate("any+combo")
        assert allowed
