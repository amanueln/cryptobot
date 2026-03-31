# Command Center Admin Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 7-tab dashboard with a single scrollable Command Center page that shows status, equity, activity log, expandable pair charts with trade annotations, health bar, and positions — all in one view.

**Architecture:** New `CommandCenterComponent` composes existing reusable components (price-chart, indicator-panel, trade-log) into a vertical layout. Two small backend additions: (1) `bot_events` table + `/api/events` endpoint for the activity log, (2) regime snapshot fields on trade records for chart annotations. All other data comes from existing API endpoints.

**Tech Stack:** Angular 20.1, lightweight-charts 5.1.0, Chart.js 4.5.1, Tailwind CSS 4.2.2, Flask REST API, SQLite

**Spec:** `docs/superpowers/specs/2026-03-31-admin-panel-design.md`

---

## File Structure

### Backend (Python)

| File | Action | Responsibility |
|------|--------|----------------|
| `data/trade_logger.py` | Modify | Add `bot_events` table, `log_event()` method, regime columns on `sim_trades` |
| `exchange/models.py` | Modify | Add regime snapshot fields to `Signal` dataclass |
| `strategies/grid_strategy.py` | Modify | Attach regime/ADX/RSI/ATR to signals when generating trades |
| `dashboard/api/app.py` | Modify | Add `/api/events` endpoint, return regime fields from `/api/trades` |

### Frontend (Angular) — New Components

| File | Responsibility |
|------|----------------|
| `dashboard/ui/src/app/components/command-center/command-center.component.ts` | Page shell, section layout, pair expand/collapse state |
| `dashboard/ui/src/app/components/status-banner/status-banner.component.ts` | Status dot, plain-English text, quick stats, tools dropdown |
| `dashboard/ui/src/app/components/activity-log/activity-log.component.ts` | Scrolling plain-English event feed |
| `dashboard/ui/src/app/components/pair-card/pair-card.component.ts` | Collapsed pair summary card |
| `dashboard/ui/src/app/components/expanded-pair-chart/expanded-pair-chart.component.ts` | Wraps price-chart + indicator-panel for inline expansion |
| `dashboard/ui/src/app/components/health-bar/health-bar.component.ts` | Compact health metrics row |

### Frontend — Modified Files

| File | Action | What Changes |
|------|--------|--------------|
| `dashboard/ui/src/app/app.ts` | Modify | Remove tab navigation, render CommandCenter directly |
| `dashboard/ui/src/app/app.routes.ts` | Modify | Single route → CommandCenterComponent |
| `dashboard/ui/src/app/services/api.service.ts` | Modify | Add `fetchEvents()`, add `EventData` interface, add regime fields to `TradeData` |

---

## Task 1: Backend — Event Logging System

Add a `bot_events` table and `/api/events` endpoint so the activity log has a unified event stream.

**Files:**
- Modify: `data/trade_logger.py`
- Modify: `dashboard/api/app.py`

- [ ] **Step 1: Add bot_events table to trade_logger.py**

In `data/trade_logger.py`, find the `_init_db` method that creates tables. Add the `bot_events` table and the `log_event()` method.

Find the `CREATE TABLE IF NOT EXISTS sim_trades` block in `_init_db`. After it, add:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS bot_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        pair TEXT,
        title TEXT NOT NULL,
        detail TEXT,
        created_at TEXT NOT NULL
    )
