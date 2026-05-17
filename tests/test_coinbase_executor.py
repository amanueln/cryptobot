"""Tests for CoinbaseExecutor — guardrails, idempotency, persistence.

The real Coinbase RESTClient is mocked. No network calls, no real orders.
"""
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock

import pytest

from engine.coinbase_executor import CoinbaseExecutor, OrderResult
from engine.live_schema import init_schema


# ---------------------------------------------------------------- fixtures ----

@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "candles.db")
    init_schema(p)
    return p


@pytest.fixture
def fake_client():
    """A MagicMock RESTClient that returns a 'success' shape on every call."""
    client = MagicMock()
    client.market_order_buy.return_value = {
        "success": True,
        "order_id": "coinbase-order-abc123",
        "success_response": {},
    }
    client.market_order_sell.return_value = {
        "success": True,
        "order_id": "coinbase-order-def456",
        "success_response": {},
    }
    client.get_accounts.return_value = {
        "accounts": [
            {"currency": "USD", "available_balance": {"value": "293.73"}},
            {"currency": "BTC", "available_balance": {"value": "0.001"}},
        ]
    }
    return client


def _enabled_executor(db_path, fake_client, **kwargs):
    """Construct an executor with LIVE_TRADING_ENABLED=true for the duration
    of the test. Always passes pair_allowlist explicitly so we don't rely on env."""
    os.environ["LIVE_TRADING_ENABLED"] = "true"
    return CoinbaseExecutor(
        db_path=db_path, client=fake_client,
        pair_allowlist=kwargs.pop("pair_allowlist", ["BTC-USD", "ETH-USD"]),
        **kwargs,
    )


# ----------------------------------------------------------------------- tests

def test_is_live_enabled_off_by_default(db_path, fake_client, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    ex = CoinbaseExecutor(db_path=db_path, client=fake_client, pair_allowlist=["BTC-USD"])
    ok, why = ex.is_live_enabled()
    assert ok is False
    assert "LIVE_TRADING_ENABLED" in why


def test_buy_blocked_when_disabled(db_path, fake_client, monkeypatch):
    monkeypatch.delenv("LIVE_TRADING_ENABLED", raising=False)
    ex = CoinbaseExecutor(db_path=db_path, client=fake_client, pair_allowlist=["BTC-USD"])
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=10.0)
    assert r.ok is False
    assert "blocked_disabled" in r.reason
    fake_client.market_order_buy.assert_not_called()


def test_buy_blocked_when_pair_not_allowlisted(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client, pair_allowlist=["ETH-USD"])
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=10.0)
    assert r.ok is False
    assert "blocked_pair_not_allowlisted" in r.reason
    fake_client.market_order_buy.assert_not_called()


def test_buy_blocked_when_order_too_large(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client, max_order_usd=50.0)
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=100.0)
    assert r.ok is False
    assert "blocked_order_too_large" in r.reason
    fake_client.market_order_buy.assert_not_called()


def test_buy_records_rejection_to_live_orders(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client, max_order_usd=10.0)
    ex.submit_market_buy("BTC-USD", quote_size_usd=999.0, intent="entry", strategy="momentum")
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT pair, side, quote_size, intent, strategy, result_status, result_message "
            "FROM live_orders ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row[0] == "BTC-USD"
    assert row[1] == "buy"
    assert row[2] == 999.0
    assert row[3] == "entry"
    assert row[4] == "momentum"
    assert row[5] == "rejected"
    assert "blocked_order_too_large" in row[6]


def test_buy_happy_path_calls_sdk_and_records_submission(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client, max_order_usd=300.0)
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=2.0,
                              intent="smoke_test", strategy="smoke")
    assert r.ok is True
    assert r.reason == "submitted"
    assert r.coinbase_order_id == "coinbase-order-abc123"
    fake_client.market_order_buy.assert_called_once()
    call_kwargs = fake_client.market_order_buy.call_args.kwargs
    assert call_kwargs["product_id"] == "BTC-USD"
    assert call_kwargs["quote_size"] == "2.00"
    assert call_kwargs["client_order_id"].startswith("bot-")
    # Row recorded
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT pair, side, quote_size, intent, coinbase_order_id, result_status "
            "FROM live_orders ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row == ("BTC-USD", "buy", 2.0, "smoke_test", "coinbase-order-abc123", "submitted")


