"""Shift existing DB timestamp strings from local (America/New_York EDT, UTC-4)
to UTC by adding 4 hours. Idempotent guard: skips DBs already migrated.

Run on the Zima after the bot is stopped and DBs are backed up. Post-deploy,
all writers emit naive-UTC strings directly — this script only fixes pre-deploy rows.

Usage:
    python scripts/migrate_timestamps_to_utc.py --dry-run   # report counts, make no changes
    python scripts/migrate_timestamps_to_utc.py             # apply the shift
    python scripts/migrate_timestamps_to_utc.py --force     # re-run even if marker exists

Rules (excluded from shift):
  - candles.pair='AVNT-USD' AND granularity='ONE_MINUTE' (already UTC from rest-backfill fix)
  - early_scanner_alerts table (do not migrate)
  - signal_combo_stats table (do not migrate)
  - Unix epoch REAL columns (ts_epoch) are already UTC — never touched
"""
import argparse
import os
import sqlite3
import sys

HOURS_OFFSET = 4  # EDT → UTC

# Each entry: (db_relpath, table, column, where_clause_or_None)
JOBS: list[tuple[str, str, str, str | None]] = [
    # --- data/candles.db ---
    # NOTE: the `candles` table is INTENTIONALLY NOT migrated. Its 9M+ rows
    # are OHLCV bars; a row-by-row +4h shift hits UNIQUE(pair, granularity,
    # timestamp) collisions because the hourly series is dense (hour N+4
    # already exists as a different bar). Mis-labeling bars by 4h does not
    # change their content, and new writes post-deploy will be UTC. If a
    # clean candles TZ is needed later, re-backfill from Coinbase.

    # sim_trades
    ("data/candles.db", "sim_trades", "timestamp", None),
    ("data/candles.db", "sim_trades", "created_at", None),
    # equity_snapshots
    ("data/candles.db", "equity_snapshots", "timestamp", None),
    # ml_predictions
    ("data/candles.db", "ml_predictions", "timestamp", None),
    # pair_scans
    ("data/candles.db", "pair_scans", "timestamp", None),
    # vol_predictions
    ("data/candles.db", "vol_predictions", "timestamp", None),
    # vol_accuracy
    ("data/candles.db", "vol_accuracy", "timestamp", None),
    # grid_cycles
    ("data/candles.db", "grid_cycles", "timestamp", None),
    # self_check_log
    ("data/candles.db", "self_check_log", "timestamp", None),
    # bot_events
    ("data/candles.db", "bot_events", "timestamp", None),
    ("data/candles.db", "bot_events", "created_at", None),
    # adaptations
    ("data/candles.db", "adaptations", "timestamp", None),
    # momentum_trades
    ("data/candles.db", "momentum_trades", "timestamp", None),
    ("data/candles.db", "momentum_trades", "created_at", None),
    # momentum_equity
    ("data/candles.db", "momentum_equity", "timestamp", None),
    # momentum_events
    ("data/candles.db", "momentum_events", "timestamp", None),
    ("data/candles.db", "momentum_events", "created_at", None),
    # wall_decisions
    ("data/candles.db", "wall_decisions", "timestamp", None),
    ("data/candles.db", "wall_decisions", "created_at", None),
    # regime_snapshots
    ("data/candles.db", "regime_snapshots", "timestamp", None),
    ("data/candles.db", "regime_snapshots", "created_at", None),
    # momentum_gate_log
    ("data/candles.db", "momentum_gate_log", "timestamp", None),
    ("data/candles.db", "momentum_gate_log", "created_at", None),
    # NOTE: early_scanner_alerts + signal_combo_stats are excluded by design.

    # --- data/ws_ticks.db ---
    ("data/ws_ticks.db", "ws_ticks", "timestamp", None),
    ("data/ws_ticks.db", "ws_comparisons", "sell_time_poll", None),
    ("data/ws_ticks.db", "ws_comparisons", "sell_time_ws", None),
    ("data/ws_ticks.db", "ws_comparisons", "created_at", None),

    # --- data/market_tape.db ---
    ("data/market_tape.db", "ws_matches", "ts", None),
    ("data/market_tape.db", "l2_snapshots", "ts", None),
]

MARKER_TABLE = "migration_markers"
MARKER_KEY = "utc_shift_v1_plus4h"


def _ensure_marker_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {MARKER_TABLE} "
        "(key TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )


def _marker_present(conn: sqlite3.Connection) -> bool:
    _ensure_marker_table(conn)
    row = conn.execute(
        f"SELECT 1 FROM {MARKER_TABLE} WHERE key = ?", (MARKER_KEY,)
    ).fetchone()
    return row is not None


def _set_marker(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"INSERT OR REPLACE INTO {MARKER_TABLE} (key, applied_at) "
        "VALUES (?, datetime('now'))",
        (MARKER_KEY,),
    )


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def migrate_db(db_path: str, jobs: list[tuple[str, str, str | None]], *,
               dry_run: bool, force: bool) -> None:
    if not os.path.exists(db_path):
        print(f"[skip] {db_path} does not exist")
        return

    conn = sqlite3.connect(db_path)
    try:
        if not force and _marker_present(conn):
            print(f"[skip] {db_path} already migrated (marker present)")
            return

        total_rows_shifted = 0
        for table, column, where in jobs:
            if not _table_exists(conn, table):
                print(f"  [skip] {table}: table not present")
                continue
            if not _column_exists(conn, table, column):
                print(f"  [skip] {table}.{column}: column not present")
                continue

            where_sql = f" WHERE {where}" if where else ""
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}{where_sql} "
                f"AND {column} IS NOT NULL" if where else
                f"SELECT COUNT(*) FROM {table} WHERE {column} IS NOT NULL"
            ).fetchone()[0]

            if dry_run:
                print(f"  [dry] {table}.{column}: would shift {count} rows{where_sql}")
                continue

            # SQLite's datetime() drops fractional seconds. We preserve them by
            # shifting only the first 19 chars (YYYY-MM-DDTHH:MM:SS) and re-appending
            # whatever trailing content the original had (.microseconds, 'Z', etc.).
            sql = (
                f"UPDATE {table} SET {column} = "
                f"REPLACE(datetime(substr({column}, 1, 19), "
                f"'+{HOURS_OFFSET} hours'), ' ', 'T') || "
                f"CASE WHEN length({column}) > 19 "
                f"THEN substr({column}, 20) ELSE '' END "
                f"WHERE {column} IS NOT NULL"
            )
            if where:
                sql += f" AND ({where})"
            cur = conn.execute(sql)
            changed = cur.rowcount
            total_rows_shifted += changed
            print(f"  [done] {table}.{column}: shifted {changed} rows")

        if not dry_run:
            _set_marker(conn)
            conn.commit()
            print(f"[ok] {db_path}: {total_rows_shifted} row-updates committed, marker set")
        else:
            print(f"[dry] {db_path}: no changes written")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Report counts, make no changes")
    parser.add_argument("--force", action="store_true",
                        help="Apply even if marker is already present (dangerous)")
    parser.add_argument("--root", default=".",
                        help="Project root containing data/*.db (default: cwd)")
    args = parser.parse_args()

    # Group jobs by DB
    by_db: dict[str, list[tuple[str, str, str | None]]] = {}
    for db_rel, table, column, where in JOBS:
        by_db.setdefault(db_rel, []).append((table, column, where))

    for db_rel, jobs in by_db.items():
        db_path = os.path.abspath(os.path.join(args.root, db_rel))
        print(f"\n=== {db_path} ===")
        migrate_db(db_path, jobs, dry_run=args.dry_run, force=args.force)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