""")
```

Then add a new method to the `TradeLogger` class:

```python
def log_event(self, event_type: str, title: str, detail: str = "", pair: str = "") -> None:
    """Log a bot event for the activity feed.

    event_type: trade_buy, trade_sell, atr_adjust, vol_check, range_recalc, scan_complete, pair_swap, error
    """
    conn = sqlite3.connect(self.db_path)
    try:
        conn.execute(
            """INSERT INTO bot_events (timestamp, event_type, pair, title, detail, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(),
                event_type,
                pair,
                title,
                detail,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 2: Add /api/events endpoint to app.py**

In `dashboard/api/app.py`, add a new route. Find an appropriate location near the other `/api/` routes and add:

```python
@app.route("/api/events")
def api_events():
    limit = int(request.args.get("limit", 50))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM bot_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception:
        return jsonify([])
    finally:
        conn.close()
```

- [ ] **Step 3: Emit events from grid_strategy trade signals**

In `engine/bot_engine.py`, find where `trade_logger.log_trade(trade)` is called. After that call, add event logging:

```python
event_type = "trade_buy" if trade.side == "buy" else "trade_sell"
title = f"{'Bought' if trade.side == 'buy' else 'Sold'} {trade.amount:,.0f} {trade.pair.replace('-USD', '')} at ${trade.price}"
detail = trade.reason
self.trade_logger.log_event(event_type, title, detail, pair=trade.pair)
```

- [ ] **Step 4: Emit events for ATR spacing changes**

In `strategies/grid_strategy.py`, find the `_maybe_recalc_range` method where the ATR spacing multiplier is applied. After the spacing is recalculated, emit an event. Find the line where `self._vol_spacing_multiplier` is set (or where the new spacing is computed) and add:

```python
# After spacing multiplier is computed and applied
if hasattr(self, '_trade_logger') and self._trade_logger:
    old_mult = getattr(self, '_prev_atr_mult', 1.0)
    new_mult = self._vol_spacing_multiplier
    if abs(new_mult - old_mult) > 0.05:
        direction = "widened" if new_mult > old_mult else "narrowed"
        self._trade_logger.log_event(
            "atr_adjust",
            f"{self.pair.replace('-USD', '')} spacing {direction} to {new_mult:.1f}x",
            f"ATR moved from ${self._atr_mean:.6f} avg to ${self._atr_current:.6f} current",
            pair=self.pair,
        )
        self._prev_atr_mult = new_mult
```

Also initialize `self._prev_atr_mult = 1.0` in `__init__` and `self._trade_logger = None`. The trade_logger needs to be injected — in `engine/bot_engine.py` where the strategy is created, set `engine.strategy._trade_logger = engine.trade_logger`.

- [ ] **Step 5: Test the events system**

Run the bot briefly or use the simulator to verify events are being written:

```bash
cd /c/Users/Nathan/cryptobot
python -c "
from data.trade_logger import TradeLogger
tl = TradeLogger('data/candles.db')
tl.log_event('test', 'Test event', 'Testing the event system')
import sqlite3
conn = sqlite3.connect('data/candles.db')
rows = conn.execute('SELECT * FROM bot_events ORDER BY id DESC LIMIT 5').fetchall()
for r in rows:
    print(r)
conn.close()
"
```

Expected: See the test event row printed.

- [ ] **Step 6: Commit**

```bash
git add data/trade_logger.py dashboard/api/app.py engine/bot_engine.py strategies/grid_strategy.py
git commit -m "feat: add bot_events table and /api/events endpoint for activity log"
```

---

## Task 2: Backend — Trade Regime Snapshots

Add regime/ADX/RSI/ATR fields to trade records so chart markers can show what the bot was seeing at trade time.

**Files:**
- Modify: `exchange/models.py`
- Modify: `data/trade_logger.py`
- Modify: `strategies/grid_strategy.py`
- Modify: `dashboard/api/app.py`

- [ ] **Step 1: Add regime fields to Signal dataclass**

In `exchange/models.py`, find the `Signal` dataclass. Add these optional fields:

```python
regime: str = ""
adx: float = 0.0
rsi: float = 0.0
atr_multiplier: float = 1.0
```

- [ ] **Step 2: Add regime columns to sim_trades table**

In `data/trade_logger.py`, find the `CREATE TABLE IF NOT EXISTS sim_trades` statement. Add new columns at the end (before the closing parenthesis):

```sql
regime TEXT DEFAULT '',
adx REAL DEFAULT 0,
rsi REAL DEFAULT 0,
atr_multiplier REAL DEFAULT 1.0
```

Also update the `log_trade` method's INSERT statement to include these fields. Find the INSERT and update it:

```python
def log_trade(self, trade: Trade) -> None:
    conn = sqlite3.connect(self.db_path)
    try:
        conn.execute(
            """INSERT INTO sim_trades
               (timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason, created_at,
                regime, adx, rsi, atr_multiplier)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.timestamp.isoformat(),
                trade.pair,
                trade.side,
                trade.price,
                trade.amount,
                trade.cost_usd,
                trade.fee,
                trade.strategy,
                trade.reason,
                datetime.now().isoformat(),
                getattr(trade, 'regime', ''),
                getattr(trade, 'adx', 0.0),
                getattr(trade, 'rsi', 0.0),
                getattr(trade, 'atr_multiplier', 1.0),
            ),
        )
        conn.commit()
    finally:
        conn.close()
```

Since the Trade dataclass may not have these fields, use `getattr` with defaults. If the Trade dataclass is in `exchange/models.py`, add the same fields there:

```python
regime: str = ""
adx: float = 0.0
rsi: float = 0.0
atr_multiplier: float = 1.0
```

- [ ] **Step 3: Attach regime data to signals in grid_strategy.py**

In `strategies/grid_strategy.py`, find the `on_candle` method where buy and sell `Signal` objects are created (the `signals.append(Signal(...))` calls).

For each Signal creation, add the regime snapshot fields. The strategy already has access to regime, ADX, RSI via its internal state. Find the buy signal creation and add:

```python
signals.append(Signal(
    action="buy",
    pair=self.pair,
    price=candle.close,
    order_type="limit",
    amount_usd=self.investment_per_grid,
    limit_price=level.price,
    reason=f"grid buy at {level.price:.2f}",
    regime=getattr(self, '_current_regime', ''),
    adx=getattr(self, '_last_adx', 0.0),
    rsi=getattr(self, '_last_rsi', 0.0),
    atr_multiplier=getattr(self, '_vol_spacing_multiplier', 1.0),
))
```

Do the same for sell signals.

- [ ] **Step 4: Pass regime fields from Signal to Trade**

In `engine/simulator.py`, find where Trade objects are created from Signal objects. Add the regime fields:

```python
trade = Trade(
    timestamp=...,
    pair=signal.pair,
    side=signal.action,
    price=fill_price,
    amount=amount,
    cost_usd=cost,
    fee=fee,
    strategy=...,
    reason=signal.reason,
    regime=getattr(signal, 'regime', ''),
    adx=getattr(signal, 'adx', 0.0),
    rsi=getattr(signal, 'rsi', 0.0),
    atr_multiplier=getattr(signal, 'atr_multiplier', 1.0),
)
```

- [ ] **Step 5: Return regime fields from /api/trades**

In `dashboard/api/app.py`, find the `/api/trades` route handler. Where it builds the trade dict to return, add the new fields:

```python
"regime": row["regime"] if "regime" in row.keys() else "",
"adx": row["adx"] if "adx" in row.keys() else 0,
"rsi": row["rsi"] if "rsi" in row.keys() else 0,
"atr_multiplier": row["atr_multiplier"] if "atr_multiplier" in row.keys() else 1.0,
```

Use conditional checks so old trade records without these columns don't break.

- [ ] **Step 6: Run existing tests**

```bash
cd /c/Users/Nathan/cryptobot
python -m pytest tests/ -v --tb=short 2>&1 | head -60
```

Expected: All existing tests still pass. The new columns have defaults, so old code paths are unaffected.

- [ ] **Step 7: Commit**

```bash
git add exchange/models.py data/trade_logger.py strategies/grid_strategy.py engine/simulator.py dashboard/api/app.py
git commit -m "feat: add regime/ADX/RSI/ATR snapshots to trade records for chart annotations"
```

---

## Task 3: Frontend — API Service Updates + EventData Interface

Add the `EventData` interface, `fetchEvents()` method, and regime fields to `TradeData`.

**Files:**
- Modify: `dashboard/ui/src/app/services/api.service.ts`

- [ ] **Step 1: Add EventData interface**

In `api.service.ts`, after the `UpdateResult` interface (near line 258), add:

```typescript
export interface EventData {
  id: number;
  timestamp: string;
  event_type: string;
  pair: string;
  title: string;
  detail: string;
}
```

- [ ] **Step 2: Add regime fields to TradeData**

In `api.service.ts`, find the `TradeData` interface. Add these fields at the end:

```typescript
regime: string;
adx: number;
rsi: number;
atr_multiplier: number;
```

- [ ] **Step 3: Add fetchEvents method**

In the `ApiService` class, add:

```typescript
fetchEvents(limit = 50) {
  return this.http.get<EventData[]>(`${API}/events`, { params: { limit: limit.toString() } });
}
```

- [ ] **Step 4: Commit**

```bash
cd /c/Users/Nathan/cryptobot
git add dashboard/ui/src/app/services/api.service.ts
git commit -m "feat: add EventData interface and fetchEvents to API service"
```

---

## Task 4: Frontend — StatusBannerComponent

New component showing bot status dot, plain-English text, quick stats, and Tools dropdown.

**Files:**
- Create: `dashboard/ui/src/app/components/status-banner/status-banner.component.ts`

- [ ] **Step 1: Create the component file**

Create `dashboard/ui/src/app/components/status-banner/status-banner.component.ts`:

```typescript
import { Component, inject, signal, computed, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, StatusData, HealthData } from '../../services/api.service';

@Component({
  selector: 'app-status-banner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="banner" style="background:linear-gradient(135deg,#1a1d2e,#242840);padding:14px 24px;border-bottom:1px solid #2d3148;display:flex;align-items:center;gap:16px;flex-wrap:wrap;">

      <!-- Status dot -->
      <div
        class="status-dot"
        [style.background]="dotColor()"
        [style.box-shadow]="'0 0 8px ' + dotColor()"
      ></div>

      <!-- Status text -->
      <div style="flex:1;min-width:280px;">
        <div style="font-size:15px;font-weight:600;color:#e2e8f0;">{{ statusText() }}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:2px;">{{ lastActionText() }}</div>
      </div>

      <!-- Quick stats -->
      <div style="display:flex;gap:16px;flex-wrap:wrap;">
        <div class="quick-stat">
          <div class="qs-label">Equity</div>
          <div class="qs-value" [class.positive]="pnl() >= 0" [class.negative]="pnl() < 0">{{ formatCurrency(equity()) }}</div>
        </div>
        <div class="quick-stat">
          <div class="qs-label">Net P&L</div>
          <div class="qs-value" [class.positive]="pnl() >= 0" [class.negative]="pnl() < 0">
            {{ pnl() >= 0 ? '+' : '' }}{{ formatCurrency(pnl()) }}
          </div>
        </div>
        <div class="quick-stat">
          <div class="qs-label">Trades</div>
          <div class="qs-value neutral">{{ totalTrades() }}</div>
        </div>
        <div class="quick-stat">
          <div class="qs-label">Uptime</div>
          <div class="qs-value neutral">{{ uptimeText() }}</div>
        </div>
      </div>

      <!-- Tools button -->
      <div style="position:relative;">
        <button
          class="tools-btn"
          (click)="toolsOpen.set(!toolsOpen())"
        >Tools ▾</button>
        <div *ngIf="toolsOpen()" class="tools-dropdown">
          <button (click)="toolSelected.emit('simulator'); toolsOpen.set(false)">Simulator</button>
          <button (click)="toolSelected.emit('regime'); toolsOpen.set(false)">Regime Visualizer</button>
          <button (click)="toolSelected.emit('self-check'); toolsOpen.set(false)">Self-Check</button>
          <div class="tools-divider"></div>
          <button (click)="updateClicked.emit(); toolsOpen.set(false)">Update Bot</button>
        </div>
      </div>

    </div>
  `,
  styles: [`
    .status-dot {
      width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
    }
    .quick-stat { text-align: center; }
    .qs-label {
      font-size: 10px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .qs-value {
      font-size: 16px; font-weight: 700; color: #e2e8f0;
    }
    .qs-value.positive { color: #4ade80; }
    .qs-value.negative { color: #f87171; }
    .qs-value.neutral { color: #e2e8f0; }
    .tools-btn {
      font-size: 11px; color: #6b7280; padding: 6px 12px; border: 1px solid #2d3148;
      border-radius: 6px; background: transparent; cursor: pointer; white-space: nowrap;
    }
    .tools-btn:hover { background: #2d3148; color: #e2e8f0; }
    .tools-dropdown {
      position: absolute; top: 100%; right: 0; margin-top: 4px; background: #1a1d2e;
      border: 1px solid #2d3148; border-radius: 8px; padding: 4px 0; z-index: 50;
      min-width: 180px; box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    }
    .tools-dropdown button {
      display: block; width: 100%; text-align: left; padding: 8px 16px;
      font-size: 12px; color: #9ca3af; background: transparent; border: none; cursor: pointer;
    }
    .tools-dropdown button:hover { background: #242840; color: #e2e8f0; }
    .tools-divider { height: 1px; background: #2d3148; margin: 4px 0; }
  `],
})
export class StatusBannerComponent {
  private api = inject(ApiService);

