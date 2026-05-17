"""Tests for MomentumEngine's LIVE-mode branching (executor injected).

These tests use a MagicMock executor; no Coinbase calls happen. They verify
the wiring between MomentumEngine._buy / _sell and CoinbaseExecutor:

  - Init reconciles cash from executor.get_usd_cash()
  - _buy routes through executor.submit_market_buy + wait_for_fill
  - _buy uses ACTUAL fill numbers (not candle close) for the holding
  - Rejected / unfilled buys don't update internal state
  - _sell routes through executor.submit_market_sell + wait_for_fill
  - Failed sells keep the holding (so we retry next tick)
  - Live trades / positions get written to live_trades / live_positions
"""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from engine.live_schema import init_schema
from engine.momentum_engine import MomentumEngine


# ----------------------------------------------------------------- fixtures


@pytest.fixture
def live_db(tmp_path):
    p = str(tmp_path / "live.db")
    init_schema(p)
    return p


@pytest.fixture
def fake_executor():
    """A MagicMock executor that simulates a clean fill on every call."""
    ex = MagicMock()
    ex.get_usd_cash.return_value = 293.73

    # buy returns OrderResult-like
    buy_result = MagicMock()
    buy_result.ok = True
    buy_result.reason = "submitted"
    buy_result.local_order_id = 1
    buy_result.coinbase_order_id = "cb-buy-id"
    buy_result.detail = ""
    ex.submit_market_buy.return_value = buy_result

    sell_result = MagicMock()
    sell_result.ok = True
    sell_result.reason = "submitted"
    sell_result.local_order_id = 2
    sell_result.coinbase_order_id = "cb-sell-id"
    sell_result.detail = ""
    ex.submit_market_sell.return_value = sell_result

    # wait_for_fill returns a filled dict by default
    ex.wait_for_fill.return_value = {
        "filled": True, "status": "FILLED",
        "filled_size": 0.05, "avg_price": 40.0,
        "fee_usd": 0.012, "notional_usd": 2.0, "error": None,
    }
    return ex


def _build_engine(executor, live_db_path, alloc=300.0):
    """Construct a MomentumEngine in LIVE mode with one tracked pair (BTC-USD).
    Pre-seeds enough candle history that ATR + entry stop calc don't crash."""
    engine = MomentumEngine(
        allocation_usd=alloc, fee_rate=0.012,
        pairs=["BTC-USD"],
        executor=executor, live_db_path=live_db_path,
    )
    # Seed minimal candle history so _buy / _sell can read self._closes[-1]
    # and ATR can compute. Just need len >= ATR_STOP_LOOKBACK candles.
    base_price = 40.0
    for i in range(50):
        engine._closes["BTC-USD"].append(base_price + i * 0.01)
        engine._opens["BTC-USD"].append(base_price + i * 0.01)
        engine._highs["BTC-USD"].append(base_price + i * 0.01 + 0.1)
        engine._lows["BTC-USD"].append(base_price + i * 0.01 - 0.1)
        engine._timestamps["BTC-USD"].append(datetime.now(timezone.utc))
    return engine


# ----------------------------------------------------------------- tests


def test_init_reconciles_cash_from_executor(live_db, fake_executor):
    """In live mode, self.cash should reflect Coinbase USD balance (capped at alloc)."""
    fake_executor.get_usd_cash.return_value = 293.73
    engine = MomentumEngine(allocation_usd=300.0, fee_rate=0.012,
                            pairs=["BTC-USD"],
                            executor=fake_executor, live_db_path=live_db)
    assert engine.cash == 293.73
    fake_executor.get_usd_cash.assert_called_once()


def test_init_caps_cash_at_allocation_even_when_coinbase_has_more(live_db, fake_executor):
    """If the connected portfolio has $1000 but we said alloc=$300, we cap at $300."""
    fake_executor.get_usd_cash.return_value = 1000.0
    engine = MomentumEngine(allocation_usd=300.0, fee_rate=0.012,
                            pairs=["BTC-USD"],
                            executor=fake_executor, live_db_path=live_db)
    assert engine.cash == 300.0


def test_init_falls_back_to_alloc_when_reconcile_raises(live_db, fake_executor):
    """If get_usd_cash blows up, we don't crash — start at alloc."""
    fake_executor.get_usd_cash.side_effect = RuntimeError("network")
    engine = MomentumEngine(allocation_usd=300.0, fee_rate=0.012,
                            pairs=["BTC-USD"],
                            executor=fake_executor, live_db_path=live_db)
    assert engine.cash == 300.0


def test_buy_routes_through_executor_in_live_mode(live_db, fake_executor):
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)

    trade = engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test")

    assert trade is not None
    fake_executor.submit_market_buy.assert_called_once()
    call_kwargs = fake_executor.submit_market_buy.call_args.kwargs
    assert call_kwargs["quote_size_usd"] == 2.0
    assert call_kwargs["intent"] == "entry"
    fake_executor.wait_for_fill.assert_called_once_with("cb-buy-id", timeout_sec=25)


def test_buy_uses_actual_fill_data_not_candle_close(live_db, fake_executor):
    """The holding's entry_price + shares should match the fill, not self._closes[-1]."""
    # Last close is 40.49 (from _build_engine's seed loop), but fill says 40.00 / 0.05 BTC
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)
    fake_executor.wait_for_fill.return_value = {
        "filled": True, "status": "FILLED",
        "filled_size": 0.05, "avg_price": 38.50,  # deliberately different from candle close
        "fee_usd": 0.023, "notional_usd": 1.925, "error": None,
    }
    engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test")

    holding = engine.holdings["BTC-USD"]
    assert holding.entry_price == 38.50  # NOT the candle close
    assert holding.shares == 0.05
    # cash debited by actual notional + fee, not nominal $2
    expected_cash = 293.73 - (1.925 + 0.023)
    assert engine.cash == pytest.approx(expected_cash, abs=0.001)