def test_buy_rejected_by_coinbase_records_rejection(db_path, fake_client, monkeypatch):
    fake_client.market_order_buy.return_value = {
        "success": False,
        "order_id": None,
        "failure_reason": "INSUFFICIENT_FUNDS",
    }
    ex = _enabled_executor(db_path, fake_client)
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=10.0)
    assert r.ok is False
    assert r.reason == "rejected"
    assert "INSUFFICIENT_FUNDS" in r.detail
    with sqlite3.connect(db_path) as conn:
        status = conn.execute("SELECT result_status FROM live_orders ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert status == "rejected"


def test_buy_sdk_exception_recorded_as_error_not_raised(db_path, fake_client, monkeypatch):
    fake_client.market_order_buy.side_effect = RuntimeError("network unreachable")
    ex = _enabled_executor(db_path, fake_client)
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=10.0)
    assert r.ok is False
    assert r.reason == "error"
    assert "network unreachable" in r.detail
    with sqlite3.connect(db_path) as conn:
        status, msg = conn.execute(
            "SELECT result_status, result_message FROM live_orders ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert status == "error"
    assert "network unreachable" in msg


def test_exposure_cap_blocks_buy_when_at_limit(db_path, fake_client, monkeypatch):
    # Pre-seed a position taking up the full $300 cap
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO live_positions (pair, entry_ts, entry_price, entry_notional_usd, "
            "  amount, fees_paid_usd, strategy, created_at, updated_at) "
            "VALUES ('ETH-USD', '2026-05-17T00:00:00+00:00', 3000.0, 300.0, 0.1, 1.8, "
            "  'momentum', '2026-05-17T00:00:00+00:00', '2026-05-17T00:00:00+00:00')"
        )
    ex = _enabled_executor(db_path, fake_client, max_exposure_usd=300.0)
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=10.0)
    assert r.ok is False
    assert "blocked_exposure_cap" in r.reason
    fake_client.market_order_buy.assert_not_called()


def test_kill_switch_blocks_orders(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client)
    ex.trip_kill_switch("daily_loss_cap_hit")
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=10.0)
    assert r.ok is False
    assert "blocked_paused" in r.reason
    assert "daily_loss_cap_hit" in r.reason


def test_kill_switch_reset_re_enables_orders(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client)
    ex.trip_kill_switch("test")
    ex.reset_kill_switch()
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=10.0)
    assert r.ok is True


def test_sell_basic_happy_path(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client)
    r = ex.submit_market_sell("BTC-USD", base_size=0.0001, intent="exit", strategy="momentum")
    assert r.ok is True
    fake_client.market_order_sell.assert_called_once()
    call_kwargs = fake_client.market_order_sell.call_args.kwargs
    assert call_kwargs["product_id"] == "BTC-USD"
    assert call_kwargs["base_size"] == "0.0001"


def test_sell_blocked_when_pair_not_allowlisted(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client, pair_allowlist=["ETH-USD"])
    r = ex.submit_market_sell("BTC-USD", base_size=0.0001)
    assert r.ok is False
    assert "blocked_pair_not_allowlisted" in r.reason


def test_rate_limit_blocks_after_N(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client, rate_limit_n=3, rate_limit_window_sec=60)
    # 3 buys should pass
    for _ in range(3):
        r = ex.submit_market_buy("BTC-USD", quote_size_usd=1.0)
        assert r.ok is True
    # 4th should be rate-limited
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=1.0)
    assert r.ok is False
    assert "blocked_rate_limit" in r.reason


def test_get_usd_cash_reads_from_coinbase(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client)
    assert ex.get_usd_cash() == 293.73


def test_get_crypto_balance_reads_from_coinbase(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client)
    assert ex.get_crypto_balance("BTC") == 0.001
    assert ex.get_crypto_balance("MISSING") == 0.0


def test_pause_auto_resumes_after_until_ts(db_path, fake_client, monkeypatch):
    from datetime import datetime, timedelta, timezone
    ex = _enabled_executor(db_path, fake_client)
    past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    ex.trip_kill_switch("test", until_ts=past)
    paused, _why = ex.is_paused()
    assert paused is False  # already expired


def test_check_can_place_order_combines_all_gates(db_path, fake_client, monkeypatch):
    ex = _enabled_executor(db_path, fake_client, max_order_usd=10.0)
    ok, _ = ex.check_can_place_order("BTC-USD", 5.0)
    assert ok is True
    ok, why = ex.check_can_place_order("BTC-USD", 50.0)
    assert ok is False
    assert "blocked_order_too_large" in why
    ok, why = ex.check_can_place_order("DOGE-USD", 5.0)
    assert ok is False
    assert "blocked_pair_not_allowlisted" in why
