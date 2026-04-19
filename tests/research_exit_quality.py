"""
Exit-quality forensic analysis.

Read-only analysis over fresh DB snapshots in data_snapshots/. For each closed
momentum_trade in the last 14 days, compute 5 in-position signals at exit time,
label post-exit price action, and emit a markdown report.

Spec: docs/superpowers/specs/2026-04-19-exit-quality-analysis-design.md
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "data_snapshots"
OUT_DIR = REPO_ROOT / "tests" / "out"
CANDLES_DB = SNAPSHOT_DIR / "candles.db"
MARKET_TAPE_DB = SNAPSHOT_DIR / "market_tape.db"

FEE_BUFFER_PCT = 0.012  # matches engine/momentum_engine.py:1146 wall-aware min_profit_buffer_pct
LOOKBACK_DAYS = 14
FREAK_OUT_UP_PCT = 3.0   # post-exit rise threshold to label freak-out
LEGIT_DOWN_PCT = 2.0     # post-exit drop threshold to label legit


def connect() -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection with both SQLite DBs attached read-only."""
    if not CANDLES_DB.exists():
        sys.exit(f"ERROR: {CANDLES_DB} missing. Run Task 0 to pull snapshots.")
    if not MARKET_TAPE_DB.exists():
        sys.exit(f"ERROR: {MARKET_TAPE_DB} missing. Run Task 0 to pull snapshots.")
    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{CANDLES_DB}' AS candles_db (TYPE SQLITE, READ_ONLY)")
    con.execute(f"ATTACH '{MARKET_TAPE_DB}' AS tape_db (TYPE SQLITE, READ_ONLY)")
    return con


def freshness_report(con: duckdb.DuckDBPyConnection) -> str:
    """Return a markdown block describing snapshot freshness."""
    rows = []
    for label, sql in [
        ("wall_decisions", "SELECT MAX(timestamp) FROM candles_db.wall_decisions"),
        ("regime_snapshots", "SELECT MAX(timestamp) FROM candles_db.regime_snapshots"),
        ("candles 1m", "SELECT MAX(timestamp) FROM candles_db.candles WHERE granularity='ONE_MINUTE'"),
        ("momentum_trades sells", "SELECT MAX(timestamp) FROM candles_db.momentum_trades WHERE side='sell' AND pnl_pct IS NOT NULL"),
        ("ws_matches", "SELECT MAX(ts) FROM tape_db.ws_matches"),
        ("l2_snapshots", "SELECT MAX(ts) FROM tape_db.l2_snapshots"),
    ]:
        latest = con.execute(sql).fetchone()[0]
        rows.append(f"| {label} | {latest} |")
    return "## Snapshot freshness\n\n| source | latest row |\n|---|---|\n" + "\n".join(rows) + "\n"


def iso_to_epoch(ts_iso: str) -> float:
    """Parse an ISO timestamp to UTC epoch seconds.

    candles.db stores timestamps as UTC-naive ISO text (e.g. '2026-04-17T02:54:56').
    Treat naive strings as UTC, not local. An explicit offset/Z is honored.
    """
    d = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


def epoch_to_iso(ts_epoch: float) -> str:
    """Format a UTC epoch as a naive UTC ISO string matching candles.db format."""
    return dt.datetime.fromtimestamp(ts_epoch, tz=dt.timezone.utc).replace(tzinfo=None).isoformat()


@dataclass
class SignalResult:
    score: Optional[float]   # in [-1, +1], or None if no data
    raw: dict


def signal_tape_balance(con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float) -> SignalResult:
    """Signal 1: tape-order-flow balance over the 10 min before ts_epoch.

    (buy_usd - sell_usd) / total_usd using ws_matches.side uppercase BUY/SELL.
    Score in [-1, +1]. None if no trades in window.
    """
    lookback_s = 600.0
    row = con.execute("""
        SELECT
            SUM(CASE WHEN UPPER(side)='BUY'  THEN price*size ELSE 0 END) AS buy_usd,
            SUM(CASE WHEN UPPER(side)='SELL' THEN price*size ELSE 0 END) AS sell_usd,
            COUNT(*) AS n
        FROM tape_db.ws_matches
        WHERE pair = ?
          AND ts_epoch BETWEEN ? AND ?
    """, [pair, ts_epoch - lookback_s, ts_epoch]).fetchone()
    buy_usd, sell_usd, n = (row[0] or 0.0), (row[1] or 0.0), row[2]
    total = buy_usd + sell_usd
    if n == 0 or total <= 0:
        return SignalResult(None, {"n_trades": n, "reason": "no_trades_in_window"})
    score = (buy_usd - sell_usd) / total
    return SignalResult(score, {"n_trades": n, "buy_usd": buy_usd, "sell_usd": sell_usd})


