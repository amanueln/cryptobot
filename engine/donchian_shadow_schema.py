"""SQLite schema for the Donchian shadow comparison system.

Two tables:
  - donchian_shadow: every Donchian 20-period breakout signal the engine sees.
    Logged in observation-only mode. NOT used for trading decisions.

  - donchian_daily_compare: one row per day, written by the 8 AM UTC cron job.
    Aggregates yesterday's shadow trades and compares to real momentum_trades.

Both tables live in candles.db (same DB the bot uses).
"""
from __future__ import annotations

import sqlite3


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS donchian_shadow (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,                    -- ISO timestamp when the signal fired
  pair TEXT NOT NULL,
  entry_price REAL NOT NULL,           -- close at signal moment
  rolling_20h_high REAL NOT NULL,      -- the level that was broken
  breakout_pct REAL NOT NULL,          -- (entry - 20h_high) / 20h_high * 100

  -- Bot state context at signal time (informational, not used for execution)
  bot_in_position INTEGER NOT NULL DEFAULT 0,
  bot_active_pair TEXT,
  bot_unrealized_pnl_pct REAL,

  -- Gate features at signal time (for analysis - not applied as filters)
  rsi REAL,
  adx REAL,
  accel REAL,

  -- Exit outcome — filled in by the daily replay script
  replayed INTEGER NOT NULL DEFAULT 0, -- 0 = not yet replayed, 1 = done
  exit_ts TEXT,
  exit_price REAL,
  exit_reason TEXT,                    -- 'trail' | 'stop' | 'time' | 'data_end'
  pnl_pct REAL,
  peak_pct REAL,
  mae_pct REAL,
  hours_held REAL,
  net_usd REAL,                        -- $3000 position - 1.2% fees applied

  -- Sequential-queue flag (option A simulation)
  -- 1 = this signal was "taken" in the single-position simulation
  -- 0 = skipped because a prior shadow trade was still open at this ts
  kept_in_queue INTEGER DEFAULT 0,

  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_donch_shadow_ts ON donchian_shadow(ts);
CREATE INDEX IF NOT EXISTS idx_donch_shadow_pair_ts ON donchian_shadow(pair, ts);
CREATE INDEX IF NOT EXISTS idx_donch_shadow_replayed ON donchian_shadow(replayed);


CREATE TABLE IF NOT EXISTS donchian_daily_compare (
  date TEXT PRIMARY KEY,               -- 'YYYY-MM-DD' UTC

  -- Donchian (shadow) numbers
  donch_n_signals INTEGER NOT NULL,    -- total Donchian fires that day
  donch_n_kept INTEGER NOT NULL,       -- after single-position queue dedup
  donch_wins INTEGER NOT NULL,
  donch_pnl_usd REAL NOT NULL,
  donch_biggest_win REAL,
  donch_biggest_loss REAL,
  donch_avg_hold_h REAL,

  -- Real bot numbers (from momentum_trades)
  real_n INTEGER NOT NULL,
  real_wins INTEGER NOT NULL,
  real_pnl_usd REAL NOT NULL,
  real_biggest_win REAL,
  real_biggest_loss REAL,

  -- Comparison
  delta_usd REAL NOT NULL,             -- donch_pnl_usd - real_pnl_usd
  real_in_cash_all_day INTEGER NOT NULL DEFAULT 0, -- 1 if real_n == 0, flag for "not a fair comparison"

  -- Bookkeeping
  created_at TEXT NOT NULL
);
"""


def init_schema(db_path: str) -> None:
    """Create donchian_shadow + donchian_daily_compare tables and indexes."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()
