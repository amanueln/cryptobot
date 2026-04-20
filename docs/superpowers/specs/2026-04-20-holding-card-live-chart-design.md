# Holding Card Live Chart — Design

**Date:** 2026-04-20
**Mockup reference:** [mockups/holding_card_chart_mockup.html](../../../mockups/holding_card_chart_mockup.html)

## Goal

Add a small live-updating candle chart inside each position card in the dashboard so the user can watch their open positions in real time. The chart shows entry price, current wall-aware trail stop, and a live-forming current candle. It expands to a larger modal view on click.

## User experience

The mockup captures the target UX. Key behaviors:

- **One mini chart per open position**, embedded below the PnL line of the existing position card.
- **1-minute candles by default**, with `1m` / `5m` / `15m` / `1h` toggles.
- **Live-forming last candle** — the bar for the current minute updates at 1 Hz as price ticks (open fixed at minute start, high/low expand, close follows live price). On minute close, a new bar begins.
- **Fixed rolling window** — shows the last N bars at the selected timeframe. New bars slide in from the right; older bars slide off the left. Does not accumulate indefinitely.
- **Mouse-wheel zoom** — scrolling on the chart adjusts the visible bar count (10–150 on small, 20–200 in modal). A small label shows `N bars · Mm window`.
- **Click-and-drag pan** — dragging the chart horizontally scrolls through historical bars, Webull / TradingView style. Two snap-back affordances: a `● go live` button appears bottom-right whenever the chart is panned away from the live edge, and double-clicking anywhere on the chart snaps straight back to the live edge. While panned, the live bar continues to update in the background, and the live price label remains visible on the right axis, but the amber "now" dot and the live-bar highlight only render when the viewport includes the live bar. A short drag (>4px) suppresses the click-to-expand handler so panning doesn't accidentally open the modal.
- **Entry line** (dashed blue) and **wall-aware trail line** (dashed red) overlaid, with price labels floated at the right edge.
- **Live "now" marker** — amber dot on the last bar with a dashed hairline across the chart and a price label at the right edge.
- **Expand** — clicking the chart or the ⤢ button opens a modal with the same chart at 460px height plus a 4-cell info panel (entry / now / trail stop / session peak).
- **LIVE · 1Hz pulse pill** on each chart so the liveness is visually confirmed.

## Architecture

Reuse the existing `lightweight-charts` dependency (already used by [price-chart.component.ts](../../../dashboard/ui/src/app/components/price-chart/price-chart.component.ts)). Do not build a custom canvas renderer; `lightweight-charts` handles candles, time axis, zoom/pan, crosshair, and price-line overlays natively, and it supports per-tick updates to the last bar via `series.update(bar)`.

New component `LiveCandleChartComponent` is purpose-built for the holding card use case (candles + entry line + trail line + live tick). It is intentionally separate from the existing `PriceChartComponent` because the feature surface is different — no BB/EMA/grid/indicators, but adds timeframe toggles, rolling window, and 1 Hz live updates.

Data flow:

```
Backend (Flask)                  Frontend (Angular)
───────────────                  ───────────────────
/api/candles/live    ──────►    LiveCandleChartService (poll 1 Hz)
  pair, tf, limit                  └─► LiveCandleChartComponent
  returns:                              ├─ candle series (lightweight-charts)
    - historical bars                   ├─ entry price line
    - in-progress bar                   ├─ trail price line
                                        └─ live-price marker + hairline
```

## Components

### Backend

**New endpoint:** `GET /api/candles/live?pair=X&tf=1m&limit=200`

Returns:
```json
{
  "pair": "FARTCOIN-USD",
  "tf": "1m",
  "server_time_ms": 1745193600000,
  "bars": [
    {"t": 1745190000000, "open": 0.1985, "high": 0.1992, "low": 0.1983, "close": 0.1990},
    ...
  ],
  "live": {"t": 1745193600000, "open": 0.1990, "high": 0.1997, "low": 0.1989, "close": 0.1996}
}
```

Historical bars come from the existing `candles_1m` SQLite table (or aggregated up for 5m/15m/1h — see aggregation note below). The `live` bar is constructed from:
- `open` = first price of the current minute bucket
- `high` / `low` = running min/max since minute start
- `close` = most recent price tick

The bot's `ws_matches` / price-tick stream is the source for the live bar's high/low/close. If the forming-bar state isn't already materialized in memory, the endpoint queries the latest ticks since the current minute-start and aggregates.

**Aggregation for higher timeframes:** For `5m`/`15m`/`1h`, aggregate from `candles_1m` in SQL (GROUP BY bucket). The live bar for those timeframes aggregates 1-minute bars within the current bucket plus the in-progress 1m live bar. This keeps a single source of truth.

### Frontend

**`LiveCandleChartComponent`** (new) — `dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts`