def signal_book_imbalance(con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float) -> SignalResult:
    """Signal 2: nearest L2 snapshot, bid-vs-ask USD within ±2% of mid.

    bids/asks are JSON '[[price,size],...]' strings. Score = (bid_usd - ask_usd) / total.
    None if no snapshot within 5 min before ts_epoch.
    """
    max_age_s = 300.0
    row = con.execute("""
        SELECT ts_epoch, mid, bids, asks
        FROM tape_db.l2_snapshots
        WHERE pair = ?
          AND ts_epoch BETWEEN ? AND ?
        ORDER BY ts_epoch DESC
        LIMIT 1
    """, [pair, ts_epoch - max_age_s, ts_epoch]).fetchone()
    if row is None:
        return SignalResult(None, {"reason": "no_snapshot_within_5min"})
    snap_ts, mid, bids_json, asks_json = row
    if mid is None or mid <= 0:
        return SignalResult(None, {"reason": "bad_mid", "ts_epoch": snap_ts})
    band_lo = mid * 0.98
    band_hi = mid * 1.02
    bids = json.loads(bids_json)
    asks = json.loads(asks_json)
    bid_usd = sum(p * s for p, s in bids if band_lo <= p <= mid)
    ask_usd = sum(p * s for p, s in asks if mid <= p <= band_hi)
    total = bid_usd + ask_usd
    if total <= 0:
        return SignalResult(None, {"reason": "no_liquidity_in_band", "mid": mid})
    score = (bid_usd - ask_usd) / total
    snap_age = ts_epoch - snap_ts
    return SignalResult(score, {"bid_usd": bid_usd, "ask_usd": ask_usd, "mid": mid, "snap_age_s": snap_age})


def _ema(values: list[float], period: int) -> list[float]:
    """Simple EMA. Returns list same length as input; first (period-1) entries padded with None."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    out = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(out[-1] + k * (v - out[-1]))
    # pad front with Nones so index aligns with input
    return [None] * (period - 1) + out


def signal_micro_trend(con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float) -> SignalResult:
    """Signal 3: 1m EMA5 vs EMA20 over the last 60 minutes before ts_epoch.

    Score = sign(EMA5 - EMA20) * min(1, abs(slope_per_min)/0.001),
    where slope_per_min is (EMA5_now - EMA5_60min_ago) / 60 / close_now.
    None if fewer than 25 1m candles available (need enough for EMA20 + slope window).
    """
    ts_iso = epoch_to_iso(ts_epoch)
    rows = con.execute("""
        SELECT timestamp, close
        FROM candles_db.candles
        WHERE pair = ?
          AND granularity = 'ONE_MINUTE'
          AND timestamp <= ?
        ORDER BY timestamp DESC
        LIMIT 60
    """, [pair, ts_iso]).fetchall()
    if len(rows) < 25:
        return SignalResult(None, {"reason": "insufficient_candles", "n": len(rows)})
    # reverse to chronological
    rows = rows[::-1]
    closes = [r[1] for r in rows]
    ema5 = _ema(closes, 5)
    ema20 = _ema(closes, 20)
    if ema5[-1] is None or ema20[-1] is None:
        return SignalResult(None, {"reason": "ema_not_computed"})
    ema5_now, ema20_now = ema5[-1], ema20[-1]
    ema5_ago = ema5[max(0, len(ema5) - 60)] if len(ema5) >= 60 and ema5[len(ema5)-60] is not None else ema5[20]
    close_now = closes[-1]
    if close_now <= 0:
        return SignalResult(None, {"reason": "bad_close"})
    window_min = max(1, len(ema5) - 1 - max(0, len(ema5) - 60))
    slope_per_min = (ema5_now - ema5_ago) / window_min / close_now
    direction = 1.0 if ema5_now > ema20_now else -1.0 if ema5_now < ema20_now else 0.0
    magnitude = min(1.0, abs(slope_per_min) / 0.001)
    score = direction * magnitude
    return SignalResult(score, {
        "ema5": ema5_now, "ema20": ema20_now, "close": close_now,
        "slope_per_min": slope_per_min, "n_candles": len(rows),
    })


def _probe(con: duckdb.DuckDBPyConnection, pair: str, ts_iso: str) -> None:
    """Print every signal's value at (pair, ts_iso). For smoke-testing."""
    ts_epoch = iso_to_epoch(ts_iso)
    print(f"probe {pair} @ {ts_iso} (epoch {ts_epoch:.0f})")
    for name, fn in [
        ("tape_balance", signal_tape_balance),
        ("book_imbalance", signal_book_imbalance),
        ("micro_trend", signal_micro_trend),
    ]:
        r = fn(con, pair, ts_epoch)
        print(f"  {name}: score={r.score} raw={r.raw}")


def main() -> None:
    con = connect()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) >= 4 and sys.argv[1] == "probe":
        # usage: python research_exit_quality.py probe <PAIR> <ISO_TS>
        _probe(con, sys.argv[2], sys.argv[3])
        return
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    out_path = OUT_DIR / f"exit_quality_{stamp}.md"
    lines = [f"# Exit-Quality Analysis — {stamp}\n", freshness_report(con)]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
