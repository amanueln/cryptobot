"""Tests for SimRunner._restore_momentum_state peak/trough reconcile + trail recompute.

Motivated by commit 99bf76b (2026-04-18 AVNT incident): live 1Hz peak tracking
can miss intra-hour spikes that warmed 1h candles DO capture. On restart the
stale saved peak would otherwise cause the first post-restore tick to ratchet
the trail stop above current price and fire an immediate sell.

Scenarios exercised:
  - stale_saved_peak_reconciles_to_candle_high:   AVNT-style, reconcile kicks in
  - fresh_saved_peak_is_preserved:                  saved peak already >= candle max (no-op)
  - trail_stop_recomputed_from_reconciled_peak:   trail tier selection uses new peak
  - no_entry_time_skips_reconcile:                 defensive — malformed row doesn't crash
  - candle_high_before_entry_ignored:              only candles with ts >= entry count
"""
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest

from engine.momentum_engine import MomentumEngine


@pytest.fixture
def runner_and_db():
    """Build a SimRunner wired to a temp DB with the momentum_equity schema.

    Side-effect: patches runner.client.get_ticker_price so restore doesn't
    hit the network.
    """
    from sim_runner import SimRunner
    from data.trade_logger import TradeLogger

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create schema
    TradeLogger(db_path)  # __init__ runs CREATE TABLE IF NOT EXISTS

    runner = SimRunner()
    runner.trade_logger.db_path = db_path
    runner.client.get_ticker_price = lambda _pair: None  # skip network

    yield runner, db_path

    try:
        os.unlink(db_path)
    except OSError:
        pass


def _seed_engine_candles(engine: MomentumEngine, pair: str,
                         ts_start: datetime, highs: list[float],
                         lows: list[float] | None = None) -> None:
    """Populate the engine's warmed candle history for `pair` (1h cadence)."""
    if pair not in engine._closes:
        engine._closes[pair] = []
        engine._highs[pair] = []
        engine._lows[pair] = []
        engine._timestamps[pair] = []
        engine.pairs.append(pair)
    if lows is None:
        lows = [h - 0.001 for h in highs]
    for i, (hi, lo) in enumerate(zip(highs, lows)):
        engine._timestamps[pair].append(ts_start + timedelta(hours=i))
        engine._highs[pair].append(hi)
        engine._lows[pair].append(lo)
        # Seed a close equal to low so get_equity has something to read
        engine._closes[pair].append(lo)


def _write_equity_snapshot(db_path: str, pair: str, entry_price: float,
                           entry_time: datetime, saved_peak: float,
                           shares: float = 24000.0, saved_trail: float = 0.0,
                           saved_atr: float = 0.144) -> None:
    holdings = [{
        "pair": pair,
        "shares": shares,
        "entry_price": entry_price,
        "entry_time": entry_time.isoformat(),
        "peak_price": saved_peak,
        "current_price": saved_peak,
        "atr_stop_price": saved_atr,
        "trail_stop_price": saved_trail,
        "ticks_above_tighten": 0,
        "ticks_since_new_peak": 0,
    }]
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO momentum_equity (timestamp, equity, cash, positions_value, status, holdings) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), 3750.0, 38.0, 3712.0, "holding",
         json.dumps(holdings)),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------

def test_stale_saved_peak_reconciles_to_candle_high(runner_and_db):
    """AVNT-style: saved live peak lagged the true 1h candle high; restore
    must bump peak_price to match the real high so trail recompute is correct.
    """
    runner, db_path = runner_and_db
    pair = "AVNT-USD"
    entry_price = 0.1553
    entry_time = datetime(2026, 4, 18, 14, 0, 0)
    saved_peak = 0.156              # stale — from 1Hz ticks
    true_candle_high = 0.1705       # captured in the 16:00 hourly candle

    engine = MomentumEngine(allocation_usd=3000.0, pairs=[pair])
    runner.momentum_engine = engine

    # Hourly candle highs since entry: flat → spike to 0.1705 → fade
    _seed_engine_candles(
        engine, pair, entry_time,
        highs=[0.1555, 0.1650, true_candle_high, 0.1620, 0.1550, 0.1510],
    )

    _write_equity_snapshot(db_path, pair, entry_price, entry_time, saved_peak)

    assert runner._restore_momentum_state() is True

    holding = engine.holdings[pair]
    assert holding.peak_price == pytest.approx(true_candle_high), \
        "Reconcile should bump saved peak to match warmed candle high"


