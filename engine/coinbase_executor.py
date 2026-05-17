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
        # Pair allowlist + wildcard support. `LIVE_PAIR_ALLOWLIST=*` means
        # "trust whatever the strategy picks" — useful when the strategy has
        # its own pair filter (e.g., the momentum scanner's top-30-by-volume)
        # and we don't want this guard to silently veto its choices.
        if pair_allowlist is None:
            raw = os.environ.get("LIVE_PAIR_ALLOWLIST", "")
            entries = [p.strip() for p in raw.split(",") if p.strip()]
            self.pair_allow_all = ("*" in entries)
            self.pair_allowlist = set(entries) - {"*"}
        else:
            self.pair_allow_all = ("*" in pair_allowlist)
            self.pair_allowlist = set(pair_allowlist) - {"*"}

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
        if not self.pair_allow_all and pair not in self.pair_allowlist:
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

        # PRE-FLIGHT 1: confirm Coinbase actually has the cash (drift detector).
        # The bot's internal self.cash is reconciled at startup but isn't
        # re-queried before each trade. Manual transfers, conversions, or
        # missed-fill scenarios could leave the bot's tracking stale.
        cash_ok, live_balance, cash_why = self.verify_sufficient_cash(notional)
        if not cash_ok:
            local_id = self._record_order(
                client_order_id=None, pair=pair, side="buy", order_type="market",
                quote_size=notional, base_size=None, limit_price=None,
                intent=intent, strategy=strategy, signal_source_id=signal_source_id,
                result_status="rejected", result_message=cash_why,
            )
            return OrderResult(ok=False, reason=f"blocked_{cash_why.split(':')[0]}",
                               detail=cash_why, local_order_id=local_id)

        # PRE-FLIGHT 2: confirm the pair is tradable + order meets minimums.
        # Pairs go offline/halted occasionally; submitting to a halted pair
        # wastes a round-trip and pollutes live_orders with confusing errors.
        # Cached 1h to keep load minimal.
        product_ok, product_why = self.verify_product_tradable(pair, notional)
        if not product_ok:
            local_id = self._record_order(
                client_order_id=None, pair=pair, side="buy", order_type="market",
                quote_size=notional, base_size=None, limit_price=None,
                intent=intent, strategy=strategy, signal_source_id=signal_source_id,
                result_status="rejected", result_message=product_why,
            )
            return OrderResult(ok=False, reason=f"blocked_{product_why.split(':')[0]}",
                               detail=product_why, local_order_id=local_id)

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
        if not self.pair_allow_all and pair not in self.pair_allowlist:
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
        """Coinbase available USD balance in the connected portfolio.

        Endpoint: GET /api/v3/brokerage/accounts (SDK: client.get_accounts()).
        Iterates accounts and returns float(available_balance.value) for the
        USD account. USD isn't always first in the list — don't index [0].
        """
        client = self._get_client()
        resp = client.get_accounts()
        accounts = resp.get('accounts', []) if isinstance(resp, dict) else getattr(resp, 'accounts', [])
        for a in accounts:
            currency = _attr(a, 'currency')
            if currency == "USD":
                bal_obj = _attr(a, 'available_balance') or {}
                return float(_attr(bal_obj, 'value') or 0)
        return 0.0

    def verify_sufficient_cash(self, quote_usd: float,
                                buffer_usd: float = 0.05) -> tuple[bool, float, str]:
        """Pre-flight: confirm Coinbase actually has enough USD to cover the
        order, before we submit. Catches drift between the bot's internal cash
        tracking and the real exchange balance (manual transfers, conversions,
        out-of-band activity between init reconcile and now).

        Returns (ok, live_balance, reason).

        Coinbase's `market_order_buy` with `quote_size=$X` consumes EXACTLY
        $X — the fee is taken from the crypto received, not added on top.
        So no fee buffer is needed. The $0.05 default is just floating-point
        safety / balance-refresh latency; anything bigger is over-restrictive.

        Endpoint: GET /api/v3/brokerage/accounts (same as get_usd_cash)."""
        try:
            live = self.get_usd_cash()
        except Exception as e:
            return False, 0.0, f"live_cash_check_failed: {type(e).__name__}"
        needed = quote_usd + buffer_usd
        if live + 1e-6 < needed:
            return False, live, (
                f"insufficient_live_cash: have ${live:.2f}, "
                f"need ${needed:.2f} (order ${quote_usd:.2f} + ${buffer_usd:.2f} buffer)"
            )
        return True, live, ""

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

    def get_product_info(self, pair: str) -> dict:
        """Per-pair trading rules from Coinbase.

        Endpoint: GET /api/v3/brokerage/products/{product_id}
        (SDK: RESTClient.get_product).

        Returns a flat dict with the fields the bot cares about:
          - status: 'online' when tradable
          - trading_disabled / is_disabled / cancel_only / view_only: bool gates
          - base_min_size / quote_min_size: minimum order sizes (as strings)
          - base_increment / quote_increment: precision steps (as strings)
          - price: last trade price (string)
        On failure returns {'error': str} so callers can decide whether to
        proceed cautiously or block.

        Per-pair info is cached for 1 hour — these rules don't change often
        but we shouldn't bombard the API on every tick."""
        # Cache: pair -> (fetched_at_unix, dict)
        cache = getattr(self, "_product_cache", None)
        if cache is None:
            cache = {}
            self._product_cache = cache
        now = time.time()
        cached = cache.get(pair)
        if cached and (now - cached[0]) < 3600:
            return cached[1]
        try:
            client = self._get_client()
            resp = client.get_product(product_id=pair)
            # Flat object — read attrs
            info = {
                "pair": pair,
                "status": _attr(resp, "status"),
                "trading_disabled": bool(_attr(resp, "trading_disabled")),
                "is_disabled": bool(_attr(resp, "is_disabled")),
                "cancel_only": bool(_attr(resp, "cancel_only")),
                "view_only": bool(_attr(resp, "view_only")),
                "base_min_size": _attr(resp, "base_min_size"),
                "quote_min_size": _attr(resp, "quote_min_size"),
                "base_increment": _attr(resp, "base_increment"),
                "quote_increment": _attr(resp, "quote_increment"),
                "price": _attr(resp, "price"),
            }
            cache[pair] = (now, info)
            return info
        except Exception as e:
            return {"pair": pair, "error": f"{type(e).__name__}: {e}"}

    def get_fee_tier_info(self, product_type: str = "SPOT") -> dict:
        """Current fee tier + 30-day volume, so the dashboard can show what
        you're actually paying and how close you are to the next tier.

        Endpoint: GET /api/v3/brokerage/transaction_summary
        (SDK: RESTClient.get_transaction_summary — singular).

        Returns:
          {
            "pricing_tier": str,      # e.g. "Advanced 1" or "<$10k"
            "maker_fee_rate": float,  # decimal e.g. 0.006 = 0.6%
            "taker_fee_rate": float,  # decimal e.g. 0.012 = 1.2%
            "total_volume_30d": float,
            "usd_from": float,        # current tier band start
            "usd_to": float,          # current tier band end (= next-tier threshold)
            "to_next_tier_usd": float, # how much more volume needed
            "error": str (optional)   # only on failure
          }

        Inconsistency note (verified 2026-05-17): the docs schema page emphasizes
        aop_from/aop_to (assets-on-platform) but the live response still returns
        usd_from/usd_to (30d volume band). Use usd_* for the next-tier calc;
        aop_* is a separate Coinbase ONE qualification axis, not 30d volume."""
        try:
            client = self._get_client()
            resp = client.get_transaction_summary(product_type=product_type)
            total_volume = float(_attr(resp, "total_volume") or 0)
            tier_obj = _attr(resp, "fee_tier") or {}
            pricing_tier = _attr(tier_obj, "pricing_tier") or "?"
            try:
                maker = float(_attr(tier_obj, "maker_fee_rate") or 0)
            except (TypeError, ValueError):
                maker = 0.0
            try:
                taker = float(_attr(tier_obj, "taker_fee_rate") or 0)
            except (TypeError, ValueError):
                taker = 0.0
            try:
                usd_from = float(_attr(tier_obj, "usd_from") or 0)
            except (TypeError, ValueError):
                usd_from = 0.0
            try:
                usd_to = float(_attr(tier_obj, "usd_to") or 0)
            except (TypeError, ValueError):
                usd_to = 0.0
            to_next = max(0.0, usd_to - total_volume)
            return {
                "pricing_tier": pricing_tier,
                "maker_fee_rate": maker,
                "taker_fee_rate": taker,
                "total_volume_30d": total_volume,
                "usd_from": usd_from,
                "usd_to": usd_to,
                "to_next_tier_usd": to_next,
            }
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def verify_product_tradable(self, pair: str, quote_usd: float) -> tuple[bool, str]:
        """Pre-flight: confirm the pair is currently tradable AND the order
        size meets the per-pair minimum.

        Returns (ok, reason). Empty reason on success.

        Per Coinbase docs, a product is tradable iff:
            status == 'online' AND NOT trading_disabled
                                AND NOT is_disabled
                                AND NOT cancel_only AND NOT view_only
        And `quote_size >= float(quote_min_size)` for the buy to clear the
        minimum-order check."""
        info = self.get_product_info(pair)
        if "error" in info:
            return False, f"product_info_unavailable: {info['error']}"
        if info.get("status") != "online":
            return False, f"pair_halted: status={info.get('status')!r}"
        if info.get("trading_disabled") or info.get("is_disabled"):
            return False, "pair_trading_disabled"
        if info.get("cancel_only"):
            return False, "pair_cancel_only"
        if info.get("view_only"):
            return False, "pair_view_only"
        # Numeric min size check (string → float)
        try:
            qmin = float(info.get("quote_min_size") or 0)
        except (TypeError, ValueError):
            qmin = 0.0
        if quote_usd + 1e-6 < qmin:
            return False, f"below_quote_min: order ${quote_usd:.2f} < min ${qmin:.2f}"
        return True, ""

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
        """Update live_orders + write to live_trades if we have fill info.

        SDK response shape (real, verified via smoke test):
          success: { 'success': True, 'success_response': {'order_id': '...', ...}, 'order_configuration': {...} }
          failure: { 'success': False, 'error_response': {...}, 'failure_reason': '...' }

        We were previously reading top-level 'order_id' which doesn't exist on
        the live response — the order_id is nested under 'success_response'.
        Read both locations for forward-compat across SDK versions.
        """
        success = _attr(resp, "success")
        # Prefer nested success_response.order_id (current shape); fall back to top-level.
        success_resp = _attr(resp, "success_response") or {}
        coinbase_id = _attr(success_resp, "order_id") or _attr(resp, "order_id")
        if not success:
            err_resp = _attr(resp, "error_response") or {}
            err = (_attr(err_resp, "error_details") or _attr(err_resp, "message")
                   or _attr(resp, "failure_reason") or "unknown_failure")
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                conn.execute(
                    "UPDATE live_orders SET coinbase_order_id=?, result_status=?, result_message=? WHERE id=?",
                    (coinbase_id, "rejected", str(err)[:500], local_id),
                )
            return OrderResult(ok=False, reason="rejected", detail=str(err)[:200],
                               local_order_id=local_id, coinbase_order_id=coinbase_id)
        # Mark accepted; fill details come from a separate poll via wait_for_fill().
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            conn.execute(
                "UPDATE live_orders SET coinbase_order_id=?, result_status=? WHERE id=?",
                (coinbase_id, "submitted", local_id),
            )
        return OrderResult(ok=True, reason="submitted",
                           local_order_id=local_id, coinbase_order_id=coinbase_id)

    # ------------------------------------------------------------------
    # Fill polling
    # ------------------------------------------------------------------

    def wait_for_fill(
        self, coinbase_order_id: str, *,
        timeout_sec: int = 20, poll_interval_sec: float = 1.0,
    ) -> dict:
        """Poll Coinbase for a fill. Returns a dict with:
            {
              'filled': bool,             # True if status in FILLED/CANCELLED/EXPIRED
              'status': str,              # raw Coinbase status string
              'filled_size': float,       # crypto amount filled
              'avg_price': float,         # weighted-avg fill price
              'fee_usd': float,           # total fees paid in USD
              'notional_usd': float,      # avg_price * filled_size
            }
        Times out after `timeout_sec` and returns whatever state we last saw.
        Never raises — errors are recorded in the dict under 'error'."""
        out = {
            "filled": False, "status": "unknown",
            "filled_size": 0.0, "avg_price": 0.0,
            "fee_usd": 0.0, "notional_usd": 0.0,
            "error": None,
        }
        if not coinbase_order_id:
            out["error"] = "no_coinbase_order_id"
            return out
        client = self._get_client()
        deadline = time.time() + timeout_sec
        last_resp = None
        while time.time() < deadline:
            try:
                resp = client.get_order(order_id=coinbase_order_id)
                last_resp = resp
                order = _attr(resp, "order") or resp  # SDK varies
                status = str(_attr(order, "status") or "").upper()
                filled_size = float(_attr(order, "filled_size") or 0)
                avg_price = float(_attr(order, "average_filled_price") or 0)
                fee = float(_attr(order, "total_fees") or 0)
                out.update({
                    "status": status,
                    "filled_size": filled_size,
                    "avg_price": avg_price,
                    "fee_usd": fee,
                    "notional_usd": avg_price * filled_size,
                })
                if status in ("FILLED", "CANCELLED", "EXPIRED", "FAILED"):
                    out["filled"] = (status == "FILLED")
                    return out
            except Exception as e:
                out["error"] = f"{type(e).__name__}: {e}"
            time.sleep(poll_interval_sec)
        # Timed out — return the last-known partial state if any
        out["status"] = out.get("status", "timeout")
        return out

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
