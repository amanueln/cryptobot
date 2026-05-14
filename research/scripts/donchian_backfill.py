"""One-shot backfill of donchian_shadow rows from local candle history.

Why: the live shadow logger (engine/donchian_shadow.py) was silently failing
inserts for days due to an off-by-one binding error. By the time the bug was
fixed, several weeks of "what would Donchian have done" data had been lost.

This script reads candles.db directly, detects Donchian 20h breakouts on a
representative pair universe over the last N days, and inserts shadow rows
with replayed=0. Then it triggers donchian_daily_compare.py for each day
in the window, which replays exits and writes daily comparison rows.

Pair universe: union of pairs found in pair_scans + momentum_trades + sim_trades
over the backfill window. This approximates the set of pairs the bot would
have been watching on any given day.

USAGE:
  python3 donchian_backfill.py [--days 30] [--dry-run]
  python3 donchian_backfill.py --days 30          # full insert + daily compare
  python3 donchian_backfill.py --days 7 --dry-run # just count what would land

Designed to be idempotent: re-running deletes prior backfill rows
(replayed=0 AND created_at LIKE 'backfill:%') before re-inserting.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone


DONCHIAN_PERIOD = 20
DEDUP_HOURS = 1
GRANULARITY = "ONE_HOUR"

DB_PATH = os.environ.get(
    "CRYPTOBOT_DB_PATH",
    "/app/src/data/candles.db" if os.path.exists("/app/src") else "data/candles.db",
)


def get_pair_universe(conn: sqlite3.Connection, since_iso: str) -> list[str]:
    """Pairs the MOMENTUM bot was plausibly watching during the window.

    Shadow mode compares Donchian vs the momentum bot specifically, so the
    universe must mirror what the momentum bot was tracking. We exclude
    grid bot pairs (sim_trades) — those are a separate strategy.
    """
    pairs: set[str] = set()

    # Pairs the momentum bot actually traded
    for r in conn.execute(
        "SELECT DISTINCT pair FROM momentum_trades WHERE timestamp >= ?",
        (since_iso,),
    ):
        if r[0]:
            pairs.add(r[0])

    # Pairs the momentum scanner discovered as candidates
    # (early_scanner_alerts is the momentum bot's signal source)
    try:
        for r in conn.execute(
            "SELECT DISTINCT pair FROM early_scanner_alerts WHERE created_at >= ?",
            (since_iso,),
        ):
            if r[0]:
                pairs.add(r[0])
    except sqlite3.OperationalError:
        pass  # table may not exist on older deploys

    return sorted(pairs)


def detect_breakouts_for_pair(
    conn: sqlite3.Connection, pair: str, since_iso: str
) -> list[tuple]:
    """Return list of (ts_iso, current_close, prior_high, breakout_pct) for
    every hour where close > max of prior 20 hourly closes, deduped to one
    per DEDUP_HOURS window."""
    rows = conn.execute(
        "SELECT timestamp, close FROM candles "
        "WHERE pair = ? AND granularity = ? "
        "ORDER BY timestamp ASC",
        (pair, GRANULARITY),
    ).fetchall()
    if len(rows) < DONCHIAN_PERIOD + 1:
        return []

    breakouts = []
    last_logged_ts: datetime | None = None
    for i in range(DONCHIAN_PERIOD, len(rows)):
        ts_str = rows[i][0]
        current = rows[i][1]
        if ts_str < since_iso:
            continue
        prior_window = [rows[j][1] for j in range(i - DONCHIAN_PERIOD, i)]
        prior_high = max(prior_window)
        if current <= prior_high:
            continue

        try:
            current_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        if last_logged_ts and (current_ts - last_logged_ts).total_seconds() < DEDUP_HOURS * 3600:
            continue

        breakout_pct = (current - prior_high) / prior_high * 100
        breakouts.append((current_ts.isoformat(), current, prior_high, breakout_pct))
        last_logged_ts = current_ts

    return breakouts


def clear_prior_backfill(conn: sqlite3.Connection) -> int:
    """Remove rows from previous backfill runs (marked by created_at='backfill:...')
    that haven't been replayed yet. Lets us re-run safely."""
    cur = conn.execute(
        "DELETE FROM donchian_shadow "
        "WHERE replayed = 0 AND created_at LIKE 'backfill:%'"
    )
    return cur.rowcount


