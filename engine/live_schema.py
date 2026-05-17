"""SQLite schema for the LIVE trading path (separate from paper sim_trades).

Keeps real-money tables strictly disjoint from paper tables so dashboards and
queries can't accidentally mix the two. All four tables live in candles.db
alongside the paper ones; the prefix `live_` is the disambiguator.

Tables:
  live_orders     — every Coinbase order we submit (one row per request)
  live_trades     — fills we observe (one row per filled side; round-trips
                    are pairs of buy + sell rows)
  live_positions  — currently-open positions (one row per pair we hold)
  live_equity     — periodic snapshot of cash + positions for the chart
"""
from __future__ import annotations

import sqlite3


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS live_orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_order_id TEXT NOT NULL UNIQUE,    -- our generated UUID (idempotency key)
  coinbase_order_id TEXT,                  -- Coinbase's order ID, if accepted
  ts TEXT NOT NULL,                        -- when we submitted
  pair TEXT NOT NULL,
  side TEXT NOT NULL,                      -- 'buy' | 'sell'
  order_type TEXT NOT NULL,                -- 'market' | 'limit'
  quote_size REAL,                         -- USD for buys
  base_size REAL,                          -- crypto for sells
  limit_price REAL,                        -- limit orders only
  intent TEXT,                             -- 'entry' | 'exit' | 'liquidate' | 'smoke_test'
  strategy TEXT,                           -- 'momentum_accel' | 'smoke_test' | etc
  signal_source_id INTEGER,                -- e.g. alert_id, or NULL
  result_status TEXT,                      -- 'submitted' | 'filled' | 'rejected' | 'cancelled' | 'error'
  result_message TEXT,                     -- error text or raw response excerpt
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_orders_ts ON live_orders(ts);
CREATE INDEX IF NOT EXISTS idx_live_orders_pair ON live_orders(pair);
CREATE INDEX IF NOT EXISTS idx_live_orders_coinbase_id ON live_orders(coinbase_order_id);

CREATE TABLE IF NOT EXISTS live_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_local_id INTEGER NOT NULL,         -- FK to live_orders.id
  client_order_id TEXT,
  coinbase_order_id TEXT,
  coinbase_trade_id TEXT,
  ts TEXT NOT NULL,
  pair TEXT NOT NULL,
  side TEXT NOT NULL,
  fill_price REAL NOT NULL,
  fill_size REAL NOT NULL,                 -- crypto amount filled
  fee_usd REAL NOT NULL,                   -- fee in USD on this fill
  notional_usd REAL NOT NULL,              -- price * size pre-fee
  intent TEXT,
  strategy TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(order_local_id) REFERENCES live_orders(id)
);
CREATE INDEX IF NOT EXISTS idx_live_trades_ts ON live_trades(ts);
CREATE INDEX IF NOT EXISTS idx_live_trades_pair ON live_trades(pair);

CREATE TABLE IF NOT EXISTS live_positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pair TEXT NOT NULL UNIQUE,               -- only one open position per pair
  entry_ts TEXT NOT NULL,
  entry_price REAL NOT NULL,
  entry_notional_usd REAL NOT NULL,        -- USD we spent on the entry buy
  amount REAL NOT NULL,                    -- crypto held
  fees_paid_usd REAL NOT NULL,             -- cumulative fees on this position so far
  stop_price REAL,
  trail_high REAL,                         -- highest seen since entry, for trail logic
  hard_close_ts TEXT,
  strategy TEXT,
  signal_source_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS live_equity (
  ts TEXT PRIMARY KEY,
  cash_usd REAL NOT NULL,                  -- USD available in the trading portfolio
  positions_value_usd REAL NOT NULL,       -- mark-to-market sum of open positions
  total_equity_usd REAL NOT NULL,          -- cash + positions
  realized_pnl_usd REAL NOT NULL,          -- cumulative since live trading started
  unrealized_pnl_usd REAL NOT NULL,
  open_positions INTEGER NOT NULL,
  paused INTEGER NOT NULL DEFAULT 0,       -- 1 if daily-loss kill switch active
  pause_reason TEXT
);

CREATE TABLE IF NOT EXISTS live_kill_switch (
  -- single-row table (id=1). Captures any reason live trading has been paused
  -- by code (vs the LIVE_TRADING_ENABLED env-var which is operator-controlled).
  id INTEGER PRIMARY KEY CHECK (id = 1),
  paused INTEGER NOT NULL DEFAULT 0,
  paused_at TEXT,
  reason TEXT,
  pause_until_ts TEXT,                     -- auto-resume target (e.g. daily reset)
  updated_at TEXT NOT NULL
);

INSERT OR IGNORE INTO live_kill_switch (id, paused, updated_at)
  VALUES (1, 0, datetime('now'));
"""


def init_schema(db_path: str) -> None:
    """Create the live_* tables if they don't exist. Idempotent."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.executescript(SCHEMA_SQL)
    finally:
        conn.close()