  toolsOpen = signal(false);
  toolSelected = output<string>();
  updateClicked = output<void>();

  private health = signal<HealthData | null>(null);

  constructor() {
    this.api.fetchHealth().subscribe({
      next: (h) => this.health.set(h),
    });
  }

  status = computed(() => this.api.status());

  dotColor = computed(() => {
    const h = this.health();
    if (!h) return '#6b7280';
    return h.bot_running ? '#4ade80' : '#f87171';
  });

  statusText = computed(() => {
    const s = this.status();
    const h = this.health();
    if (!s) return 'Loading...';
    const running = h?.bot_running !== false;
    return running
      ? `Bot is running · watching ${s.pairs.length} pair${s.pairs.length !== 1 ? 's' : ''}`
      : 'Bot stopped';
  });

  lastActionText = computed(() => {
    const s = this.status();
    if (!s || !s.last_trade_time) return 'No trades yet';
    const ago = this.timeAgo(s.last_trade_time);
    return `Last trade: ${ago}`;
  });

  equity = computed(() => this.status()?.equity ?? 0);
  pnl = computed(() => this.status()?.pnl ?? 0);
  totalTrades = computed(() => this.status()?.total_trades ?? 0);

  uptimeText = computed(() => {
    const h = this.health();
    if (!h) return '—';
    const secs = h.uptime_seconds;
    const hrs = Math.floor(secs / 3600);
    const mins = Math.floor((secs % 3600) / 60);
    return `${hrs}h ${mins}m`;
  });