def test_buy_rejected_doesnt_create_holding(live_db, fake_executor):
    fake_executor.submit_market_buy.return_value = MagicMock(
        ok=False, reason="rejected", detail="INSUFFICIENT_FUNDS",
        local_order_id=1, coinbase_order_id=None,
    )
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)
    cash_before = engine.cash

    trade = engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test")

    assert trade is None
    assert "BTC-USD" not in engine.holdings
    assert engine.cash == cash_before  # untouched
    # wait_for_fill should NOT have been called (we bailed before)
    fake_executor.wait_for_fill.assert_not_called()


def test_buy_unfilled_doesnt_create_holding(live_db, fake_executor):
    fake_executor.wait_for_fill.return_value = {
        "filled": False, "status": "PENDING",
        "filled_size": 0, "avg_price": 0, "fee_usd": 0, "notional_usd": 0,
        "error": None,
    }
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)
    cash_before = engine.cash

    trade = engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test")

    assert trade is None
    assert "BTC-USD" not in engine.holdings
    assert engine.cash == cash_before


def test_buy_records_to_live_trades_table(live_db, fake_executor):
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)
    engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test_entry")

    with sqlite3.connect(live_db) as conn:
        row = conn.execute(
            "SELECT pair, side, fill_price, fill_size, fee_usd, notional_usd, intent, strategy "
            "FROM live_trades ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row == ("BTC-USD", "buy", 40.0, 0.05, 0.012, 2.0, "entry", "momentum_rotation")


def test_buy_records_to_live_positions_table(live_db, fake_executor):
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)
    engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test_entry")

    with sqlite3.connect(live_db) as conn:
        row = conn.execute(
            "SELECT pair, entry_price, amount, strategy FROM live_positions"
        ).fetchone()
    assert row[0] == "BTC-USD"
    assert row[1] == 40.0
    assert row[2] == 0.05
    assert row[3] == "momentum_rotation"


def test_sell_routes_through_executor_in_live_mode(live_db, fake_executor):
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)
    # Open a position first
    engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test")
    fake_executor.submit_market_buy.reset_mock()
    fake_executor.wait_for_fill.reset_mock()
    # Now sell — wait_for_fill default returns a successful sell fill too
    fake_executor.wait_for_fill.return_value = {
        "filled": True, "status": "FILLED",
        "filled_size": 0.05, "avg_price": 41.0,
        "fee_usd": 0.025, "notional_usd": 2.05, "error": None,
    }
    trade = engine._sell("BTC-USD", timestamp=ts, reason="test_exit")

    assert trade is not None
    fake_executor.submit_market_sell.assert_called_once()
    call_kwargs = fake_executor.submit_market_sell.call_args.kwargs
    assert call_kwargs["base_size"] == 0.05  # the held amount
    assert call_kwargs["intent"] == "exit"


def test_sell_rejected_keeps_holding(live_db, fake_executor):
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)
    engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test")
    # Sell will fail
    fake_executor.submit_market_sell.return_value = MagicMock(
        ok=False, reason="rejected", detail="ALLOWANCE_EXCEEDED",
        local_order_id=99, coinbase_order_id=None,
    )

    cash_before = engine.cash
    trade = engine._sell("BTC-USD", timestamp=ts, reason="test_exit")

    assert trade is None
    assert "BTC-USD" in engine.holdings, "holding must persist when sell rejects"
    assert engine.cash == cash_before  # didn't credit anything


def test_sell_unfilled_keeps_holding(live_db, fake_executor):
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)
    engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test")
    fake_executor.wait_for_fill.return_value = {
        "filled": False, "status": "PENDING",
        "filled_size": 0, "avg_price": 0, "fee_usd": 0, "notional_usd": 0,
        "error": None,
    }

    cash_before = engine.cash
    trade = engine._sell("BTC-USD", timestamp=ts, reason="test_exit")

    assert trade is None
    assert "BTC-USD" in engine.holdings
    assert engine.cash == cash_before


def test_sell_closes_live_position_row(live_db, fake_executor):
    engine = _build_engine(fake_executor, live_db)
    ts = datetime.now(timezone.utc)
    engine._buy("BTC-USD", amount_usd=2.0, timestamp=ts, reason="test")
    # Position row should exist
    with sqlite3.connect(live_db) as conn:
        n_before = conn.execute("SELECT COUNT(*) FROM live_positions").fetchone()[0]
    assert n_before == 1

    fake_executor.wait_for_fill.return_value = {
        "filled": True, "status": "FILLED",
        "filled_size": 0.05, "avg_price": 41.0,
        "fee_usd": 0.025, "notional_usd": 2.05, "error": None,
    }
    engine._sell("BTC-USD", timestamp=ts, reason="test_exit")

    with sqlite3.connect(live_db) as conn:
        n_after = conn.execute("SELECT COUNT(*) FROM live_positions").fetchone()[0]
    assert n_after == 0, "live_positions row should be deleted on successful sell"


def test_paper_mode_unchanged_no_executor(live_db, fake_executor):
    """Sanity: passing executor=None keeps the original paper-mode behavior."""
    engine = MomentumEngine(allocation_usd=3000.0, fee_rate=0.012,
                            pairs=["BTC-USD"],
                            executor=None, live_db_path=None)
    # Cash equals allocation, no Coinbase calls
    assert engine.cash == 3000.0
    fake_executor.get_usd_cash.assert_not_called()
