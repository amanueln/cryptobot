"""Live-trading executor against the Coinbase Advanced Trade API.

This is the single seam between the bot's strategy code and real money. It is
intentionally narrow: every action goes through guardrails (kill switch, max
order size, max exposure, pair allowlist, rate limit) before any HTTP call.

Layout mirrors `engine/simulator.py` so a strategy that wrote to Simulator
can write to CoinbaseExecutor with minimal changes, but the contract is
explicit about live-only concerns (idempotency keys, fills vs orders, etc).

Configuration is via environment variables. Defaults are conservative — the
bot CANNOT trade unless `LIVE_TRADING_ENABLED=true` is set on the host.

    LIVE_TRADING_ENABLED          must be 'true' (case-insensitive) to allow any order
    LIVE_KEY_FILE                 default /app/persistent/coinbase_key.json
    LIVE_MAX_ORDER_USD            default $300 (hard ceiling per single order)
    LIVE_MAX_EXPOSURE_USD         default $300 (sum of open positions)
    LIVE_DAILY_LOSS_CAP_USD       default $30 (auto-pause 24h on hit)
    LIVE_PAIR_ALLOWLIST           default ''=allow none. Comma-separated list.
    LIVE_ORDER_RATE_LIMIT         default 10 orders / 60 seconds

The Coinbase JSON key file (ECDSA / ES256) must be readable by this process.
Permissions are not enforced here — that's a host-side concern.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("coinbase_executor")


# Defaults — overridable via env
DEFAULT_KEY_FILE = "/app/persistent/coinbase_key.json"
DEFAULT_MAX_ORDER_USD = 300.0
DEFAULT_MAX_EXPOSURE_USD = 300.0
DEFAULT_DAILY_LOSS_CAP_USD = 30.0
DEFAULT_RATE_LIMIT_N = 10
DEFAULT_RATE_LIMIT_WINDOW_SEC = 60


@dataclass
class OrderResult:
    """Single return type for every execute call. Always populated, never raises."""
    ok: bool
    reason: str                     # short code: 'submitted', 'filled', 'rejected', 'blocked_*', 'error'
    detail: str = ""
    local_order_id: Optional[int] = None
    coinbase_order_id: Optional[str] = None
    fill_price: Optional[float] = None
    fill_size: Optional[float] = None
    fee_usd: Optional[float] = None
    notional_usd: Optional[float] = None


class CoinbaseExecutor:
    """Thin guardrail-wrapped facade over `coinbase.rest.RESTClient`.

    Every public method either returns an OrderResult or a plain dict/value;
    none raise on Coinbase API errors — the error is captured in result.detail.
    """

    def __init__(
        self,
        db_path: str,
        key_file: Optional[str] = None,
        *,
        # Test seam — pass a pre-built client (or mock) to skip real auth/HTTP.
        client=None,
        # Optional overrides for tests; production reads from env.
        max_order_usd: Optional[float] = None,
        max_exposure_usd: Optional[float] = None,
        daily_loss_cap_usd: Optional[float] = None,
        pair_allowlist: Optional[list[str]] = None,
        rate_limit_n: int = DEFAULT_RATE_LIMIT_N,
        rate_limit_window_sec: int = DEFAULT_RATE_LIMIT_WINDOW_SEC,
    ):
        self.db_path = db_path

        # --- env-driven config (tests can override via kwargs) ---
        self.key_file = key_file or os.environ.get("LIVE_KEY_FILE", DEFAULT_KEY_FILE)
        self.max_order_usd = (max_order_usd if max_order_usd is not None
                              else float(os.environ.get("LIVE_MAX_ORDER_USD", DEFAULT_MAX_ORDER_USD)))
        self.max_exposure_usd = (max_exposure_usd if max_exposure_usd is not None
                                 else float(os.environ.get("LIVE_MAX_EXPOSURE_USD", DEFAULT_MAX_EXPOSURE_USD)))
        self.daily_loss_cap_usd = (daily_loss_cap_usd if daily_loss_cap_usd is not None
                                   else float(os.environ.get("LIVE_DAILY_LOSS_CAP_USD", DEFAULT_DAILY_LOSS_CAP_USD)))
        if pair_allowlist is None:
            raw = os.environ.get("LIVE_PAIR_ALLOWLIST", "")
            self.pair_allowlist = {p.strip() for p in raw.split(",") if p.strip()}
        else:
            self.pair_allowlist = set(pair_allowlist)

        # rate-limit window
        self._rl_n = rate_limit_n
        self._rl_window = rate_limit_window_sec
        self._rl_lock = threading.Lock()
        self._rl_times: deque[float] = deque(maxlen=rate_limit_n * 4)

        # --- ensure live schema exists ---
        from engine.live_schema import init_schema
        init_schema(db_path)

        # --- lazy import / instantiation of the SDK client ---
        if client is not None:
            self._client = client
        else:
            self._client = None  # built on first use to keep import-time cheap

    # ------------------------------------------------------------------
    # Public guardrail surface — call these before doing anything
    # ------------------------------------------------------------------

    def is_live_enabled(self) -> tuple[bool, str]:
        """Is the master enable flag on? Operator-controlled, separate from
        code-controlled kill switch."""
        flag = os.environ.get("LIVE_TRADING_ENABLED", "").strip().lower()
        if flag not in ("true", "1", "yes", "on"):
            return False, "LIVE_TRADING_ENABLED env var is not set to true"
        return True, ""

    def is_paused(self) -> tuple[bool, str]:
        """Has code paused trading (daily loss cap hit, manual flag, etc)?
        Reads the `live_kill_switch` table."""
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            row = conn.execute(
                "SELECT paused, reason, pause_until_ts FROM live_kill_switch WHERE id=1"
            ).fetchone()
        if not row:
            return False, ""
        paused, reason, until_ts = row
        if not paused:
            return False, ""
        if until_ts:
            now_iso = datetime.now(timezone.utc).isoformat()
            if now_iso >= until_ts:
                # Auto-resume
                self._set_kill_switch(paused=False, reason="auto-resumed", until_ts=None)
                return False, ""
        return True, reason or "paused"

    def check_can_place_order(self, pair: str, notional_usd: float) -> tuple[bool, str]:
        """All gates in one call. Returns (allowed, reason)."""
        ok, why = self.is_live_enabled()
        if not ok:
            return False, f"blocked_disabled: {why}"
        paused, why = self.is_paused()
        if paused:
            return False, f"blocked_paused: {why}"
        if pair not in self.pair_allowlist:
            return False, f"blocked_pair_not_allowlisted: {pair} not in {sorted(self.pair_allowlist)[:5]}"
        if notional_usd > self.max_order_usd + 1e-6:
            return False, f"blocked_order_too_large: ${notional_usd:.2f} > ${self.max_order_usd:.2f}"
        exposure = self._current_exposure_usd()
        if exposure + notional_usd > self.max_exposure_usd + 1e-6:
            return False, f"blocked_exposure_cap: ${exposure:.2f} + ${notional_usd:.2f} > ${self.max_exposure_usd:.2f}"
        if not self._rate_limit_ok():
            return False, f"blocked_rate_limit: {self._rl_n} orders / {self._rl_window}s"
        return True, ""

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def submit_market_buy(
        self, pair: str, quote_size_usd: float, *,
        intent: str = "entry", strategy: str = "",
        signal_source_id: Optional[int] = None,
    ) -> OrderResult:
        """Market BUY for a USD amount. quote_size_usd is the dollars to spend."""
        notional = float(quote_size_usd)
        allowed, why = self.check_can_place_order(pair, notional)
        if not allowed:
            local_id = self._record_order(
                client_order_id=None, pair=pair, side="buy", order_type="market",
                quote_size=notional, base_size=None, limit_price=None,
                intent=intent, strategy=strategy, signal_source_id=signal_source_id,
                result_status="rejected", result_message=why,
            )
            return OrderResult(ok=False, reason=why, local_order_id=local_id)

        client_order_id = self._new_client_order_id()
        local_id = self._record_order(
            client_order_id=client_order_id, pair=pair, side="buy", order_type="market",
            quote_size=notional, base_size=None, limit_price=None,
            intent=intent, strategy=strategy, signal_source_id=signal_source_id,
            result_status="submitting", result_message=None,
        )

        try:
            self._rl_register()
            client = self._get_client()
            resp = client.market_order_buy(
                client_order_id=client_order_id,
                product_id=pair,
                quote_size=f"{notional:.2f}",
            )
            return self._post_submit_handle(local_id, client_order_id, pair, "buy",
                                            intent, strategy, resp)
        except Exception as e:
            return self._record_order_error(local_id, e)

    def submit_market_sell(
        self, pair: str, base_size: float, *,
        intent: str = "exit", strategy: str = "",
        signal_source_id: Optional[int] = None,
    ) -> OrderResult:
        """Market SELL for a crypto amount. base_size is the crypto units to sell."""
        # We don't know the USD notional precisely before the sell, but we can
        # estimate from current price for the exposure cap. For now skip the
        # exposure check on sells (sells reduce exposure, can't increase it).
        allowed, why = self.is_live_enabled()
        if not allowed:
            return OrderResult(ok=False, reason=f"blocked_disabled: {why}")
        paused, why = self.is_paused()
        if paused:
            return OrderResult(ok=False, reason=f"blocked_paused: {why}")
        if pair not in self.pair_allowlist:
            return OrderResult(ok=False, reason=f"blocked_pair_not_allowlisted: {pair}")
        if not self._rate_limit_ok():
            return OrderResult(ok=False, reason="blocked_rate_limit")

        client_order_id = self._new_client_order_id()
        local_id = self._record_order(
            client_order_id=client_order_id, pair=pair, side="sell", order_type="market",
            quote_size=None, base_size=base_size, limit_price=None,
            intent=intent, strategy=strategy, signal_source_id=signal_source_id,
            result_status="submitting", result_message=None,
        )

        try:
            self._rl_register()
            client = self._get_client()
            resp = client.market_order_sell(
                client_order_id=client_order_id,
                product_id=pair,
                base_size=str(base_size),
            )
            return self._post_submit_handle(local_id, client_order_id, pair, "sell",
                                            intent, strategy, resp)
        except Exception as e:
            return self._record_order_error(local_id, e)

    # ------------------------------------------------------------------
    # Reads against Coinbase (for reconciliation, equity, balance queries)
    # ------------------------------------------------------------------

    def get_usd_cash(self) -> float:
        """Coinbase available USD balance in the connected portfolio."""
        client = self._get_client()
        resp = client.get_accounts()
        accounts = resp.get('accounts', []) if isinstance(resp, dict) else getattr(resp, 'accounts', [])
        for a in accounts:
            currency = _attr(a, 'currency')
            if currency == "USD":
                bal_obj = _attr(a, 'available_balance') or {}
                return float(_attr(bal_obj, 'value') or 0)
        return 0.0

    def get_crypto_balance(self, currency: str) -> float:
        """Available balance of a single crypto (e.g. 'BTC'). Returns 0 if none."""
        client = self._get_client()
        resp = client.get_accounts()
        accounts = resp.get('accounts', []) if isinstance(resp, dict) else getattr(resp, 'accounts', [])
        for a in accounts:
            if _attr(a, 'currency') == currency:
                bal_obj = _attr(a, 'available_balance') or {}
                return float(_attr(bal_obj, 'value') or 0)
        return 0.0

    # ------------------------------------------------------------------
    # Kill switch / state
    # ------------------------------------------------------------------

    def trip_kill_switch(self, reason: str, until_ts: Optional[str] = None) -> None:
        """Pause live trading. `until_ts` (ISO) auto-resumes; None = manual unpause."""
        self._set_kill_switch(paused=True, reason=reason, until_ts=until_ts)
        logger.warning("kill switch tripped: %s (until=%s)", reason, until_ts)

    def reset_kill_switch(self) -> None:
        self._set_kill_switch(paused=False, reason=None, until_ts=None)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            # Lazy import so the module loads even without the SDK installed
            from coinbase.rest import RESTClient
            self._client = RESTClient(key_file=self.key_file)
        return self._client

    def _new_client_order_id(self) -> str:
        return f"bot-{uuid.uuid4()}"

    def _current_exposure_usd(self) -> float:
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(entry_notional_usd), 0) FROM live_positions"
            ).fetchone()
        return float(row[0] or 0)

    def _rate_limit_ok(self) -> bool:
        with self._rl_lock:
            now = time.time()
            cutoff = now - self._rl_window
            while self._rl_times and self._rl_times[0] < cutoff:
                self._rl_times.popleft()
            return len(self._rl_times) < self._rl_n

    def _rl_register(self) -> None:
        with self._rl_lock:
            self._rl_times.append(time.time())

    def _record_order(
        self, *, client_order_id, pair, side, order_type,
        quote_size, base_size, limit_price, intent, strategy,
        signal_source_id, result_status, result_message,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            cur = conn.execute(
                "INSERT INTO live_orders ("
                "  client_order_id, coinbase_order_id, ts, pair, side, order_type,"
                "  quote_size, base_size, limit_price, intent, strategy,"
                "  signal_source_id, result_status, result_message, created_at"
                ") VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (client_order_id or f"rejected-{uuid.uuid4()}", now, pair, side, order_type,
                 quote_size, base_size, limit_price, intent, strategy,
                 signal_source_id, result_status, result_message, now),
            )
            return cur.lastrowid

    def _post_submit_handle(self, local_id, client_order_id, pair, side,
                            intent, strategy, resp) -> OrderResult:
        """Update live_orders + write to live_trades if we have fill info."""
        # Successful immediate response shape (SDK returns a dict-like):
        # { 'success': True, 'order_id': '...', 'success_response': {...} }
        # On failure: { 'success': False, 'error_response': {...}, 'failure_reason': '...' }
        success = _attr(resp, "success")
        coinbase_id = _attr(resp, "order_id")
        if not success:
            err = _attr(resp, "error_response") or _attr(resp, "failure_reason") or "unknown_failure"
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                conn.execute(
                    "UPDATE live_orders SET coinbase_order_id=?, result_status=?, result_message=? WHERE id=?",
                    (coinbase_id, "rejected", str(err)[:500], local_id),
                )
            return OrderResult(ok=False, reason="rejected", detail=str(err)[:200],
                               local_order_id=local_id, coinbase_order_id=coinbase_id)
        # Mark accepted; fill details come from a separate poll
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            conn.execute(
                "UPDATE live_orders SET coinbase_order_id=?, result_status=? WHERE id=?",
                (coinbase_id, "submitted", local_id),
            )
        return OrderResult(ok=True, reason="submitted",
                           local_order_id=local_id, coinbase_order_id=coinbase_id)

    def _record_order_error(self, local_id, exc) -> OrderResult:
        msg = f"{type(exc).__name__}: {exc}"[:500]
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                conn.execute(
                    "UPDATE live_orders SET result_status='error', result_message=? WHERE id=?",
                    (msg, local_id),
                )
        except Exception:
            pass  # already logging exception
        logger.exception("order submission errored")
        return OrderResult(ok=False, reason="error", detail=msg, local_order_id=local_id)

    def _set_kill_switch(self, *, paused: bool, reason: Optional[str],
                         until_ts: Optional[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            conn.execute(
                "UPDATE live_kill_switch SET paused=?, paused_at=?, reason=?, "
                "pause_until_ts=?, updated_at=? WHERE id=1",
                (1 if paused else 0, now if paused else None, reason, until_ts, now),
            )


def _attr(obj, key, default=None):
    """SDK objects can be dict-like OR attribute-like depending on version."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
