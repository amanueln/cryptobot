# Phase 1 Case Study — 2026-04-19-1107

## Snapshot freshness

| source | latest row |
|---|---|
| wall_decisions | 2026-04-19T13:23:18.396814 |
| regime_snapshots | 2026-04-19T14:27:07.716982 |
| candles 1m | 2026-04-19T14:27:00 |
| momentum_trades sells | 2026-04-19T13:23:28.179795 |
| ws_matches | 2026-04-19T14:01:04.918189Z |
| l2_snapshots | 2026-04-19T14:01:04.315787 |

## Case: trade #59 — AXL-USD
- entry: $0.0593  exit: $0.0631  pnl: +6.41%  peak_pnl: +28.84%  hold: 4.0h
- reason: `Trail stop hit: $0.0631 <= $0.0726 (locked +6.4%)`
- exit_ts: `2026-04-17T02:54:56.556199`

### Signals at key offsets
| offset | composite | tape | book | micro | wall | regime |
|---|---|---|---|---|---|---|
| T-5m | +0.42 | – | – | +0.42 | – | – |
| T-1m | +0.39 | – | – | +0.39 | – | – |
| T+0m | +0.39 | – | – | +0.39 | – | – |
| T+1m | +0.39 | – | – | +0.39 | – | – |
| T+5m | +0.01 | – | – | +0.01 | – | – |
| T+30m | +0.30 | – | – | +0.30 | – | – |
| T+360m | -0.01 | – | – | -0.01 | – | – |

### Post-exit price path
- max_up (6h): -3.65% · max_down (6h): -9.67%
- +15m: 0.0602  +30m: 0.0606  +1h: 0.0595  +3h: 0.0589  +6h: None
- **label: `legit`**

## Case: trade #69 — AVNT-USD
- entry: $0.1553  exit: $0.1502  pnl: -3.28%  peak_pnl: +9.79%  hold: 2.0h
- reason: `Trail stop hit: $0.1502 <= $0.1679 (locked +-3.3%)`
- exit_ts: `2026-04-18T16:00:00`

### Signals at key offsets
| offset | composite | tape | book | micro | wall | regime |
|---|---|---|---|---|---|---|
| T-5m | +0.69 | – | – | +0.39 | – | +1.00 |
| T-1m | +0.74 | – | – | +0.49 | – | +1.00 |
| T+0m | +0.75 | – | – | +0.50 | – | +1.00 |
| T+1m | +0.74 | – | – | +0.48 | – | +1.00 |
| T+5m | +0.29 | – | – | +0.57 | – | +0.00 |
| T+30m | -0.15 | – | – | -0.30 | – | +0.00 |
| T+360m | -0.32 | – | – | +0.03 | -1.00 | +0.00 |

### Post-exit price path
- max_up (6h): +13.52% · max_down (6h): -0.53%
- +15m: 0.1561  +30m: 0.1547  +1h: 0.1508  +3h: None  +6h: None
- **label: `freak-out`**
