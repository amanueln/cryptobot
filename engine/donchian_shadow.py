"""Donchian shadow logger.

Observation-only module. On each compute_scores() tick, checks every
tracked pair for a Donchian 20-period high breakout. If one is found and
hasn't been logged in the last hour (dedup window), inserts a row into
the donchian_shadow table.

DOES NOT affect any trading decisions. Pure logging.

Research: see docs/superpowers/specs (if you write the spec) or the
findings: Donchian 20h breakout outperformed acceleration scanner in
backtest (+$2,608 vs -$729 over 26 days, 88% WR on walk-forward).
"""
from __future__ import annotations

import sqlite3
import logging
from datetime import datetime, timezone

logger = logging.getLogger("donchian_shadow")


DONCHIAN_PERIOD = 20         # hours
DEDUP_WINDOW_SEC = 3600       # don't log same pair more than once per hour

_schema_initialized = False


def _ensure_schema(db_path: str) -> None:
    """Idempotently init the donchian_shadow + donchian_daily_compare tables."""
    global _schema_initialized
    if _schema_initialized:
        return
    try:
        from engine.donchian_shadow_schema import init_schema
        init_schema(db_path)
        _schema_initialized = True
    except Exception:
        logger.exception("donchian_shadow schema init failed (non-fatal)")


def maybe_log_signals(engine, db_path: str) -> int:
    """For each tracked pair, check Donchian 20h breakout. Log to shadow table.

    `engine` must expose:
      - .pairs: list[str]
      - ._closes: dict[pair -> list[float]]
      - ._timestamps: dict[pair -> list[datetime]]
      - .holdings: dict[pair -> Holding]   (for context only)
      - ._rsi_cache / ._adx_cache / ._accel_scores (optional, for analysis)

    Returns the number of new signals logged.
    """
    _ensure_schema(db_path)
    logged = 0
    now_iso = datetime.utcnow().isoformat()

    # Pull the most recent shadow row per pair to enforce dedup window
    last_logged_ts: dict[str, datetime] = {}
    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            for r in conn.execute(
                "SELECT pair, MAX(ts) FROM donchian_shadow GROUP BY pair"
            ):
                pair, ts_str = r
                if ts_str:
                    try:
                        last_logged_ts[pair] = datetime.fromisoformat(
                            ts_str.replace("Z", "+00:00"))
                    except Exception:
                        pass
    except sqlite3.OperationalError:
        return 0

    # Active position context (informational)
    in_position = bool(getattr(engine, "holdings", {}))
    active_pair = None
    active_pnl = None
    if in_position:
        active_pair = next(iter(engine.holdings))
        h = engine.holdings[active_pair]
        cur = engine._closes.get(active_pair, [])
        if cur:
            active_pnl = (cur[-1] - h.entry_price) / h.entry_price * 100

    rows_to_insert = []
    for pair in engine.pairs:
        closes = engine._closes.get(pair, [])
        ts_list = engine._timestamps.get(pair, [])
        if len(closes) < DONCHIAN_PERIOD + 1:
            continue
        # Donchian: current close above prior N highs
        prior_window = closes[-(DONCHIAN_PERIOD + 1):-1]   # last 20 (not incl current)
        current_close = closes[-1]
        current_ts = ts_list[-1] if ts_list else None
        prior_high = max(prior_window)
        if current_close <= prior_high:
            continue

        # Dedup: must be > DEDUP_WINDOW_SEC since last log for this pair
        last_ts = last_logged_ts.get(pair)
        if last_ts is not None and current_ts is not None:
            delta = (current_ts - last_ts).total_seconds()
            if delta < DEDUP_WINDOW_SEC:
                continue

        breakout_pct = (current_close - prior_high) / prior_high * 100

        # Pull features for analysis (these are recomputed cheap or cached)
        rsi_val = _safe_get(engine, "_rsi_cache", pair)
        adx_val = _safe_get(engine, "_adx_cache", pair)
        accel_val = _safe_get(engine, "_accel_scores", pair)

        ts_str = current_ts.isoformat() if current_ts else now_iso
        rows_to_insert.append((
            ts_str, pair, current_close, prior_high, breakout_pct,
            int(in_position), active_pair, active_pnl,
            rsi_val, adx_val, accel_val,
            0,           # replayed
            # 8 unfilled exit-outcome columns: exit_ts, exit_price, exit_reason,
            # pnl_pct, peak_pct, mae_pct, hours_held, net_usd
            None, None, None, None, None, None, None, None,
            0,           # kept_in_queue (filled by daily script)
            now_iso,
        ))

    if not rows_to_insert:
        return 0

    try:
        with sqlite3.connect(db_path, timeout=10) as conn:
            conn.executemany(
                "INSERT INTO donchian_shadow ("
                "  ts, pair, entry_price, rolling_20h_high, breakout_pct,"
                "  bot_in_position, bot_active_pair, bot_unrealized_pnl_pct,"
                "  rsi, adx, accel,"
                "  replayed, exit_ts, exit_price, exit_reason, pnl_pct,"
                "  peak_pct, mae_pct, hours_held, net_usd,"
                "  kept_in_queue, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows_to_insert,
            )
        logged = len(rows_to_insert)
        if logged:
            logger.info("donchian_shadow logged %d signal(s)", logged)
    except Exception:
        logger.exception("donchian_shadow insert failed (non-fatal)")
        return 0

    return logged


def _safe_get(engine, attr_name, key):
    """Lookup engine.<attr_name>[key] gracefully — returns None if missing."""
    container = getattr(engine, attr_name, None)
    if container is None:
        return None
    try:
        v = container.get(key) if hasattr(container, "get") else container[key]
        return float(v) if v is not None else None
    except Exception:
        return None
