# Phase 2 — last 14d closed trades — 2026-04-19-1112

## Snapshot freshness

| source | latest row |
|---|---|
| wall_decisions | 2026-04-19T13:23:18.396814 |
| regime_snapshots | 2026-04-19T14:27:07.716982 |
| candles 1m | 2026-04-19T14:27:00 |
| momentum_trades sells | 2026-04-19T13:23:28.179795 |
| ws_matches | 2026-04-19T14:01:04.918189Z |
| l2_snapshots | 2026-04-19T14:01:04.315787 |

## Phase 2 — all closed trades (last 14d)

| id | exit_ts | pair | pnl% | peak% | comp | tape | book | micro | wall | regime | max_up | max_down | label |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 71 | 2026-04-19T13:23 | ENA-USD | +1.24 | +1.99 | +0.36 | -0.33 | -0.05 | +0.20 | +1.00 | +1.00 | +0.25 | -1.72 | **ambiguous** |
| 69 | 2026-04-18T16:00 | AVNT-USD | -3.28 | +9.79 | +0.75 | – | – | +0.50 | – | +1.00 | +13.52 | -0.53 | **freak-out** |
| 67 | 2026-04-18T11:20 | AERO-USD | -3.37 | +1.98 | -0.06 | -0.34 | +0.12 | -0.01 | – | +0.00 | +0.17 | -4.93 | **legit** |
| 65 | 2026-04-17T19:00 | FARTCOIN-USD | +0.09 | +0.74 | -0.09 | – | – | -0.09 | – | – | -0.04 | -3.68 | **legit** |
| 63 | 2026-04-17T18:32 | SAPIEN-USD | +4.56 | +4.56 | +0.42 | – | – | +0.42 | – | – | -0.84 | -10.62 | **legit** |
| 61 | 2026-04-17T15:24 | FARTCOIN-USD | +4.47 | +6.68 | +0.03 | – | – | +0.03 | – | – | -0.93 | -5.46 | **legit** |
| 59 | 2026-04-17T02:54 | AXL-USD | +6.41 | +28.84 | +0.39 | – | – | +0.39 | – | – | -3.65 | -9.67 | **legit** |
| 57 | 2026-04-16T20:10 | FARTCOIN-USD | +4.78 | +7.52 | +0.08 | – | – | +0.08 | – | – | +0.75 | -5.45 | **legit** |
| 55 | 2026-04-16T13:16 | MON-USD | +0.66 | +1.41 | -0.54 | – | – | -0.54 | – | – | -4.12 | -7.28 | **legit** |

### Summary

- n_trades analyzed: 9
- label counts: {'freak-out': 1, 'legit': 7, 'ambiguous': 1, 'no_data': 0}

### Mean signal scores by label

| label | n | tape | book | micro | wall | regime |
|---|---|---|---|---|---|---|
| ambiguous | 1 | -0.33 | -0.05 | +0.20 | +1.00 | +1.00 |
| freak-out | 1 | – | – | +0.50 | – | +1.00 |
| legit | 7 | -0.34 | +0.12 | +0.04 | – | +0.00 |