  formatCurrency(value: number): string {
    return '$' + Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  private timeAgo(ts: string): string {
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ${mins % 60}m ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd /c/Users/Nathan/cryptobot/dashboard/ui
npx ng build 2>&1 | tail -20
```

Expected: Build succeeds (component not referenced yet, but no syntax errors).

- [ ] **Step 3: Commit**

```bash
git add dashboard/ui/src/app/components/status-banner/
git commit -m "feat: add StatusBannerComponent with status dot, plain-English text, quick stats, tools dropdown"
```

---

## Task 5: Frontend — ActivityLogComponent

New component that polls `/api/events` and renders a scrolling plain-English feed.

**Files:**
- Create: `dashboard/ui/src/app/components/activity-log/activity-log.component.ts`

- [ ] **Step 1: Create the component**

```typescript
import { Component, inject, signal, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, EventData } from '../../services/api.service';
import { Subscription, interval, switchMap, startWith } from 'rxjs';

const EVENT_STYLES: Record<string, { color: string; label: string }> = {
  trade_buy:    { color: '#4ade80', label: 'Bought' },
  trade_sell:   { color: '#f87171', label: 'Sold' },
  atr_adjust:   { color: '#60a5fa', label: 'Spacing changed' },
  vol_check:    { color: '#c084fc', label: 'Vol check' },
  range_recalc: { color: '#fbbf24', label: 'Range recalc' },
  scan_complete: { color: '#94a3b8', label: 'Scan complete' },
  pair_swap:    { color: '#fb923c', label: 'Pair swap' },
  error:        { color: '#f87171', label: 'Error' },
};

const DEFAULT_STYLE = { color: '#94a3b8', label: 'Event' };

@Component({
  selector: 'app-activity-log',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="log-container">
      <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;margin-bottom:10px;">
        Live Activity
      </div>
      <div class="log-entries">
        <div *ngFor="let evt of events()" class="log-entry">
          <span class="log-time">{{ timeAgo(evt.timestamp) }}</span>
          <div class="log-body">
            <span class="log-label" [style.color]="styleFor(evt.event_type).color">
              {{ styleFor(evt.event_type).label }}
            </span>
            <span class="log-title">{{ evt.title }}</span>
            <div *ngIf="evt.detail" class="log-detail">{{ evt.detail }}</div>
          </div>
        </div>
        <div *ngIf="events().length === 0" style="color:#4b5563;font-size:12px;font-style:italic;">
          No recent activity
        </div>
      </div>
    </div>
  `,
  styles: [`
    .log-container {
      padding: 16px 20px; min-width: 0; max-height: 280px; overflow-y: auto;
    }
    .log-entries { display: flex; flex-direction: column; gap: 10px; }
    .log-entry { display: flex; gap: 10px; align-items: flex-start; font-size: 12px; }
    .log-time { color: #4b5563; white-space: nowrap; font-size: 11px; min-width: 40px; }
    .log-body { flex: 1; min-width: 0; }
    .log-label { font-weight: 600; margin-right: 4px; }
    .log-title { color: #e2e8f0; }
    .log-detail { color: #6b7280; font-size: 11px; margin-top: 2px; }
  `],
})
export class ActivityLogComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  events = signal<EventData[]>([]);
  private sub?: Subscription;

  ngOnInit(): void {
    this.sub = interval(60_000).pipe(
      startWith(0),
      switchMap(() => this.api.fetchEvents(50)),
    ).subscribe({
      next: (data) => this.events.set(data),
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  styleFor(type: string) {
    return EVENT_STYLES[type] ?? DEFAULT_STYLE;
  }

  timeAgo(ts: string): string {
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'now';
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
  }
}
```

- [ ] **Step 2: Verify build**

```bash
cd /c/Users/Nathan/cryptobot/dashboard/ui && npx ng build 2>&1 | tail -10
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/ui/src/app/components/activity-log/
git commit -m "feat: add ActivityLogComponent with plain-English event feed"
```

---

## Task 6: Frontend — PairCardComponent

Collapsed pair summary card showing pair name, regime badge, stats grid, and grid fill bar.

**Files:**
- Create: `dashboard/ui/src/app/components/pair-card/pair-card.component.ts`

- [ ] **Step 1: Create the component**

```typescript
import { Component, input, computed, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PairInfo, PositionData, VolPredictionData } from '../../services/api.service';

const REGIME_COLORS: Record<string, { bg: string; text: string }> = {
  RANGING:       { bg: '#1e293b', text: '#94a3b8' },
  TRENDING_UP:   { bg: '#1e3a5f', text: '#60a5fa' },
  TRENDING_DOWN: { bg: '#450a0a', text: '#f87171' },
  VOLATILE:      { bg: '#451a03', text: '#fbbf24' },
  SQUEEZE:       { bg: '#3b0764', text: '#c084fc' },
};

const DEFAULT_REGIME = { bg: '#1e2130', text: '#94a3b8' };

@Component({
  selector: 'app-pair-card',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      class="card"
      [class.expanded]="isExpanded()"
      [class.dimmed]="isDimmed()"
      (click)="cardClicked.emit(pair().pair)"
    >
      <div *ngIf="isExpanded()" class="collapse-hint">▲ collapse</div>
      <div class="card-header">
        <div class="pair-name" [class.highlight]="isExpanded()">{{ pair().pair }}</div>
        <span
          class="regime-badge"
          [style.background]="regimeColor().bg"
          [style.color]="regimeColor().text"
        >{{ regimeLabel() }}</span>
      </div>
      <div class="stats-grid">
        <div><span class="stat-label">Price:</span> {{ formatPrice(pair().price) }}</div>
        <div><span class="stat-label">P&L:</span>
          <span [style.color]="pnl() >= 0 ? '#4ade80' : '#f87171'">
            {{ pnl() >= 0 ? '+' : '' }}{{ formatCurrency(pnl()) }}
          </span>
        </div>
        <div><span class="stat-label">Grid:</span> {{ gridHeld() }}/{{ gridTotal() }} held</div>
        <div><span class="stat-label">ATR:</span> {{ atrMult() }}x</div>
        <div><span class="stat-label">Trades:</span> {{ pair().trade_count }}</div>
        <div><span class="stat-label">Vol R²:</span>
          <span [style.color]="volR2Color()">{{ volR2Text() }}</span>
        </div>
      </div>
      <div class="fill-bar-bg">
        <div class="fill-bar" [style.width.%]="fillPct()" [style.background]="fillColor()"></div>
      </div>
      <div class="fill-label">Grid fill: {{ fillPct() }}%</div>
    </div>
  `,
  styles: [`
    .card {
      flex: 1; min-width: 280px; background: #1a1d2e; border: 1px solid #2d3148;
      border-radius: 10px; padding: 14px; cursor: pointer; position: relative;
      transition: all 0.2s;
    }
    .card:hover { border-color: #3d4168; }
    .card.expanded { border: 2px solid #fbbf24; }
    .card.dimmed { opacity: 0.7; }
    .collapse-hint {
      position: absolute; top: 8px; right: 10px; font-size: 10px; color: #fbbf24;
    }
    .card-header {
      display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;
    }
    .pair-name { font-weight: 700; font-size: 14px; color: #e2e8f0; }
    .pair-name.highlight { color: #fbbf24; }
    .regime-badge {
      font-size: 10px; padding: 2px 8px; border-radius: 4px;
      font-weight: 600; text-transform: uppercase;
    }
    .stats-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 11px; color: #e2e8f0;
    }
    .stat-label { color: #6b7280; }
    .fill-bar-bg {
      margin-top: 8px; height: 3px; background: #2d3148; border-radius: 2px; overflow: hidden;
    }
    .fill-bar { height: 100%; border-radius: 2px; transition: width 0.3s; }
    .fill-label { font-size: 10px; color: #4b5563; margin-top: 4px; }
  `],
})
export class PairCardComponent {
  pair = input.required<PairInfo>();
  isExpanded = input(false);
  isDimmed = input(false);
  positions = input<PositionData[]>([]);
  volPrediction = input<VolPredictionData | null>(null);
  gridHeld = input(0);
  gridTotal = input(10);

  cardClicked = output<string>();

  regimeColor = computed(() => {
    const key = (this.pair().regime ?? '').toUpperCase().replace(/ /g, '_');
    return REGIME_COLORS[key] ?? DEFAULT_REGIME;
  });

  regimeLabel = computed(() => {
    return (this.pair().regime ?? 'unknown').replace(/_/g, ' ');
  });

  pnl = computed(() => {
    return this.positions()
      .filter(p => p.pair === this.pair().pair)
      .reduce((sum, p) => sum + p.unrealized_pnl, 0);
  });

  atrMult = computed(() => {
    const vp = this.volPrediction();
    return vp ? vp.spacing_multiplier.toFixed(1) : '1.0';
  });

  volR2Color = computed(() => {
    const vp = this.volPrediction();
    if (!vp) return '#6b7280';
    // Negative R² = bad model
    return '#f87171';
  });

  volR2Text = computed(() => {
    const vp = this.volPrediction();
    if (!vp) return '—';
    return `${vp.confidence.toFixed(2)}`;
  });

  fillPct = computed(() => {
    const total = this.gridTotal();
    if (total <= 0) return 0;
    return Math.round((this.gridHeld() / total) * 100);
  });

  fillColor = computed(() => {
    const pct = this.fillPct();
    if (pct > 50) return '#fbbf24';
    return '#4ade80';
  });

  formatPrice(price: number): string {
    if (!price) return '—';
    if (price >= 1) return '$' + price.toFixed(2);
    return '$' + price.toFixed(6);
  }

  formatCurrency(value: number): string {
    return '$' + Math.abs(value).toFixed(2);
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/ui/src/app/components/pair-card/
git commit -m "feat: add PairCardComponent with regime badge, stats grid, grid fill bar"
```

---

## Task 7: Frontend — ExpandedPairChartComponent

Wraps existing `PriceChartComponent` and `IndicatorPanelComponent` for inline expansion below pair cards.

**Files:**
- Create: `dashboard/ui/src/app/components/expanded-pair-chart/expanded-pair-chart.component.ts`

- [ ] **Step 1: Create the component**

```typescript
import { Component, input, inject, signal, OnInit, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PriceChartComponent } from '../price-chart/price-chart.component';
import { IndicatorPanelComponent } from '../indicator-panel/indicator-panel.component';
import { ApiService, CandleData, TradeData, IndicatorData, GridLevelData, PositionData } from '../../services/api.service';

@Component({
  selector: 'app-expanded-pair-chart',
  standalone: true,
  imports: [CommonModule, PriceChartComponent, IndicatorPanelComponent],
  template: `
    <div class="expanded-chart" [@slideDown]>
      <div style="padding:12px 16px 8px;display:flex;justify-content:space-between;align-items:center;">
        <div style="font-size:13px;font-weight:700;color:#e2e8f0;">{{ pair() }} · 4h Candles · 7 Days</div>
        <div style="font-size:10px;color:#6b7280;">
          Grid range: {{ formatPrice(rangeLower()) }} – {{ formatPrice(rangeUpper()) }}
        </div>
      </div>
      <app-price-chart
        [candles]="candles()"
        [trades]="trades()"
        [indicators]="indicators()"
        [gridLevels]="gridLevelPrices()"
        [rangeLower]="rangeLower()"
        [rangeUpper]="rangeUpper()"
        [positions]="positions()"
      />
      <app-indicator-panel [indicators]="indicators()" />
    </div>
  `,
  styles: [`
    .expanded-chart {
      background: #0d0f16; border: 1px solid #2d3148; border-radius: 10px;
      overflow: hidden; animation: slideDown 0.35s ease-out;
    }
    @keyframes slideDown {
      from { max-height: 0; opacity: 0; }
      to { max-height: 1200px; opacity: 1; }
    }
  `],
})
export class ExpandedPairChartComponent implements OnInit, OnChanges {
  pair = input.required<string>();

  private api = inject(ApiService);

  candles = signal<CandleData[]>([]);
  trades = signal<TradeData[]>([]);
  indicators = signal<IndicatorData[]>([]);
  gridLevelPrices = signal<{ price: number; type: string }[]>([]);
  rangeLower = signal(0);
  rangeUpper = signal(0);
  positions = signal<PositionData[]>([]);

  ngOnInit(): void {
    this.loadData();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['pair'] && !changes['pair'].firstChange) {
      this.loadData();
    }
  }

  private loadData(): void {
    const sym = this.pair();
    if (!sym) return;

    this.api.fetchCandles(sym, 168).subscribe({
      next: (data) => this.candles.set(data),
    });
    this.api.fetchTrades(sym, 100).subscribe({
      next: (data) => this.trades.set(data),
    });
    this.api.fetchIndicators(sym, 168).subscribe({
      next: (data) => this.indicators.set(data),
    });
    this.api.fetchGridLevels(sym).subscribe({
      next: (data: GridLevelData) => {
        this.gridLevelPrices.set(data.levels);
        this.rangeLower.set(data.lower);
        this.rangeUpper.set(data.upper);
      },
    });
    this.api.fetchPositions().subscribe({
      next: (data) => this.positions.set(data.filter(p => p.pair === sym)),
    });
  }

  formatPrice(price: number): string {
    if (!price) return '—';
    if (price >= 1) return '$' + price.toFixed(2);
    return '$' + price.toFixed(6);
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/ui/src/app/components/expanded-pair-chart/
git commit -m "feat: add ExpandedPairChartComponent wrapping price-chart + indicator-panel"
```

---

## Task 8: Frontend — HealthBarComponent

Compact row showing daily/weekly P&L vs limits, streak, vol accuracy, next scan.

**Files:**
- Create: `dashboard/ui/src/app/components/health-bar/health-bar.component.ts`

- [ ] **Step 1: Create the component**

```typescript
import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, SelfCheckData, HealthData } from '../../services/api.service';

@Component({
  selector: 'app-health-bar',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="health-bar">
      <div class="metric">
        <span class="metric-label">Daily P&L:</span>
        <span [style.color]="dailyColor()">{{ formatSigned(dailyPnl()) }}</span>
        <span class="metric-limit">/ -$30 limit</span>
      </div>
      <div class="metric">
        <span class="metric-label">Weekly:</span>
        <span [style.color]="weeklyColor()">{{ formatSigned(weeklyPnl()) }}</span>
        <span class="metric-limit">/ -$75 limit</span>
      </div>
      <div class="metric">
        <span class="metric-label">Streak:</span>
        <span [style.color]="streakColor()">{{ streakText() }}</span>
      </div>
      <div class="metric">
        <span class="metric-label">Vol accuracy:</span>
        <span [style.color]="volColor()">{{ volText() }}</span>
      </div>
      <div class="metric">
        <span class="metric-label">Next refresh:</span>
        <span style="color:#94a3b8;">{{ refreshCountdown() }}s</span>
      </div>
    </div>
  `,
  styles: [`
    .health-bar {
      padding: 12px 20px; border-bottom: 1px solid #2d3148;
      display: flex; gap: 24px; font-size: 11px; flex-wrap: wrap;
    }
    .metric { white-space: nowrap; }
    .metric-label {
      color: #6b7280; text-transform: uppercase; font-weight: 600; letter-spacing: 0.05em;
      margin-right: 4px;
    }
    .metric-limit { color: #4b5563; }
  `],
})
export class HealthBarComponent implements OnInit {
  private api = inject(ApiService);

  selfCheck = signal<SelfCheckData | null>(null);
  refreshCountdown = this.api.refreshCountdown;

  ngOnInit(): void {
    this.api.fetchSelfCheck().subscribe({
      next: (d) => this.selfCheck.set(d),
    });
  }

  dailyPnl = () => this.selfCheck()?.daily_pnl ?? 0;
  weeklyPnl = () => (this.api.status()?.pnl ?? 0);

  streakText = () => {
    const sc = this.selfCheck();
    if (!sc?.streak) return '—';
    return `${sc.streak.days} ${sc.streak.type} day${sc.streak.days !== 1 ? 's' : ''}`;
  };

  volText = () => {
    const sc = this.selfCheck();
    if (!sc?.vol_accuracy_24h) return '—';
    return `${sc.vol_accuracy_24h.avg_error_pct.toFixed(1)}% err`;
  };

  dailyColor = () => this.pnlColor(this.dailyPnl(), 30);
  weeklyColor = () => this.pnlColor(this.weeklyPnl(), 75);
  streakColor = () => {
    const sc = this.selfCheck();
    return sc?.streak?.type === 'winning' ? '#4ade80' : '#f87171';
  };
  volColor = () => {
    const sc = this.selfCheck();
    if (!sc?.vol_accuracy_24h) return '#6b7280';
    return sc.vol_accuracy_24h.avg_error_pct < 15 ? '#4ade80' : '#fbbf24';
  };

  formatSigned(val: number): string {
    return (val >= 0 ? '+' : '') + '$' + Math.abs(val).toFixed(2);
  }

  private pnlColor(val: number, limit: number): string {
    if (val >= 0) return '#4ade80';
    if (Math.abs(val) > limit * 0.6) return '#fbbf24';
    if (Math.abs(val) > limit) return '#f87171';
    return '#4ade80';
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/ui/src/app/components/health-bar/
git commit -m "feat: add HealthBarComponent with P&L limits, streak, vol accuracy"
```

---

## Task 9: Frontend — CommandCenterComponent (Page Shell)

The main page that composes all sections: status banner, equity chart + activity log, pair cards with expand/collapse, "Why these pairs?", health bar, and positions table.

**Files:**
- Create: `dashboard/ui/src/app/components/command-center/command-center.component.ts`

- [ ] **Step 1: Create the component**

```typescript
import { Component, inject, signal, OnInit, OnDestroy, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ApiService, StatusData, PositionData, TradeData,
  VolPredictionData, PairScanData, GridLevelData,
} from '../../services/api.service';
import { StatusBannerComponent } from '../status-banner/status-banner.component';
import { ActivityLogComponent } from '../activity-log/activity-log.component';
import { PairCardComponent } from '../pair-card/pair-card.component';
import { ExpandedPairChartComponent } from '../expanded-pair-chart/expanded-pair-chart.component';
import { HealthBarComponent } from '../health-bar/health-bar.component';
import { TradeLogComponent } from '../trade-log/trade-log.component';
import { PositionCardsComponent } from '../position-cards/position-cards.component';
import { EquityCurveComponent } from '../equity-curve/equity-curve.component';
import { DcaSimulatorComponent } from '../dca-simulator/dca-simulator.component';
import { RegimeVisualizerComponent } from '../regime-visualizer/regime-visualizer.component';
import { SelfCheckComponent } from '../self-check/self-check.component';
import { forkJoin } from 'rxjs';

@Component({
  selector: 'app-command-center',
  standalone: true,
  imports: [
    CommonModule, StatusBannerComponent, ActivityLogComponent,
    PairCardComponent, ExpandedPairChartComponent, HealthBarComponent,
    TradeLogComponent, PositionCardsComponent,
    DcaSimulatorComponent, RegimeVisualizerComponent, SelfCheckComponent,
  ],
  template: `
    <div class="cc-root">

      <!-- STATUS BANNER -->
      <app-status-banner
        (toolSelected)="openTool($event)"
        (updateClicked)="triggerUpdate()"
      />

      <!-- EQUITY CHART + ACTIVITY LOG -->
      <div class="equity-activity-row">
        <div class="equity-col">
          <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;margin-bottom:10px;">
            Portfolio Equity (72h)
          </div>
          <div class="equity-chart-slot">
            <canvas #equityCanvas></canvas>
          </div>
          <div class="equity-substats">
            <div><span class="sub-label">Realized:</span> <span [style.color]="realizedPnl() >= 0 ? '#4ade80' : '#f87171'">{{ formatSigned(realizedPnl()) }}</span></div>
            <div><span class="sub-label">Unrealized:</span> <span [style.color]="unrealizedPnl() >= 0 ? '#4ade80' : '#f87171'">{{ formatSigned(unrealizedPnl()) }}</span></div>
            <div><span class="sub-label">Fees:</span> <span style="color:#f87171;">{{ formatCurrency(totalFees()) }}</span></div>
            <div><span class="sub-label">Max DD:</span> <span style="color:#fbbf24;">{{ maxDrawdown().toFixed(1) }}%</span></div>
          </div>
        </div>
        <div class="activity-col">
          <app-activity-log />
        </div>
      </div>

      <!-- PAIR CARDS -->
      <div class="pair-section">
        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;margin-bottom:12px;">
          Active Pairs <span style="color:#4b5563;font-weight:400;">(click to expand chart)</span>
        </div>
        <div class="pair-cards-row">
          <app-pair-card
            *ngFor="let p of pairs()"
            [pair]="p"
            [isExpanded]="expandedPair() === p.pair"
            [isDimmed]="expandedPair() !== null && expandedPair() !== p.pair"
            [positions]="positions()"
            [volPrediction]="volForPair(p.pair)"
            [gridHeld]="gridHeldForPair(p.pair)"
            [gridTotal]="gridTotalForPair(p.pair)"
            (cardClicked)="toggleExpand($event)"
          />
        </div>

        <!-- Expanded chart -->
        <app-expanded-pair-chart
          *ngIf="expandedPair()"
          [pair]="expandedPair()!"
        />

        <!-- Why these pairs? -->
        <div class="why-pairs" *ngIf="latestScan()">
          <button class="why-toggle" (click)="whyOpen.set(!whyOpen())">
            {{ whyOpen() ? '▾' : '▸' }} Why these pairs?
          </button>
          <div *ngIf="whyOpen()" class="why-content">
            <div *ngFor="let sp of latestScan()!.selected_pairs" class="why-entry">
              <strong>{{ sp.pair.replace('-USD', '') }}</strong>:
              Score {{ sp.composite_score.toFixed(0) }}
              — volatility {{ (sp.volatility * 100).toFixed(0) }}%,
              range-bound {{ (sp.range_bound * 100).toFixed(0) }}%,
              liquidity {{ (sp.liquidity * 100).toFixed(0) }}%,
              regime {{ sp.regime }}
            </div>
          </div>
        </div>
      </div>

      <!-- HEALTH BAR -->
      <app-health-bar />

      <!-- POSITIONS + TRADES TABLE -->
      <div class="positions-section">
        <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;margin-bottom:10px;">
          Open Positions &amp; Recent Trades
        </div>
        <app-position-cards [positions]="positions()" />
        <app-trade-log [trades]="allTrades()" />
      </div>

      <!-- TOOLS SECTION (hidden by default) -->
      <div *ngIf="activeTool()" class="tool-section">
        <div class="tool-header">
          <span>{{ activeToolLabel() }}</span>
          <button class="tool-close" (click)="activeTool.set(null)">✕ Close</button>
        </div>
        <app-dca-simulator *ngIf="activeTool() === 'simulator'" />
        <app-regime-visualizer *ngIf="activeTool() === 'regime'" />
        <app-self-check *ngIf="activeTool() === 'self-check'" />
      </div>

    </div>
  `,
  styles: [`
    .cc-root {
      background: #0f1117; color: #e2e8f0; min-height: 100vh;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }

    /* Equity + Activity row */
    .equity-activity-row {
      display: flex; gap: 0; border-bottom: 1px solid #2d3148; flex-wrap: wrap;
    }
    .equity-col {
      flex: 3; padding: 16px 20px; border-right: 1px solid #2d3148; min-width: 300px;
    }
    .activity-col {
      flex: 2; min-width: 280px;
    }
    .equity-chart-slot {
      position: relative; height: 200px; background: linear-gradient(180deg, rgba(74,222,128,0.03), transparent);
      border-radius: 8px; overflow: hidden;
    }
    .equity-chart-slot canvas { display: block; width: 100% !important; height: 100% !important; }
    .equity-substats {
      display: flex; gap: 20px; margin-top: 8px; font-size: 11px; flex-wrap: wrap;
    }
    .sub-label { color: #6b7280; }

    /* Pair section */
    .pair-section { padding: 16px 20px; border-bottom: 1px solid #2d3148; }
    .pair-cards-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }

    /* Why these pairs */
    .why-pairs { margin-top: 12px; }
    .why-toggle {
      background: transparent; border: none; color: #6b7280; font-size: 12px;
      cursor: pointer; padding: 4px 0;
    }
    .why-toggle:hover { color: #e2e8f0; }
    .why-content {
      margin-top: 8px; padding: 12px 16px; background: #1a1d2e;
      border: 1px solid #2d3148; border-radius: 8px; font-size: 12px; color: #9ca3af;
    }
    .why-entry { margin-bottom: 6px; line-height: 1.6; }
    .why-entry strong { color: #e2e8f0; }

    /* Positions */
    .positions-section { padding: 16px 20px; }

    /* Tools */
    .tool-section { padding: 16px 20px; border-top: 1px solid #2d3148; }
    .tool-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 12px; font-size: 13px; font-weight: 600; color: #e2e8f0;
    }
    .tool-close {
      background: transparent; border: 1px solid #2d3148; color: #6b7280;
      padding: 4px 12px; border-radius: 6px; cursor: pointer; font-size: 11px;
    }
    .tool-close:hover { background: #2d3148; color: #e2e8f0; }

    /* Phone check-in */
    @media (max-width: 768px) {
      .equity-activity-row { flex-direction: column; }
      .equity-col { border-right: none; border-bottom: 1px solid #2d3148; }
      .pair-cards-row { flex-direction: column; }
    }
  `],
})
export class CommandCenterComponent implements OnInit {
  private api = inject(ApiService);

  expandedPair = signal<string | null>(null);
  whyOpen = signal(false);
  activeTool = signal<string | null>(null);

  positions = signal<PositionData[]>([]);
  allTrades = signal<TradeData[]>([]);
  volPredictions = signal<VolPredictionData[]>([]);
  latestScan = signal<PairScanData | null>(null);
  gridLevels = signal<Map<string, GridLevelData>>(new Map());

  // Equity sub-stats
  realizedPnl = signal(0);
  unrealizedPnl = signal(0);
  totalFees = signal(0);
  maxDrawdown = signal(0);

  pairs = computed(() => this.api.status()?.pairs ?? []);

  ngOnInit(): void {
    forkJoin({
      positions: this.api.fetchPositions(),
      trades: this.api.fetchTrades(undefined, 100),
      volLatest: this.api.fetchVolLatest(),
      scan: this.api.fetchLatestPairScan(),
    }).subscribe({
      next: ({ positions, trades, volLatest, scan }) => {
        this.positions.set(positions);
        this.allTrades.set(trades);
        this.volPredictions.set(volLatest);
        this.latestScan.set(scan);
        this.computeSubStats(trades, positions);
      },
    });

    // Fetch grid levels for each pair
    this.api.fetchPairs().subscribe({
      next: (pairs) => {
        for (const pair of pairs) {
          this.api.fetchGridLevels(pair).subscribe({
            next: (gl) => {
              const map = new Map(this.gridLevels());
              map.set(pair, gl);
              this.gridLevels.set(map);
            },
          });
        }
      },
    });
  }

  private computeSubStats(trades: TradeData[], positions: PositionData[]): void {
    let realized = 0, fees = 0;
    for (const t of trades) {
      if (t.net_profit != null) realized += t.net_profit;
      if (t.fee != null) fees += t.fee;
    }
    this.realizedPnl.set(realized);
    this.totalFees.set(fees);
    this.unrealizedPnl.set(positions.reduce((s, p) => s + p.unrealized_pnl, 0));

    // Max drawdown from status
    const s = this.api.status();
    if (s) {
      const dd = s.equity < s.starting_balance
        ? ((s.starting_balance - s.equity) / s.starting_balance) * 100
        : 0;
      this.maxDrawdown.set(dd);
    }
  }

  toggleExpand(pair: string): void {
    this.expandedPair.set(this.expandedPair() === pair ? null : pair);
  }

  volForPair(pair: string): VolPredictionData | null {
    return this.volPredictions().find(v => v.pair === pair) ?? null;
  }

  gridHeldForPair(pair: string): number {
    const gl = this.gridLevels().get(pair);
    if (!gl) return 0;
    return gl.levels.filter(l => l.type === 'held').length;
  }

  gridTotalForPair(pair: string): number {
    const gl = this.gridLevels().get(pair);
    return gl?.num_grids ?? 10;
  }

  openTool(tool: string): void {
    this.activeTool.set(this.activeTool() === tool ? null : tool);
  }

  activeToolLabel(): string {
    const labels: Record<string, string> = {
      simulator: 'Simulator', regime: 'Regime Visualizer', 'self-check': 'Self-Check',
    };
    return labels[this.activeTool() ?? ''] ?? '';
  }

  triggerUpdate(): void {
    this.api.triggerUpdate().subscribe({
      next: (res) => alert(res.output || 'Update complete'),
      error: () => alert('Update failed'),
    });
  }

  formatSigned(val: number): string {
    return (val >= 0 ? '+$' : '-$') + Math.abs(val).toFixed(2);
  }

  formatCurrency(val: number): string {
    return '$' + Math.abs(val).toFixed(2);
  }
}
```

Note: The equity chart in this component uses a canvas placeholder. The full Chart.js equity chart logic should be adapted from `EquityCurveComponent` — extract the chart-building logic into this component's `AfterViewInit`, using a narrower height (200px instead of 420px). The existing `EquityCurveComponent` has all the chart-building code in `buildChart()` — copy the relevant pieces (line chart with drawdown, trade markers, per-pair lines) and adjust the height.

- [ ] **Step 2: Verify build compiles**

```bash
cd /c/Users/Nathan/cryptobot/dashboard/ui && npx ng build 2>&1 | tail -20
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/ui/src/app/components/command-center/
git commit -m "feat: add CommandCenterComponent — main page shell composing all sections"
```

---

## Task 10: Frontend — Routing & App Shell Changes

Replace tab navigation with the Command Center. Update routing. Add phone-friendly CSS.

**Files:**
- Modify: `dashboard/ui/src/app/app.ts`
- Modify: `dashboard/ui/src/app/app.routes.ts`

- [ ] **Step 1: Update app.routes.ts**

Replace the entire contents of `dashboard/ui/src/app/app.routes.ts`:

```typescript
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./components/command-center/command-center.component').then(
        (m) => m.CommandCenterComponent
      ),
  },
  // Backwards compat redirects
  { path: 'pair/:symbol', redirectTo: '', pathMatch: 'full' },
  { path: 'ml-brain', redirectTo: '', pathMatch: 'full' },
  { path: 'pair-scanner', redirectTo: '', pathMatch: 'full' },
  { path: 'simulator', redirectTo: '', pathMatch: 'full' },
  { path: 'regime', redirectTo: '', pathMatch: 'full' },
  { path: 'self-check', redirectTo: '', pathMatch: 'full' },
];
```

- [ ] **Step 2: Simplify app.ts**

Replace the template and class in `dashboard/ui/src/app/app.ts`. Remove tab navigation, stats-bar import, and pair fetching. The Command Center handles everything now:

```typescript
import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ApiService } from './services/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <div class="min-h-screen" style="background: #0f1117; color: #e1e4ed;">
      <router-outlet />
    </div>
  `,
})
export class App implements OnInit, OnDestroy {
  private api = inject(ApiService);

  ngOnInit() {
    this.api.startPolling(60);
  }

  ngOnDestroy() {
    this.api.stopPolling();
  }
}
```

- [ ] **Step 3: Build and test**

```bash
cd /c/Users/Nathan/cryptobot/dashboard/ui && npx ng build 2>&1 | tail -20
```

Expected: Build succeeds. If there are import errors, fix them (missing imports, circular dependencies).

- [ ] **Step 4: Serve and manually verify**

```bash
cd /c/Users/Nathan/cryptobot/dashboard/ui && npx ng serve --open
```

Open http://localhost:4200 and verify:
- Status banner shows at top with green dot, equity, P&L, trade count, uptime
- Tools dropdown works (Simulator, Regime, Self-Check, Update Bot)
- Equity chart renders on the left
- Activity log shows on the right (or below on narrow screens)
- Pair cards show for each active pair
- Clicking a pair card expands the chart inline below
- Clicking again collapses it
- "Why these pairs?" collapsible works
- Health bar shows at bottom
- Positions + trade table shows at bottom
- On narrow browser window: layout stacks vertically

- [ ] **Step 5: Commit**

```bash
git add dashboard/ui/src/app/app.ts dashboard/ui/src/app/app.routes.ts
git commit -m "feat: replace tab navigation with Command Center single-page layout"
```

---

## Self-Review Checklist

| Spec Requirement | Task |
|-----------------|------|
| Status banner with dot, text, stats, tools | Task 4 (StatusBanner) |
| Equity chart (left) | Task 9 (CommandCenter) |
| Activity log (right) with plain-English ATR changes | Task 1 (backend events) + Task 5 (ActivityLog) |
| Pair cards with regime, stats, grid fill | Task 6 (PairCard) |
| Click-to-expand candlestick chart with EMAs, BBands, grid levels | Task 7 (ExpandedPairChart) |
| Trade markers with regime annotation (ADX/RSI) | Task 2 (backend snapshots) + Task 7 |
| Indicator strip (ADX/RSI/Volume/OBV) | Task 7 (reuses IndicatorPanel) |
| "Why these pairs?" collapsible | Task 9 (CommandCenter) |
| Health bar (daily/weekly P&L, streak, vol accuracy) | Task 8 (HealthBar) |
| Positions + trade history table | Task 9 (reuses TradeLog + PositionCards) |
| Tools dropdown (Simulator, Regime, Self-Check, Update) | Task 4 (StatusBanner) + Task 9 |
| Phone check-in (flex-wrap stacking) | Task 9 (CSS media query) + Task 10 |
| Trade regime snapshots in DB | Task 2 |
| `/api/events` endpoint | Task 1 |
| Routing change (single route) | Task 10 |
| Backwards-compat redirects | Task 10 |
