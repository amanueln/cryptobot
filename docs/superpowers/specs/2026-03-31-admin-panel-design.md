# Command Center Admin Panel — Design Spec

## Goal

Replace the current 7-tab Angular dashboard with a single scrollable "Command Center" page that consolidates all essential bot monitoring into one view. Pair detail charts are accessible via click-to-expand cards instead of separate tab navigation.

## Architecture

The Command Center is a new Angular standalone component that replaces the current tab-based routing. It reuses existing API endpoints and charting libraries (lightweight-charts for candlesticks, Chart.js for equity curve). The existing reusable components (price-chart, indicator-panel, trade-log, position-cards, stats-bar) are composed into a single vertical layout. Minor backend additions: trade regime snapshots on trade records, and an optional `/api/events` endpoint for the activity log.

## Tech Stack

- **Angular 20.1** (standalone components, signals for state)
- **lightweight-charts 5.1.0** — candlestick charts, EMAs, Bollinger Bands, grid levels, trade markers
- **Chart.js 4.5.1** — equity curve with drawdown overlay
- **Tailwind CSS 4.2.2** — layout and styling
- **RxJS** — HTTP polling (existing intervals from api.service.ts)

---

## Section 1: Status Banner

Full-width bar at the top of the page.

**Contents:**
- **Status dot** (left): Green = running, Red = stopped/error, Yellow = degraded (e.g., pair scan in progress)
- **Status text**: One-liner in plain English. Examples:
  - "Bot is running · watching 3 pairs"
  - "Bot stopped · last active 2h ago"
  - "Bot is running · scanning for new pairs..."
- **Last action subtitle**: "Bought 42,000 NKN at $0.0139 · 12 min ago · Grid level 4 triggered"
- **Quick stats** (right side): Equity, Net P&L, Trade count, Uptime — pulled from existing `/api/status` endpoint
- **Tools button** (far right): Dropdown that reveals links to Simulator, Regime Visualizer, and Self-Check (these load below the main content or as modal overlays)

**Data source:** `/api/status` (polled every 60s, same as current stats-bar)

---

## Section 2: Equity Chart + Activity Log (side by side)

Two-column layout below the status banner.

### Left column (~60%): Portfolio Equity Chart

- Line chart showing portfolio equity over time (default 72h, with 24h/7d/30d toggle)
- Green/red dots on the line at trade points
- Drawdown overlay on secondary y-axis (same as current equity-curve component)
- Sub-stats below chart: Realized P&L, Unrealized P&L, Total Fees, Max Drawdown %
- **Reuse:** Existing `equity-curve.component.ts` chart logic, adapted to fit the narrower width

**Data source:** `/api/equity?hours=72`, `/api/status` for sub-stats

### Right column (~40%): Live Activity Log

Scrolling feed of bot actions in plain English. Each entry has:
- **Relative timestamp** (e.g., "12m ago", "1.5h ago")
- **Color-coded action type + description:**
  - Green "Bought" — "42,000 NKN at $0.0139"
  - Red "Sold" — "15,000 NKN at $0.0152 → +$0.19 profit"
  - Blue "ATR adjusted" — "NKN spacing to 1.3x"
  - Purple "Vol check" — "passed — all models within tolerance"
  - Yellow "Range recalc" — "NOM — new range $0.0017–$0.0045"
  - Gray "Scan complete" — "3 pairs confirmed, no swaps"
- **Sub-detail line** explaining why (e.g., "Grid level 4 — price dipped below $0.014")

The activity log is a **new component** that aggregates data from multiple existing endpoints into a unified chronological feed:
- Trades from `/api/trades`
- Status changes from `/api/status`
- Scan results from `/api/pair-scans/latest`
- Self-check results from `/api/self-check`
- Health/vol events from `/api/health`

The log auto-scrolls to show newest entries at the top. Maximum ~50 entries visible, older entries discarded from the DOM. Polling interval: 60s (same as status).

---

## Section 3: Pair Cards (Click-to-Expand)

Row of cards, one per active pair. Flexbox with wrapping.

### Collapsed state (default)