def test_fresh_saved_peak_is_preserved(runner_and_db):
    """Idempotency: if live peak is already >= every warmed candle high since
    entry, reconcile must leave peak_price untouched.
    """
    runner, db_path = runner_and_db
    pair = "ENA-USD"
    entry_price = 0.1206
    entry_time = datetime(2026, 4, 18, 18, 0, 0)
    saved_peak = 0.1250  # already above all candle highs below

    engine = MomentumEngine(allocation_usd=3000.0, pairs=[pair])
    runner.momentum_engine = engine

    _seed_engine_candles(
        engine, pair, entry_time,
        highs=[0.1210, 0.1215, 0.1220, 0.1218],
    )

    _write_equity_snapshot(db_path, pair, entry_price, entry_time, saved_peak)

    assert runner._restore_momentum_state() is True

    holding = engine.holdings[pair]
    assert holding.peak_price == pytest.approx(saved_peak), \
        "Fresh saved peak must not be overwritten by a lower candle max"


def test_trail_stop_recomputed_from_reconciled_peak(runner_and_db):
    """After reconcile, _update_trail_stop must produce a trail consistent with
    the new (higher) peak. Uses progressive tier: +8% peak → 1.5% trail.

    AVNT-style numbers:
        entry $0.1553, reconciled peak $0.1705 → peak_pct = +9.79%
        Triggered tiers: progressive (6.0, 2.0) and (8.0, 1.5)
        Expected stop = $0.1705 * (1 - 0.015) = $0.16794375
    """
    runner, db_path = runner_and_db
    pair = "AVNT-USD"
    entry_price = 0.1553
    entry_time = datetime(2026, 4, 18, 14, 0, 0)
    saved_peak = 0.156

    engine = MomentumEngine(allocation_usd=3000.0, pairs=[pair])
    runner.momentum_engine = engine

    _seed_engine_candles(
        engine, pair, entry_time,
        highs=[0.1555, 0.1650, 0.1705, 0.1620, 0.1550, 0.1510],
    )
    _write_equity_snapshot(db_path, pair, entry_price, entry_time, saved_peak)

    runner._restore_momentum_state()

    holding = engine.holdings[pair]
    expected_stop = 0.1705 * (1 - 0.015)  # progressive +8% tier
    assert holding.trail_stop_price == pytest.approx(expected_stop, rel=1e-4), \
        f"Trail stop should reflect +8% progressive tier off the reconciled peak"
    # Sanity: stop must sit below the reconciled peak and above entry (locked profit)
    assert entry_price < holding.trail_stop_price < holding.peak_price


def test_no_entry_time_skips_reconcile(runner_and_db):
    """Defensive: a malformed holdings row without entry_time must not crash;
    reconcile is skipped and saved peak is preserved.
    """
    runner, db_path = runner_and_db
    pair = "AVNT-USD"

    engine = MomentumEngine(allocation_usd=3000.0, pairs=[pair])
    runner.momentum_engine = engine

    # Write a row whose entry_time is missing (empty string)
    holdings = [{
        "pair": pair,
        "shares": 24000.0,
        "entry_price": 0.1553,
        "entry_time": "",          # <-- malformed
        "peak_price": 0.156,
        "current_price": 0.156,
        "atr_stop_price": 0.144,
        "trail_stop_price": 0.0,
        "ticks_above_tighten": 0,
        "ticks_since_new_peak": 0,
    }]
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO momentum_equity (timestamp, equity, cash, positions_value, status, holdings) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), 3750.0, 38.0, 3712.0, "holding",
         json.dumps(holdings)),
    )
    conn.commit()
    conn.close()

    # Should not raise — entry_time falls back to utcnow inside _restore
    assert runner._restore_momentum_state() is True
    assert pair in engine.holdings


def test_candle_high_before_entry_ignored(runner_and_db):
    """Reconcile must only scan candles whose ts >= entry_time. A historical
    spike from before the entry should not pollute peak_price.
    """
    runner, db_path = runner_and_db
    pair = "AVNT-USD"
    entry_price = 0.1553
    entry_time = datetime(2026, 4, 18, 14, 0, 0)
    saved_peak = 0.158

    engine = MomentumEngine(allocation_usd=3000.0, pairs=[pair])
    runner.momentum_engine = engine

    # Seed pre-entry candles with a big spike ($0.30), then post-entry with modest highs
    pre_entry_start = entry_time - timedelta(hours=3)
    for i, hi in enumerate([0.30, 0.28, 0.25]):
        engine._timestamps[pair].append(pre_entry_start + timedelta(hours=i))
        engine._highs[pair].append(hi)
        engine._lows[pair].append(hi - 0.01)
        engine._closes[pair].append(hi - 0.005)
    # Post-entry: all below saved_peak=$0.158
    for i, hi in enumerate([0.1560, 0.1570, 0.1565]):
        engine._timestamps[pair].append(entry_time + timedelta(hours=i))
        engine._highs[pair].append(hi)
        engine._lows[pair].append(hi - 0.001)
        engine._closes[pair].append(hi - 0.0005)

    _write_equity_snapshot(db_path, pair, entry_price, entry_time, saved_peak)

    runner._restore_momentum_state()

    holding = engine.holdings[pair]
    assert holding.peak_price == pytest.approx(saved_peak), \
        "Pre-entry spike must not be reconciled into peak_price"
