"""SQLite schema for the scanner bot.

Tables live in candles.db (the same DB the early scanner uses), all prefixed
scanner_bot_ to keep them isolated from existing engines.
"""
from __future__ import annotations

import sqlite3


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scanner_bot_positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id INTEGER NOT NULL,
  combo_key TEXT NOT NULL,
  pair TEXT NOT NULL,
  entry_ts TEXT NOT NULL,
  entry_price REAL NOT NULL,
  position_usd REAL NOT NULL,
  shares REAL NOT NULL,
  stop_price REAL NOT NULL,
  hard_close_ts TEXT NOT NULL,
  manual_sell_requested INTEGER DEFAULT 0,
  milestones_hit TEXT DEFAULT '[]',
  current_price REAL,
  current_pct REAL,
  peak_price REAL,
  last_tick_ts TEXT,
  trail_stop_price REAL,
  trough_price REAL
);

CREATE INDEX IF NOT EXISTS idx_sbp_pair ON scanner_bot_positions (pair);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sbp_alert ON scanner_bot_positions (alert_id);

CREATE TABLE IF NOT EXISTS scanner_bot_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id INTEGER NOT NULL,
  combo_key TEXT NOT NULL,
  pair TEXT NOT NULL,
  entry_ts TEXT NOT NULL,
  entry_price REAL NOT NULL,
  exit_ts TEXT NOT NULL,
  exit_price REAL NOT NULL,
  position_usd REAL NOT NULL,
  shares REAL NOT NULL,
  gross_pnl_usd REAL NOT NULL,
  fees_usd REAL NOT NULL,
  net_pnl_usd REAL NOT NULL,
  pct REAL NOT NULL,
  peak_pct REAL NOT NULL,
  exit_reason TEXT NOT NULL,
  max_adverse_pct REAL
);

CREATE INDEX IF NOT EXISTS idx_sbt_pair ON scanner_bot_trades (pair);
CREATE INDEX IF NOT EXISTS idx_sbt_exit_ts ON scanner_bot_trades (exit_ts);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sbt_alert ON scanner_bot_trades (alert_id);

CREATE TABLE IF NOT EXISTS scanner_bot_equity (
  ts TEXT PRIMARY KEY,
  cash_usd REAL NOT NULL,
  positions_value_usd REAL NOT NULL,
  total_equity_usd REAL NOT NULL,
  open_positions INTEGER NOT NULL,
  realized_pnl_usd REAL NOT NULL,
  unrealized_pnl_usd REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS scanner_bot_alert_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  alert_id INTEGER NOT NULL,
  ts TEXT NOT NULL,
  combo_key TEXT NOT NULL,
  pair TEXT NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_sbad_ts ON scanner_bot_alert_decisions (ts);
"""


def init_schema(db_path: str) -> None:
    """Create scanner_bot_* tables and indexes if they don't already exist."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        # executescript() issues an implicit COMMIT before running the script,
        # so no explicit conn.commit() is needed afterwards.
        conn.executescript(SCHEMA_SQL)

        # Migrations — each is live-DB safe (no-op if column already exists)
        for stmt in (
            "ALTER TABLE scanner_bot_positions ADD COLUMN trail_stop_price REAL",
            "ALTER TABLE scanner_bot_positions ADD COLUMN trough_price REAL",
            "ALTER TABLE scanner_bot_trades ADD COLUMN max_adverse_pct REAL",
        ):
            try:
                conn.execute(stmt)
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
    finally:
        conn.close()