Each card shows:
- **Pair name** (e.g., "NKN-USD") + **Regime badge** (Ranging/Volatile/Trending/Squeeze/Crash — color-coded, same palette as regime-visualizer)
- **2x3 stat grid:** Price, P&L, Grid fill (X/10 held), ATR multiplier, Trade count, Vol R² status
- **Grid fill progress bar** at the bottom

### Expanded state (one at a time)

Click a card → it gets a highlighted border (yellow). Other cards dim to 70% opacity. Below all cards, an **expanded chart panel** slides open (animated, ~400ms).

The expanded panel contains:

#### A. Candlestick Chart
- 4h candles, 7 days of data (configurable via small timeframe selector: 1h/4h/1d)
- Overlays: EMA 50 (yellow), EMA 200 (cyan), Bollinger Bands (blue dashed)
- Grid levels: buy levels (green dashed), sell levels (red dashed)
- Grid range boundaries (gray dashed at top/bottom)
- Current price horizontal line
- **Trade markers with regime annotations:**
  - Green upward triangle at buy prices, labeled "BUY $0.0128"
  - Red downward triangle at sell prices, labeled "SELL $0.0152 → +$0.19"
  - Below each marker label: regime + key indicators at time of trade (e.g., "Ranging · ADX 18 · RSI 48")
- Chart legend in top-right corner

**Reuse:** Existing `price-chart.component.ts` handles all of this — candlesticks, EMAs, Bollinger, grid levels, trade markers. The regime annotation on markers is new and requires the trade's snapshot of ADX/RSI/regime at execution time.

**Data sources:**
- `/api/candles?pair=NKN-USD&hours=168` (7 days)
- `/api/indicators?pair=NKN-USD`
- `/api/grid-levels?pair=NKN-USD`
- `/api/trades?pair=NKN-USD`

#### B. Indicator Strip
Four equal-width sub-charts in a horizontal row below the candlestick chart:
- **ADX** — line chart, current value badge, threshold line at 25
- **RSI** — line chart, overbought (70) / oversold (30) zones shaded
- **Volume** — bar chart, green/red per candle direction
- **OBV** — line chart, trend arrow badge

**Reuse:** Existing `indicator-panel.component.ts` renders these exact sub-charts.

**Data source:** `/api/indicators?pair=NKN-USD`

#### Expand/collapse behavior
- Click an expanded card again → collapse (chart panel slides closed)
- Click a different card while one is expanded → swap (collapse current, expand new)
- Only one card expanded at a time
- On initial page load, all cards are collapsed

---

## Section 4: Health Bar

Single compact row spanning full width.

**Contents (inline, separated by spacing):**
- Daily P&L: "+$4.30 / -$30 limit"
- Weekly P&L: "+$12.40 / -$75 limit"
- Win/loss streak: "3 winning days"
- Vol accuracy: "8.3% avg error"
- Next scan countdown: "2h 15m"

Colors: green if healthy, yellow if approaching limits (>60% of loss limit), red if breached.

**Data source:** `/api/self-check`, `/api/status`, `/api/health`

---

## Section 5: Positions & Trade History Table

Standard table at the bottom.

**Columns:** Pair, Side (Buy/Sell), Qty, Entry Price, Current Price, P&L, Time

- Open positions: full opacity, sorted by most recent first
- Recent closed trades: 60% opacity, below open positions
- Default: show last 20 entries (10 open + 10 recent)
- "Show more" link to load additional history

**Data source:** `/api/positions`, `/api/trades`

---

## Section 6: Tools Dropdown

Clicking the "Tools" button in the status banner reveals a dropdown menu with:
- **Simulator** — loads the existing `dca-simulator` component
- **Regime Visualizer** — loads the existing `regime-visualizer` component
- **Self-Check** — loads the existing `self-check` component

These open as **full-width sections** appended below the positions table (push page content, not modals). Each has a close/collapse button. Only one tool section open at a time.

---

## New Backend Requirement: Trade Regime Snapshots

The trade annotations on the candlestick chart need to show what regime/indicators the bot saw at the time of each trade. This requires storing a snapshot with each trade.

