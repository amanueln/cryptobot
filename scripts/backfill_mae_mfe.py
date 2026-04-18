"""Backfill MAE/MFE (and trough_price) for historical sells in momentum_trades.

For each sell row missing max_adverse_pct and max_favorable_pct, finds the
matching buy (same pair, latest buy before the sell timestamp), pulls 1m
candles in the hold window, and computes:

    trough_price      = min(low)  across candles strictly between buy_ts and sell_ts
    max_adverse_pct   = (trough_price - entry_price) / entry_price * 100
    peak_price        = max(high) across the same candles (if currently NULL)
    max_favorable_pct = (peak_price - entry_price) / entry_price * 100

Sub-minute holds (zero candles in window) fall back to min/max of entry/exit
prices so the numbers still reflect the two points we know.

Usage:
    py scripts/backfill_mae_mfe.py --db data/candles.db                # dry run
    py scripts/backfill_mae_mfe.py --db data/candles.db --apply        # write
    py scripts/backfill_mae_mfe.py --db /DATA/AppData/cryptobot/data/candles.db --apply
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", required=True, help="Path to candles.db (has momentum_trades + candles)")
    p.add_argument("--apply", action="store_true", help="Actually write updates (default is dry-run)")
    p.add_argument("--verbose", "-v", action="store_true", help="Per-trade detail")
    return p.parse_args()


def _find_unfilled_sells(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, timestamp, pair, price AS exit_price
        FROM momentum_trades
        WHERE side = 'sell'
          AND (max_adverse_pct IS NULL AND max_favorable_pct IS NULL)
        ORDER BY timestamp ASC
        """
    ).fetchall()
    return list(rows)


def _find_matching_buy(conn: sqlite3.Connection, pair: str, sell_ts: str) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT id, timestamp, price AS entry_price
        FROM momentum_trades
        WHERE pair = ? AND side = 'buy' AND timestamp < ?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (pair, sell_ts),
    ).fetchone()
    return row


def _fetch_candles(conn: sqlite3.Connection, pair: str, start_ts: str, end_ts: str) -> list[sqlite3.Row]:
    # Strict > buy_ts AND < sell_ts — exclude the entry/exit candles to avoid
    # counting lows/highs that happened before we were in or after we were out.
    rows = conn.execute(
        """
        SELECT timestamp, high, low
        FROM candles
        WHERE pair = ? AND granularity = 'ONE_MINUTE'
          AND timestamp > ? AND timestamp < ?
        """,
        (pair, start_ts, end_ts),
    ).fetchall()
    return list(rows)


def _minutes_between(a: str, b: str) -> int:
    try:
        ta = datetime.fromisoformat(a)
        tb = datetime.fromisoformat(b)
        return max(0, int((tb - ta).total_seconds() // 60))
    except Exception:
        return -1


def main() -> int:
    args = _parse_args()
    db_path = args.db
    if not os.path.exists(db_path):
        print(f"ERROR: db not found: {db_path}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path, timeout=30)
    try:
        sells = _find_unfilled_sells(conn)
        print(f"Found {len(sells)} sells with NULL MAE/MFE in {db_path}")
        if not sells:
            return 0

        filled = 0
        skipped_no_buy = 0
        fallback_no_candles = 0
        updates: list[tuple] = []

        for s in sells:
            sell_id = s["id"]
            pair = s["pair"]
            sell_ts = s["timestamp"]
            exit_price = s["exit_price"]

            buy = _find_matching_buy(conn, pair, sell_ts)
            if buy is None:
                skipped_no_buy += 1
                if args.verbose:
                    print(f"  skip sell id={sell_id} {pair}@{sell_ts}: no prior buy")
                continue

            entry_price = buy["entry_price"]
            buy_ts = buy["timestamp"]
            candles = _fetch_candles(conn, pair, buy_ts, sell_ts)
            expected_min = _minutes_between(buy_ts, sell_ts)

            if candles:
                lows = [c["low"] for c in candles]
                highs = [c["high"] for c in candles]
                # Bracket by entry_price so trough never exceeds entry and peak never
                # falls below it — matches the live writer's semantics (trough_price
                # and peak_price are initialised to entry_price at fill). MAE <= 0,
                # MFE >= 0 by construction.
                trough_price = min(entry_price, min(lows))
                peak_price = max(entry_price, max(highs))
                coverage = f"{len(candles)}/{expected_min}m" if expected_min > 0 else f"{len(candles)}m"
            else:
                # Sub-minute hold or missing candles — fall back to the two prices we know.
                trough_price = min(entry_price, exit_price)
                peak_price = max(entry_price, exit_price)
                fallback_no_candles += 1
                coverage = f"0/{expected_min}m (FALLBACK)"

            if entry_price <= 0:
                if args.verbose:
                    print(f"  skip sell id={sell_id} {pair}: entry_price<=0")
                skipped_no_buy += 1
                continue

            max_adverse_pct = (trough_price - entry_price) / entry_price * 100.0
            max_favorable_pct = (peak_price - entry_price) / entry_price * 100.0

            updates.append((
                round(max_adverse_pct, 4),
                round(max_favorable_pct, 4),
                trough_price,
                peak_price,
                sell_id,
            ))
            filled += 1
            if args.verbose:
                print(
                    f"  fill id={sell_id} {pair} "
                    f"entry={entry_price:.6f} exit={exit_price:.6f} "
                    f"MAE={max_adverse_pct:+.2f}% MFE={max_favorable_pct:+.2f}% "
                    f"candles={coverage}"
                )

        print()
        print("=== Coverage report ===")
        print(f"  total unfilled sells:        {len(sells)}")
        print(f"  would fill (w/ candles):     {filled - fallback_no_candles}")
        print(f"  would fill (fallback only):  {fallback_no_candles}")
        print(f"  skipped (no matching buy):   {skipped_no_buy}")

        if not args.apply:
            print()
            print("DRY RUN — no writes. Re-run with --apply to persist.")
            return 0

        if not updates:
            print("Nothing to write.")
            return 0

        # Check whether peak_price column is present; only update it if it exists
        # and is NULL on the row (don't clobber a value the live writer set).
        cols = {r[1] for r in conn.execute("PRAGMA table_info(momentum_trades)").fetchall()}
        has_peak = "peak_price" in cols

        with conn:
            for mae, mfe, trough, peak, sid in updates:
                if has_peak:
                    conn.execute(
                        """
                        UPDATE momentum_trades
                        SET max_adverse_pct = ?,
                            max_favorable_pct = ?,
                            trough_price = ?,
                            peak_price = COALESCE(peak_price, ?)
                        WHERE id = ?
                        """,
                        (mae, mfe, trough, peak, sid),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE momentum_trades
                        SET max_adverse_pct = ?,
                            max_favorable_pct = ?,
                            trough_price = ?
                        WHERE id = ?
                        """,
                        (mae, mfe, trough, sid),
                    )
        print(f"Wrote {len(updates)} rows.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