Inputs:
- `pair: string` — e.g. `"FARTCOIN-USD"`
- `entry: number` — entry price (draws blue dashed line)
- `trailStop: number` — current wall-aware stop (draws red dashed line)
- `height: number` — default 160 for card, 460 for modal

Internal state:
- `tf: '1m' | '5m' | '15m' | '1h'` — default `'1m'`
- `visibleBars: number` — default 50 for card, 100 for modal
- `chart: IChartApi` + `candleSeries: ISeriesApi<'Candlestick'>` from `lightweight-charts`
- Polling subscription: 1 Hz `/api/candles/live` fetch

Template: same layout as the mockup — top row with `tf-btn` group + `LIVE` pill + `expand` button; chart body; bottom row with legend + zoom/window label.

**`HoldingCardChartModalComponent`** (new) — modal wrapper. Opens when the small chart is clicked. Reuses `LiveCandleChartComponent` with `height=460`, defaults `visibleBars=100`. Adds the 4-cell info panel below the chart (entry / now / trail stop / session peak).

**`PositionCardsComponent`** (modify) — add `<app-live-candle-chart>` below the PnL line of each card, wire up entry/trailStop from the existing position data. Add click handler that opens the modal.

**`ApiService`** (modify) — add `getLiveCandles(pair, tf, limit)` method.

### Data flow for live updates

- Each visible `LiveCandleChartComponent` polls `/api/candles/live` once per second.
- On each poll:
  - If the server returns new closed bars (one fell off our window, a new one locked), append the new bar and drop the oldest: `candleSeries.update(newBar)` for the most recent, plus slice management for older tail.
  - Update the live-forming bar: `candleSeries.update(liveBar)` — lightweight-charts supports updating the last bar in place.
  - Update the live-price marker (a small custom series or price line at the live close).
  - Update the `now` label on the right axis.
- Timeframe switch → refetch full window at new `tf`, rebuild series.
- Zoom (mouse wheel) → adjust `visibleBars`, call `chart.timeScale().fitContent()` or set visible range.

### Polling vs WebSocket

We pick **polling at 1 Hz** for this first implementation. Rationale:
- Dashboard already polls at 60s and has a 1 Hz poller for the holding card. Same pattern.
- No new infrastructure (WebSocket server, reconnection logic, auth propagation) required.
- 1 Hz is visually indistinguishable from streaming for a chart you watch by eye.
- Upgrade to WebSocket push is a drop-in later if latency ever matters.

## Out of scope

- **Indicators** (VWAP, EMA, RSI overlays) — the mockup does not show these; the `ExpandedPairChart` component already covers indicator-heavy views elsewhere.
- **Trade markers** (buy/sell arrows on the chart) — future enhancement.
- **Multi-position comparison** — each card has its own chart; no combined view.
- **Depth/orderbook overlay** — already covered by the existing L2 ladder.
- **Pre-entry charts** (charting coins you don't hold) — scope limited to open positions.

## Files touched

- **Create:**
  - [dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts](../../../dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts)
  - [dashboard/ui/src/app/components/holding-card-chart-modal/holding-card-chart-modal.component.ts](../../../dashboard/ui/src/app/components/holding-card-chart-modal/holding-card-chart-modal.component.ts)
- **Modify:**
  - [dashboard/ui/src/app/components/position-cards/position-cards.component.ts](../../../dashboard/ui/src/app/components/position-cards/position-cards.component.ts) — embed chart + modal trigger
  - [dashboard/ui/src/app/services/api.service.ts](../../../dashboard/ui/src/app/services/api.service.ts) — add `getLiveCandles` method
  - [dashboard/api/app.py](../../../dashboard/api/app.py) — add `/api/candles/live` endpoint

## Acceptance criteria

1. Each open position in the dashboard shows a candle chart below the PnL line, defaulting to 1m / 50 bars.
2. The last candle visibly updates at 1 Hz as price ticks.
3. Entry line (blue dashed, labeled on right) and trail-stop line (red dashed, labeled) are always visible on every chart.
4. Timeframe toggle (1m / 5m / 15m / 1h) switches the chart; live bar continues to update at new timeframe.
5. Mouse-wheel zoom adjusts visible bar count; label shows the current window.
6. Click-and-drag pans the chart left/right through historical bars. When panned away from the live edge, a `● go live` button appears and returns the viewport to the live edge on click; double-clicking anywhere on the chart also snaps back to the live edge.
7. Clicking the chart (or the ⤢ button) opens a modal chart at ~460px height with the same data and 4-cell info panel. A click that was actually a drag (>4px of movement) does not open the modal.
8. Charts stop polling when the modal is closed or the card is removed (no stale intervals).
9. On dashboard tab-backgrounding, polling pauses (use `document.visibilityState` or Angular lifecycle).
10. Existing dashboard functionality (other panels, 60s refresh) is not disturbed.