**What to store per trade (new fields on trade records):**
- `regime`: string (e.g., "Ranging", "Volatile")
- `adx`: float (e.g., 18.2)
- `rsi`: float (e.g., 48.1)
- `atr_multiplier`: float (e.g., 1.3)
- `trigger_reason`: string (e.g., "Grid level 4 — price crossed $0.014")

**Where to add it:** The grid strategy's trade execution path should attach these fields when recording a trade. The `/api/trades` endpoint should return them.

If historical trades don't have this data, the chart should gracefully show markers without annotations (just "BUY $0.0128" with no regime line).

---

## New Component: Activity Log

A new standalone Angular component that aggregates events into a unified chronological feed.

**Event types and sources:**
| Event | Source | Color |
|-------|--------|-------|
| Trade executed (buy/sell) | `/api/trades` | Green/Red |
| ATR spacing adjusted | `/api/status` or new field | Blue |
| Vol check result | `/api/self-check` | Purple |
| Range recalculated | `/api/status` or new field | Yellow |
| Scan completed | `/api/pair-scans/latest` | Gray |
| Pair swapped in/out | `/api/pair-scans/latest` | Orange |
| Error/warning | `/api/health` | Red |

**Implementation:** Poll each source on the existing intervals. Merge into a single time-sorted array. Deduplicate by event type + timestamp. Cap at 50 entries in the DOM.

For ATR adjustments and range recalculations, the backend currently doesn't emit discrete events. Two options:
1. **Preferred:** Add a lightweight `/api/events` endpoint that returns recent bot events (the bot already logs these — expose the log)
2. **Fallback:** Diff the `/api/status` response between polls to detect changes (ATR multiplier changed, range changed)

---

## Routing Changes

**Before (7 routes):**
```
/                → EquityCurveComponent
/pair/:symbol    → PairViewComponent
/ml-brain        → MlBrainComponent
/pair-scanner    → PairScannerComponent
/simulator       → DcaSimulatorComponent
/regime          → RegimeVisualizerComponent
/self-check      → SelfCheckComponent
```

**After (1 primary route):**
```
/                → CommandCenterComponent
```

The old routes can be kept as redirects to `/` for backwards compatibility, or removed entirely.

---

## Component Breakdown

| Component | New/Reuse | Purpose |
|-----------|-----------|---------|
| `CommandCenterComponent` | **New** | Page shell, section layout, pair expand/collapse state |
| `StatusBannerComponent` | **New** | Status dot, text, quick stats, tools button |
| `ActivityLogComponent` | **New** | Chronological event feed |
| `PairCardComponent` | **New** | Collapsed pair card with stats |
| `ExpandedPairChartComponent` | **New** (composes existing) | Wraps price-chart + indicator-panel for inline expansion |
| `HealthBarComponent` | **New** | Compact health metrics row |
| `ToolsDropdownComponent` | **New** | Dropdown menu for hidden tools |
| `EquityCurveComponent` | **Reuse** (adapt) | Equity chart, narrower width |
| `PriceChartComponent` | **Reuse** | Candlestick chart with all overlays |
| `IndicatorPanelComponent` | **Reuse** | ADX/RSI/Volume/OBV strip |
| `TradeLogComponent` | **Reuse** | Positions + trade history table |
| `DcaSimulatorComponent` | **Reuse** | Hidden behind Tools |
| `RegimeVisualizerComponent` | **Reuse** | Hidden behind Tools |
| `SelfCheckComponent` | **Reuse** | Hidden behind Tools |

---

## Design Tokens (consistent with current theme)

```
Background:       #0f1117
Card background:  #1a1d2e
Border:           #2d3148
Text primary:     #e2e8f0
Text secondary:   #9ca3af
Text muted:       #6b7280
Text dimmed:      #4b5563
Green (positive): #4ade80
Red (negative):   #f87171
Blue (info):      #60a5fa
Purple (AI/vol):  #c084fc
Yellow (caution): #fbbf24
Cyan (EMA200):    #22d3ee
Pink (RSI):       #f472b6
```

---

## Out of Scope

- Mobile-specific layout (desktop-first, flexbox wrapping handles smaller screens adequately)
- Real-time WebSocket updates (keep existing polling approach)
- New backend API beyond trade regime snapshots and optional `/api/events`
- Drag-and-drop section reordering
- User preferences / layout customization
