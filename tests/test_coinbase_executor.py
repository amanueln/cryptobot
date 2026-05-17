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
    """A MagicMock RESTClient that returns a 'success' shape on every call.

    Includes stub responses for the live API calls the executor makes during
    pre-flight (get_accounts, get_product). Without these, attribute access
    on a bare MagicMock returns truthy values (e.g. bool(MagicMock()) == True),
    which would falsely block every order in tests."""
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
    # Pre-flight 2 (product validation) calls get_product. Return a tradable
    # default; individual tests can override on the fake_client to simulate
    # halted/disabled/min-size-blocked products.
    client.get_product.return_value = {
        "status": "online",
        "trading_disabled": False,
        "is_disabled": False,
        "cancel_only": False,
        "view_only": False,
        "base_min_size": "0.0001",
        "quote_min_size": "1.00",
        "base_increment": "0.00000001",
        "quote_increment": "0.01",
        "price": "78000.00",
    }
    # Pre-flight 3 (preview_order) calls preview_market_order_buy. Return a
    # clean preview by default (empty errs). Tests that want to exercise the
    # rejection path can override .errs on the fake_client per-test.
    client.preview_market_order_buy.return_value = {
        "errs": [],
        "warning": [],
        "quote_size": "2.00",
        "base_size": "0.00002524",
        "est_average_filled_price": "78000.00",
        "commission_total": "0.024",
        "slippage": "0",
        "best_bid": "77995.00",
        "best_ask": "78005.00",
        "order_total": "2.024",
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


# --- order_id parsing (regression — smoke test caught this missing) ---

def test_buy_captures_coinbase_order_id_from_nested_success_response(db_path, fake_client):
    """Live SDK response nests order_id under success_response, not top-level.
    Our code must read both for forward-compat."""
    fake_client.market_order_buy.return_value = {
        "success": True,
        "success_response": {
            "order_id": "abcd-1234",
            "client_order_id": "bot-xyz",
            "product_id": "BTC-USD",
        },
        "order_configuration": {},
    }
    ex = _enabled_executor(db_path, fake_client)
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=2.0)
    assert r.ok is True
    assert r.coinbase_order_id == "abcd-1234"
    with sqlite3.connect(db_path) as conn:
        cb_id = conn.execute(
            "SELECT coinbase_order_id FROM live_orders ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    assert cb_id == "abcd-1234"


def test_buy_captures_coinbase_order_id_from_top_level_fallback(db_path, fake_client):
    """Older SDK versions may put order_id at the top level. Don't lose it."""
    fake_client.market_order_buy.return_value = {
        "success": True,
        "order_id": "old-shape-id",
        "success_response": {},
    }
    ex = _enabled_executor(db_path, fake_client)
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=2.0)
    assert r.coinbase_order_id == "old-shape-id"


def test_buy_rejected_with_nested_error_response(db_path, fake_client):
    """Failure shape: 'error_response' has 'error_details' or 'message'."""
    fake_client.market_order_buy.return_value = {
        "success": False,
        "error_response": {"error_details": "PREVIEW_INSUFFICIENT_FUNDS"},
        "failure_reason": "INSUFFICIENT_FUNDS",
    }
    ex = _enabled_executor(db_path, fake_client)
    r = ex.submit_market_buy("BTC-USD", quote_size_usd=2.0)
    assert r.ok is False
    assert "PREVIEW_INSUFFICIENT_FUNDS" in r.detail


# --- wait_for_fill ---

def test_wait_for_fill_returns_filled_state(db_path, fake_client):
    fake_client.get_order.return_value = {
        "order": {
            "status": "FILLED",
            "filled_size": "0.00002524",
            "average_filled_price": "78029.64",
            "total_fees": "0.0236",
        }
    }
    ex = _enabled_executor(db_path, fake_client)
    out = ex.wait_for_fill("some-order-id", timeout_sec=1, poll_interval_sec=0.01)
    assert out["filled"] is True
    assert out["status"] == "FILLED"
    assert out["filled_size"] == pytest.approx(0.00002524)
    assert out["avg_price"] == pytest.approx(78029.64)
    assert out["fee_usd"] == pytest.approx(0.0236)
    assert out["notional_usd"] == pytest.approx(0.00002524 * 78029.64)


