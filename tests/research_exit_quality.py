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


def _probe(con: duckdb.DuckDBPyConnection, pair: str, ts_iso: str) -> None:
    """Print every signal's value at (pair, ts_iso). For smoke-testing."""
    ts_epoch = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).timestamp()
    print(f"probe {pair} @ {ts_iso} (epoch {ts_epoch:.0f})")
    for name, fn in [
        ("tape_balance", signal_tape_balance),
        # others added in later tasks
    ]:
        r = fn(con, pair, ts_epoch)
        print(f"  {name}: score={r.score} raw={r.raw}")


def main() -> None:
    con = connect()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) >= 3 and sys.argv[1] == "probe":
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