def insert_shadow_rows(
    conn: sqlite3.Connection, pair: str, breakouts: list[tuple]
) -> int:
    """Insert backfill rows. Matches engine/donchian_shadow.py column layout."""
    if not breakouts:
        return 0
    tag = f"backfill:{datetime.now(timezone.utc).isoformat()}"
    rows = []
    for ts, entry, prior_high, bo_pct in breakouts:
        rows.append((
            ts, pair, entry, prior_high, bo_pct,
            0, None, None,                          # bot_in_position, active_pair, unrealized_pnl
            None, None, None,                       # rsi, adx, accel (not reconstructable)
            0,                                       # replayed
            None, None, None, None, None, None, None, None,  # 8 exit cols
            0,                                       # kept_in_queue
            tag,                                     # created_at — tag for re-runs
        ))
    conn.executemany(
        "INSERT INTO donchian_shadow ("
        "  ts, pair, entry_price, rolling_20h_high, breakout_pct,"
        "  bot_in_position, bot_active_pair, bot_unrealized_pnl_pct,"
        "  rsi, adx, accel,"
        "  replayed, exit_ts, exit_price, exit_reason, pnl_pct,"
        "  peak_pct, mae_pct, hours_held, net_usd,"
        "  kept_in_queue, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def run_daily_compare(date_str: str) -> tuple[int, str]:
    """Invoke donchian_daily_compare.py for one date. Returns (returncode, output)."""
    script = "/app/src/research/scripts/donchian_daily_compare.py"
    if not os.path.exists(script):
        script = "research/scripts/donchian_daily_compare.py"
    r = subprocess.run(
        ["python3", script, "--date", date_str],
        capture_output=True, text=True, timeout=300,
    )
    return r.returncode, (r.stdout + r.stderr)[-400:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    since_iso = since.isoformat()

    print(f"Backfilling Donchian shadow {args.days} days from {since_iso[:10]}")
    print(f"DB: {DB_PATH}")
    print(f"Dry-run: {args.dry_run}")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    pairs = get_pair_universe(conn, since_iso)
    print(f"Pair universe: {len(pairs)} pairs ({pairs[:10]}{'...' if len(pairs) > 10 else ''})")

    if not args.dry_run:
        cleared = clear_prior_backfill(conn)
        if cleared:
            print(f"Cleared {cleared} unreplayed rows from previous backfill")

    total_breakouts = 0
    per_pair = {}
    for pair in pairs:
        breakouts = detect_breakouts_for_pair(conn, pair, since_iso)
        per_pair[pair] = len(breakouts)
        total_breakouts += len(breakouts)
        if not args.dry_run and breakouts:
            insert_shadow_rows(conn, pair, breakouts)

    if not args.dry_run:
        conn.commit()

    print()
    print(f"Total breakouts detected: {total_breakouts}")
    if total_breakouts:
        ranked = sorted(per_pair.items(), key=lambda kv: -kv[1])
        for p, n in ranked[:15]:
            if n > 0: print(f"  {p:<14} {n} signals")

    conn.close()

    if args.dry_run:
        print("\n(dry-run — no rows inserted, no daily compares run)")
        return

    # Run daily_compare for each date in window
    print()
    print(f"Running daily_compare for {args.days} dates...")
    today = datetime.now(timezone.utc).date()
    for day_offset in range(args.days, 0, -1):
        d = today - timedelta(days=day_offset)
        date_str = d.isoformat()
        rc, out = run_daily_compare(date_str)
        marker = "OK " if rc == 0 else "ERR"
        # Pull last line of output for status
        last_line = ""
        for ln in reversed(out.splitlines()):
            if ln.strip():
                last_line = ln.strip()[:120]
                break
        print(f"  [{marker}] {date_str}  {last_line}")


if __name__ == "__main__":
    main()