def test_wait_for_fill_handles_cancelled(db_path, fake_client):
    fake_client.get_order.return_value = {
        "order": {"status": "CANCELLED", "filled_size": "0", "average_filled_price": "0", "total_fees": "0"}
    }
    ex = _enabled_executor(db_path, fake_client)
    out = ex.wait_for_fill("x", timeout_sec=1, poll_interval_sec=0.01)
    assert out["filled"] is False
    assert out["status"] == "CANCELLED"


def test_wait_for_fill_times_out_when_still_pending(db_path, fake_client):
    fake_client.get_order.return_value = {
        "order": {"status": "PENDING", "filled_size": "0", "average_filled_price": "0", "total_fees": "0"}
    }
    ex = _enabled_executor(db_path, fake_client)
    out = ex.wait_for_fill("x", timeout_sec=0.5, poll_interval_sec=0.1)
    assert out["filled"] is False
    assert out["status"] == "PENDING"


def test_wait_for_fill_returns_error_when_no_order_id(db_path, fake_client):
    ex = _enabled_executor(db_path, fake_client)
    out = ex.wait_for_fill("", timeout_sec=1)
    assert out["filled"] is False
    assert "no_coinbase_order_id" in (out["error"] or "")


# --- Pair allowlist wildcard ---

def test_pair_allow_all_via_wildcard_kwarg(db_path, fake_client, monkeypatch):
    """pair_allowlist=['*'] means trust whatever the strategy picks."""
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    ex = CoinbaseExecutor(db_path=db_path, client=fake_client, pair_allowlist=["*"])
    # Any pair, even one we've never heard of
    r = ex.submit_market_buy("RANDOMCOIN-USD", quote_size_usd=2.0)
    assert r.ok is True
    assert ex.pair_allow_all is True
    assert ex.pair_allowlist == set()  # the '*' is consumed, no concrete pairs


def test_pair_allow_all_via_env_var(db_path, fake_client, monkeypatch):
    """LIVE_PAIR_ALLOWLIST=* env var sets wildcard mode."""
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    monkeypatch.setenv("LIVE_PAIR_ALLOWLIST", "*")
    ex = CoinbaseExecutor(db_path=db_path, client=fake_client)
    assert ex.pair_allow_all is True
    r = ex.submit_market_buy("OBSCURECOIN-USD", quote_size_usd=2.0)
    assert r.ok is True


def test_pair_allowlist_with_wildcard_plus_extras_still_allows_all(db_path, fake_client, monkeypatch):
    """If '*' is mixed with concrete pairs, wildcard wins (allow_all=True)."""
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    ex = CoinbaseExecutor(db_path=db_path, client=fake_client,
                          pair_allowlist=["BTC-USD", "*", "ETH-USD"])
    assert ex.pair_allow_all is True
    r = ex.submit_market_buy("DOGE-USD", quote_size_usd=2.0)
    assert r.ok is True


def test_pair_allow_all_still_honors_other_gates(db_path, fake_client, monkeypatch):
    """Wildcard only bypasses the pair check — not size/exposure/kill switch."""
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    ex = CoinbaseExecutor(db_path=db_path, client=fake_client, pair_allowlist=["*"],
                          max_order_usd=10.0)
    r = ex.submit_market_buy("DOGE-USD", quote_size_usd=999.0)
    assert r.ok is False
    assert "blocked_order_too_large" in r.reason


def test_sell_allows_all_pairs_in_wildcard_mode(db_path, fake_client, monkeypatch):
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    ex = CoinbaseExecutor(db_path=db_path, client=fake_client, pair_allowlist=["*"])
    r = ex.submit_market_sell("UNKNOWN-USD", base_size=0.001)
    assert r.ok is True


def test_no_wildcard_still_blocks_unlisted(db_path, fake_client, monkeypatch):
    """Sanity: when no wildcard is set, an unlisted pair is still blocked."""
    monkeypatch.setenv("LIVE_TRADING_ENABLED", "true")
    ex = CoinbaseExecutor(db_path=db_path, client=fake_client,
                          pair_allowlist=["BTC-USD"])
    assert ex.pair_allow_all is False
    r = ex.submit_market_buy("DOGE-USD", quote_size_usd=2.0)
    assert r.ok is False
    assert "blocked_pair_not_allowlisted" in r.reason
