# Data Collection — Schema Reference

This directory holds all runtime state for the bot. Tables are split across
two SQLite files for isolation (see the "Isolation contract" section below).

## Files

| File              | Written by                         | Purpose                          |
|-------------------|------------------------------------|----------------------------------|
| `candles.db`      | engine / trade logger (main thread) | candles, trades, gate/wall logs, regime snapshots |
| `market_tape.db`  | `MarketTapeRecorder` (own thread)  | high-frequency `ws_matches` + `l2_snapshots` |
| `ws_ticks.db`     | `WSRecorder`                       | per-trade ticker tape (legacy, kept for stop-diff comparisons) |

The dashboard's `/api/download-db` endpoint zips all three files into
`cryptobot_data.zip` for handoff.

## Tables in `candles.db`

### `wall_decisions`
Every wall-aware trail-stop evaluation. **Use to answer**: *"was this exit a
real signal or noise?"* — the core signal-persistence question driving this
data collection phase.

| col               | type    | meaning                                              |
|-------------------|---------|------------------------------------------------------|
| `timestamp`       | TEXT    | engine-side ISO timestamp                            |
| `pair`            | TEXT    | trading pair                                         |
| `action`          | TEXT    | `anchor`, `cleared`, `raised`                        |
| `detail`          | TEXT    | human-readable reason                                |
| `current_price`   | REAL    | tick price at decision                               |
| `wall_aware_stop` | REAL    | stop level that decision produced                    |
| `entry_price`     | REAL    | entry                                                |
| `peak_price`      | REAL    | running peak at decision                             |
| `wall_price`      | REAL    | price level of the anchored wall (null if cleared)   |
| `wall_usd`        | REAL    | wall size in USD                                     |
| `wall_age_ms`     | INTEGER | how long the wall had been sitting there             |
| `book_bids`       | TEXT    | JSON: top-5 bids `[[price, size], ...]`              |
| `book_asks`       | TEXT    | JSON: top-5 asks                                     |

Written by `engine/momentum_engine.py::_record_wall_decision()` into
`_wall_decisions_unwritten`; drained every 1s by `sim_runner._book_writer_loop`.

### `momentum_trades` — new MAE/MFE columns
Added via ALTER TABLE. **Use to answer**: *"are our stops too tight?"* and
*"how much did we leave on the table?"*

| col                 | type | meaning                                                    |
|---------------------|------|------------------------------------------------------------|
| `max_adverse_pct`   | REAL | worst unrealized P&L during hold (% from entry, negative)  |
| `max_favorable_pct` | REAL | best unrealized P&L during hold (% from entry)             |
| `trough_price`      | REAL | lowest observed price during hold (drives `max_adverse`)   |

Updated at candle close, 60s trail check, and each 1Hz `refresh_live_state`
tick, then finalized on exit.

### `regime_snapshots`
One row per scan cycle. **Use to answer**: *"does our edge only exist in
certain market regimes?"*

| col                | type    | meaning                                          |
|--------------------|---------|--------------------------------------------------|
| `btc_price`        | REAL    | current BTC close                                |
| `btc_ma`           | REAL    | regime-MA (REGIME_MA hourly bars)                |
| `regime_state`     | TEXT    | `bullish` / `bearish` / `unknown`                |
| `regime_bullish`   | INTEGER | 0/1                                              |
| `btc_4h_return`    | REAL    | % change vs 5 hourly closes ago                  |
| `btc_24h_return`   | REAL    | % change vs 25 hourly closes ago                 |
| `scans_pass`       | INTEGER | pairs that passed gate this cycle                |
| `scans_fail`       | INTEGER | pairs that failed                                |
| `holdings_count`   | INTEGER | open positions                                   |

Written by `sim_runner._poll_momentum` after `info_scan`.

## Tables in `market_tape.db`

### `ws_matches`
Every executed trade on watched pairs from Coinbase's `market_trades` WS
channel. **Use to answer**: *"are the walls real flow or spoofing?"* and
*"what was aggressive-buy vs aggressive-sell pressure before the exit?"*

| col        | type | meaning                                 |
|------------|------|-----------------------------------------|
| `ts`       | TEXT | exchange-side ISO timestamp             |
| `ts_epoch` | REAL | client-side receive time                |
| `pair`     | TEXT | trading pair                            |
| `trade_id` | TEXT | Coinbase trade id                       |
| `price`    | REAL | fill price                              |
| `size`     | REAL | fill size (base currency)               |
| `side`     | TEXT | `BUY` / `SELL` (aggressor side)         |

Indexed on `(pair, ts_epoch)`.

### `l2_snapshots`
Full 50-level order book snapshot per pair, written every
`l2_snapshot_interval_sec` (default 5s). **Use to answer**: spoofing
detection, order-book imbalance features, L2-aware sim backtests.

| col          | type | meaning                                  |
|--------------|------|------------------------------------------|
| `ts`         | TEXT | snapshot ISO timestamp                   |
| `ts_epoch`   | REAL | snapshot epoch                           |
| `pair`       | TEXT | trading pair                             |
| `mid`        | REAL | (best_bid + best_ask) / 2                |
| `spread_bps` | REAL | spread in basis points                   |
| `bids`       | TEXT | JSON: `[[price, size], ... × depth]`     |
| `asks`       | TEXT | JSON: same for asks                      |

Indexed on `(pair, ts_epoch)`.

## 1-minute candles

Stored in the existing `candles` table with `granularity = 'ONE_MINUTE'`.
Backfilled via `scripts/backfill_1m.py` (no persistent 1m poller yet — run
the script periodically or before an analysis session).

```
py scripts/backfill_1m.py                 # last 7 days, watched pairs
py scripts/backfill_1m.py --days 30
py scripts/backfill_1m.py --pairs BTC-USD --days 3
```

## Isolation contract

The market tape recorder writes to its own DB file on its own thread with
fail-silent error handling and a config kill switch. This is by design: a WS
crash or SQLite contention must never impact the engine's trading loop.

| requirement         | implementation                                    |
|---------------------|---------------------------------------------------|
| Separate DB         | `data/market_tape.db`                             |
| Dedicated thread    | `MarketTapeRecorder` runs its own `ws` + `snap` threads |
| Batched writes      | matches: every 100 msgs OR 5s; L2: every 5s       |
| Fail-silent         | `try/except` on `on_message`, `_flush_matches`, `_snapshot_loop`; errors increment `stats.errors` and continue |
| Kill switch         | `market_tape.enabled: false` in `config/bot_config.yaml` |

Phases that write into `candles.db` (wall_decisions, MAE/MFE cols,
regime_snapshots) are low-frequency, engine-thread-safe, and need no
isolation.
