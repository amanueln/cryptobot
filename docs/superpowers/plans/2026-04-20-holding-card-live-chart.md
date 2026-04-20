# Holding Card Live Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-04-20-holding-card-live-chart-design.md](../specs/2026-04-20-holding-card-live-chart-design.md)
**Mockup:** [mockups/holding_card_chart_mockup.html](../../../mockups/holding_card_chart_mockup.html)

**Goal:** Embed a live-updating candle chart in each open-position card so the user can watch their holdings in real time, with zoom, pan, timeframe toggles, and a click-to-expand modal.

**Architecture:** Backend adds `/api/candles/live` that returns historical bars from the existing `candles` SQLite table (aggregated up for 5m/15m/1h) plus an in-progress "live" bar built from `market_tape.db`'s `ws_matches` ticks since the current bucket start. Frontend reuses the already-bundled `lightweight-charts` library for a new `LiveCandleChartComponent` that polls at 1 Hz, updates the last bar in place via `candleSeries.update()`, and overlays entry / trail-stop price lines. A modal wrapper renders the same component at larger size plus a 4-cell info panel.

**Tech Stack:** Flask + SQLite (backend), Angular 20 + standalone components + `lightweight-charts` v5 (frontend), no new dependencies.

---

## File Structure

**Create:**
- `dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts` — the reusable chart component (used both on-card and in-modal)
- `dashboard/ui/src/app/components/holding-card-chart-modal/holding-card-chart-modal.component.ts` — modal wrapper with info panel
- `tests/test_api_candles_live.py` — Flask endpoint tests

**Modify:**
- `dashboard/api/app.py` — add `_build_live_bar` helper + `/api/candles/live` route
- `dashboard/ui/src/app/services/api.service.ts` — add `LiveCandleBar` + `LiveCandlesResponse` types + `fetchLiveCandles` method
- `dashboard/ui/src/app/components/position-cards/position-cards.component.ts` — embed `<app-live-candle-chart>` below PnL row, open modal on click

---

## Conventions

- **Commit style:** match repo (`feat(...): ...`, `fix(...): ...`). Current branch is `master`. Commit after every passing test.
- **No military time anywhere user-visible.** 12-hour AM/PM. Use the existing `fmt12Hour` helper in `api.service.ts` for ISO timestamps.
- **Build before push.** Run `ng build` in `dashboard/ui/` before any push — ZimaOS doesn't build on deploy.
- **Bot DB read path:** `data/candles.db` (existing `candles` table; `granularity='ONE_MINUTE'` holds 1m bars) and `data/market_tape.db` (`ws_matches` for live ticks).
- **Timestamps in DB:** stored as naive-UTC ISO strings (no Z, no offset). Parse via `datetime.fromisoformat` + `.replace(tzinfo=timezone.utc)`.

---

## Task 1: Backend — live bar builder helper

Build a pure function that aggregates ws_matches ticks into an OHLC bar for the current (in-progress) bucket.

**Files:**
- Modify: `dashboard/api/app.py` — add helper near the `/api/candles` route (around line 394)
- Test: `tests/test_api_candles_live.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_candles_live.py`:

```python
"""Tests for the /api/candles/live live-chart endpoint."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta

import pytest


def _make_tape_db(path: str, ticks: list[tuple[str, str, float, float]]) -> None:
    """ticks: list of (pair, ts_iso_naive_utc, price, size)."""
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE ws_matches (
            pair TEXT, ts TEXT, price REAL, size REAL, side TEXT
        )"""
    )
    conn.executemany(
        "INSERT INTO ws_matches (pair, ts, price, size, side) VALUES (?,?,?,?,'buy')",
        ticks,
    )
    conn.commit()
    conn.close()


def test_build_live_bar_aggregates_ticks_in_current_bucket():
    from dashboard.api.app import _build_live_bar

    with tempfile.TemporaryDirectory() as tmp:
        tape_path = os.path.join(tmp, "market_tape.db")
        # Bucket starts at 2026-04-20 15:30:00 UTC
        bucket_start = datetime(2026, 4, 20, 15, 30, 0, tzinfo=timezone.utc)
        ticks = [
            ("FARTCOIN-USD", "2026-04-20T15:30:05", 0.200, 10.0),
            ("FARTCOIN-USD", "2026-04-20T15:30:17", 0.205, 5.0),
            ("FARTCOIN-USD", "2026-04-20T15:30:29", 0.199, 7.0),
            ("FARTCOIN-USD", "2026-04-20T15:30:50", 0.203, 3.0),
        ]
        _make_tape_db(tape_path, ticks)

        bar = _build_live_bar(tape_path, "FARTCOIN-USD", bucket_start)

        assert bar is not None
        assert bar["open"] == 0.200
        assert bar["high"] == 0.205
        assert bar["low"] == 0.199
        assert bar["close"] == 0.203
        assert bar["t"] == int(bucket_start.timestamp() * 1000)


def test_build_live_bar_returns_none_when_no_ticks():
    from dashboard.api.app import _build_live_bar

    with tempfile.TemporaryDirectory() as tmp:
        tape_path = os.path.join(tmp, "market_tape.db")
        _make_tape_db(tape_path, [])
        bucket_start = datetime(2026, 4, 20, 15, 30, 0, tzinfo=timezone.utc)

        bar = _build_live_bar(tape_path, "FARTCOIN-USD", bucket_start)
        assert bar is None


def test_build_live_bar_excludes_ticks_before_bucket_start():
    from dashboard.api.app import _build_live_bar

    with tempfile.TemporaryDirectory() as tmp:
        tape_path = os.path.join(tmp, "market_tape.db")
        bucket_start = datetime(2026, 4, 20, 15, 30, 0, tzinfo=timezone.utc)
        ticks = [
            # BEFORE bucket — must be ignored
            ("FARTCOIN-USD", "2026-04-20T15:29:55", 0.190, 10.0),
            # Inside bucket
            ("FARTCOIN-USD", "2026-04-20T15:30:05", 0.200, 10.0),
            ("FARTCOIN-USD", "2026-04-20T15:30:15", 0.202, 5.0),
        ]
        _make_tape_db(tape_path, ticks)

        bar = _build_live_bar(tape_path, "FARTCOIN-USD", bucket_start)
        assert bar["open"] == 0.200  # not 0.190
        assert bar["high"] == 0.202
        assert bar["low"] == 0.200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_api_candles_live.py -v`
Expected: FAIL — `ImportError: cannot import name '_build_live_bar' from 'dashboard.api.app'`

- [ ] **Step 3: Implement `_build_live_bar`**

In `dashboard/api/app.py`, add this helper just above the `/api/candles` route (around line 394, before the `# ---------- /api/candles ----------` comment):

```python
def _build_live_bar(tape_path: str, pair: str, bucket_start: datetime) -> dict | None:
    """Aggregate ws_matches ticks since bucket_start into an in-progress OHLC bar.

    Returns None when there are no ticks in the bucket yet.
    `bucket_start` must be timezone-aware UTC. The returned bar's `t` is ms since epoch.
    """
    if not os.path.exists(tape_path):
        return None
    start_iso = bucket_start.strftime("%Y-%m-%dT%H:%M:%S")
    conn = sqlite3.connect(tape_path)
    try:
        rows = conn.execute(
            "SELECT price FROM ws_matches "
            "WHERE pair = ? AND ts >= ? "
            "ORDER BY ts ASC",
            (pair, start_iso),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return None

    prices = [float(r[0]) for r in rows]
    return {
        "t": int(bucket_start.timestamp() * 1000),
        "open": prices[0],
        "high": max(prices),
        "low": min(prices),
        "close": prices[-1],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_api_candles_live.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add dashboard/api/app.py tests/test_api_candles_live.py
git commit -m "feat(api): add _build_live_bar helper for live-chart endpoint"
```

---

## Task 2: Backend — `/api/candles/live` route (1m only)

Wire the helper into a Flask route that returns historical 1m bars + the in-progress live bar.

**Files:**
- Modify: `dashboard/api/app.py` — add route after `/api/candles` (around line 424)
- Test: `tests/test_api_candles_live.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api_candles_live.py`:

```python
def _make_candles_db(path: str, candles: list[tuple[str, str, float, float, float, float, float]]) -> None:
    """candles: list of (pair, timestamp, open, high, low, close, volume). granularity='ONE_MINUTE'."""
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE candles (
            pair TEXT, granularity TEXT, timestamp TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL
        )"""
    )
    conn.executemany(
        "INSERT INTO candles (pair, granularity, timestamp, open, high, low, close, volume) "
        "VALUES (?, 'ONE_MINUTE', ?, ?, ?, ?, ?, ?)",
        candles,
    )
    conn.commit()
    conn.close()


def test_candles_live_returns_historical_and_live_bars(monkeypatch, tmp_path):
    from dashboard.api import app as app_mod

    candles_path = tmp_path / "candles.db"
    tape_path = tmp_path / "market_tape.db"

    # 3 historical 1m bars ending at 15:29
    _make_candles_db(str(candles_path), [
        ("FARTCOIN-USD", "2026-04-20T15:27:00", 0.195, 0.196, 0.194, 0.196, 100.0),
        ("FARTCOIN-USD", "2026-04-20T15:28:00", 0.196, 0.198, 0.195, 0.198, 120.0),
        ("FARTCOIN-USD", "2026-04-20T15:29:00", 0.198, 0.199, 0.197, 0.199, 90.0),
    ])
    # Live-forming bucket @ 15:30
    _make_tape_db(str(tape_path), [
        ("FARTCOIN-USD", "2026-04-20T15:30:05", 0.199, 10.0),
        ("FARTCOIN-USD", "2026-04-20T15:30:20", 0.201, 5.0),
    ])

    monkeypatch.setattr(app_mod, "DB_PATH", str(candles_path))
    # Freeze "now" at 15:30:25 so the current bucket is 15:30:00.
    frozen = datetime(2026, 4, 20, 15, 30, 25, tzinfo=timezone.utc)
    monkeypatch.setattr(app_mod, "_utcnow", lambda: frozen)

    client = app_mod.app.test_client()
    resp = client.get("/api/candles/live?pair=FARTCOIN-USD&tf=1m&limit=200")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["pair"] == "FARTCOIN-USD"
    assert data["tf"] == "1m"
    assert len(data["bars"]) == 3
    assert data["bars"][0]["close"] == 0.196
    assert data["bars"][-1]["close"] == 0.199

    live = data["live"]
    assert live is not None
    assert live["open"] == 0.199
    assert live["high"] == 0.201
    assert live["close"] == 0.201
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_api_candles_live.py::test_candles_live_returns_historical_and_live_bars -v`
Expected: FAIL — 404 (route not registered) or `AttributeError: module has no attribute '_utcnow'`

- [ ] **Step 3: Implement `_utcnow` + route**

In `dashboard/api/app.py`, add `_utcnow` near `_build_live_bar` (this wraps `datetime.now(timezone.utc)` so tests can freeze time):

```python
def _utcnow() -> datetime:
    """Wrapped so tests can monkeypatch the 'now' clock."""
    return datetime.now(timezone.utc)


def _bucket_start(now: datetime, tf: str) -> datetime:
    """Floor `now` to the start of its bucket for the given timeframe."""
    minutes_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}
    m = minutes_map[tf]
    if tf == "1h":
        return now.replace(minute=0, second=0, microsecond=0)
    bucket_min = (now.minute // m) * m
    return now.replace(minute=bucket_min, second=0, microsecond=0)
```

Then add the route after the existing `/api/candles` route (which ends around line 423):

```python
# ---------- /api/candles/live ----------

@app.route("/api/candles/live")
def api_candles_live():
    pair = request.args.get("pair", "")
    tf = request.args.get("tf", "1m")
    limit = int(request.args.get("limit", 200))
    if tf not in ("1m", "5m", "15m", "1h"):
        return jsonify({"error": f"invalid tf: {tf}"}), 400
    if not pair:
        return jsonify({"error": "pair required"}), 400

    now = _utcnow()
    bucket_start = _bucket_start(now, tf)

    # Historical bars (closed), up to but not including the current bucket.
    conn = get_db()
    try:
        if tf == "1m":
            rows = conn.execute(
                "SELECT timestamp, open, high, low, close FROM candles "
                "WHERE pair = ? AND granularity = 'ONE_MINUTE' AND timestamp < ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (pair, bucket_start.strftime("%Y-%m-%dT%H:%M:%S"), limit),
            ).fetchall()
            bars = [
                {
                    "t": int(datetime.fromisoformat(r["timestamp"])
                             .replace(tzinfo=timezone.utc).timestamp() * 1000),
                    "open": r["open"], "high": r["high"],
                    "low": r["low"], "close": r["close"],
                }
                for r in reversed(rows)
            ]
        else:
            # Higher-tf aggregation implemented in Task 3; stub for now.
            bars = []
    finally:
        conn.close()

    tape_path = os.path.join(os.path.dirname(DB_PATH), "market_tape.db")
    live = _build_live_bar(tape_path, pair, bucket_start)

    return jsonify({
        "pair": pair,
        "tf": tf,
        "server_time_ms": int(now.timestamp() * 1000),
        "bars": bars,
        "live": live,
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_api_candles_live.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add dashboard/api/app.py tests/test_api_candles_live.py
git commit -m "feat(api): add /api/candles/live endpoint (1m only)"
```

---

## Task 3: Backend — 5m/15m/1h aggregation

Extend the endpoint to aggregate 1m bars up to higher timeframes.

**Files:**
- Modify: `dashboard/api/app.py` — flesh out the `else` branch of `api_candles_live`
- Test: `tests/test_api_candles_live.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api_candles_live.py`:

```python
def test_candles_live_aggregates_5m_from_1m(monkeypatch, tmp_path):
    from dashboard.api import app as app_mod

    candles_path = tmp_path / "candles.db"
    tape_path = tmp_path / "market_tape.db"

    # 10 minutes of 1m bars: two complete 5m buckets (15:20-15:24 and 15:25-15:29),
    # plus an in-progress 15:30 bucket via ws_matches.
    _make_candles_db(str(candles_path), [
        ("F-USD", "2026-04-20T15:20:00", 1.00, 1.02, 0.99, 1.01, 1.0),
        ("F-USD", "2026-04-20T15:21:00", 1.01, 1.03, 1.00, 1.02, 1.0),
        ("F-USD", "2026-04-20T15:22:00", 1.02, 1.04, 1.01, 1.03, 1.0),
        ("F-USD", "2026-04-20T15:23:00", 1.03, 1.05, 1.02, 1.04, 1.0),
        ("F-USD", "2026-04-20T15:24:00", 1.04, 1.06, 1.03, 1.05, 1.0),
        ("F-USD", "2026-04-20T15:25:00", 1.05, 1.07, 1.04, 1.06, 1.0),
        ("F-USD", "2026-04-20T15:26:00", 1.06, 1.08, 1.05, 1.07, 1.0),
        ("F-USD", "2026-04-20T15:27:00", 1.07, 1.09, 1.06, 1.08, 1.0),
        ("F-USD", "2026-04-20T15:28:00", 1.08, 1.10, 1.07, 1.09, 1.0),
        ("F-USD", "2026-04-20T15:29:00", 1.09, 1.11, 1.08, 1.10, 1.0),
    ])
    _make_tape_db(str(tape_path), [
        ("F-USD", "2026-04-20T15:30:10", 1.10, 1.0),
        ("F-USD", "2026-04-20T15:30:20", 1.12, 1.0),
    ])

    monkeypatch.setattr(app_mod, "DB_PATH", str(candles_path))
    frozen = datetime(2026, 4, 20, 15, 30, 25, tzinfo=timezone.utc)
    monkeypatch.setattr(app_mod, "_utcnow", lambda: frozen)

    client = app_mod.app.test_client()
    resp = client.get("/api/candles/live?pair=F-USD&tf=5m&limit=50")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["tf"] == "5m"
    assert len(data["bars"]) == 2

    # First bucket: 15:20 open=1.00, max high=1.06, min low=0.99, close=1.05
    b0 = data["bars"][0]
    assert b0["open"] == 1.00
    assert b0["high"] == 1.06
    assert b0["low"] == 0.99
    assert b0["close"] == 1.05

    # Second bucket: 15:25 open=1.05, close=1.10
    b1 = data["bars"][1]
    assert b1["open"] == 1.05
    assert b1["close"] == 1.10

    # Live bucket built from ws_matches @ 15:30
    assert data["live"]["open"] == 1.10
    assert data["live"]["close"] == 1.12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest tests/test_api_candles_live.py::test_candles_live_aggregates_5m_from_1m -v`
Expected: FAIL — `assert len(data["bars"]) == 2` fails (currently returns 0).

- [ ] **Step 3: Implement aggregation**

Replace the `else: bars = []` stub in `dashboard/api/app.py` with:

```python
        else:
            # Aggregate 1m bars into higher-tf buckets, then trim to `limit` most recent.
            tf_minutes = {"5m": 5, "15m": 15, "1h": 60}[tf]
            bucket_seconds = tf_minutes * 60
            rows = conn.execute(
                "SELECT timestamp, open, high, low, close FROM candles "
                "WHERE pair = ? AND granularity = 'ONE_MINUTE' AND timestamp < ? "
                "ORDER BY timestamp ASC",
                (pair, bucket_start.strftime("%Y-%m-%dT%H:%M:%S")),
            ).fetchall()

            buckets: dict[int, dict] = {}
            for r in rows:
                ts = datetime.fromisoformat(r["timestamp"]).replace(tzinfo=timezone.utc)
                epoch = int(ts.timestamp())
                bkey = (epoch // bucket_seconds) * bucket_seconds
                b = buckets.get(bkey)
                if b is None:
                    buckets[bkey] = {
                        "t": bkey * 1000,
                        "open": r["open"], "high": r["high"],
                        "low": r["low"], "close": r["close"],
                    }
                else:
                    b["high"] = max(b["high"], r["high"])
                    b["low"] = min(b["low"], r["low"])
                    b["close"] = r["close"]

            bars = [buckets[k] for k in sorted(buckets.keys())][-limit:]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -m pytest tests/test_api_candles_live.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add dashboard/api/app.py tests/test_api_candles_live.py
git commit -m "feat(api): aggregate 5m/15m/1h live candles from 1m"
```

---

## Task 4: Frontend — ApiService types + `fetchLiveCandles`

Add the typed method the component will call.

**Files:**
- Modify: `dashboard/ui/src/app/services/api.service.ts` — add types near the other exports, add method inside `ApiService`

- [ ] **Step 1: Add types**

In `dashboard/ui/src/app/services/api.service.ts`, after the `CandleData` interface (around line 13), add:

```typescript
export interface LiveCandleBar {
  t: number;  // ms since epoch, bucket start
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface LiveCandlesResponse {
  pair: string;
  tf: '1m' | '5m' | '15m' | '1h';
  server_time_ms: number;
  bars: LiveCandleBar[];
  live: LiveCandleBar | null;
}
```

- [ ] **Step 2: Add the fetch method**

Inside `ApiService` class (near `fetchCandles` around line 534), add:

```typescript
  fetchLiveCandles(pair: string, tf: '1m' | '5m' | '15m' | '1h' = '1m', limit = 200) {
    return this.http.get<LiveCandlesResponse>(`${API}/candles/live`, {
      params: { pair, tf, limit: limit.toString() },
    });
  }
```

- [ ] **Step 3: Verify the frontend type-checks**

Run: `cd dashboard/ui && npx tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add dashboard/ui/src/app/services/api.service.ts
git commit -m "feat(ui): add fetchLiveCandles API client + types"
```

---

## Task 5: Frontend — `LiveCandleChartComponent` scaffold

Stand up the component with `lightweight-charts` + initial-load of historical + live bars. No polling or timeframe toggles yet — just a static snapshot rendered from one fetch.

**Files:**
- Create: `dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts`

- [ ] **Step 1: Create the component file**

```typescript
import {
  Component, input, effect, ElementRef, viewChild, OnDestroy, signal,
} from '@angular/core';
import {
  createChart, IChartApi, ISeriesApi, Time,
  CandlestickSeries, CandlestickData,
} from 'lightweight-charts';
import { ApiService, LiveCandleBar } from '../../services/api.service';

@Component({
  selector: 'app-live-candle-chart',
  standalone: true,
  template: `
    <div class="live-chart-root">
      <div #chartContainer class="chart-container" [style.height.px]="height()"></div>
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }
    .live-chart-root { width: 100%; background: #0f1117; border: 1px solid #2d3148; border-radius: 6px; overflow: hidden; }
    .chart-container { width: 100%; }
  `],
})
export class LiveCandleChartComponent implements OnDestroy {
  pair = input.required<string>();
  entry = input<number>(0);
  trailStop = input<number>(0);
  height = input<number>(160);

  chartContainer = viewChild<ElementRef<HTMLDivElement>>('chartContainer');

  private chart: IChartApi | null = null;
  private candleSeries: ISeriesApi<'Candlestick'> | null = null;
  private resizeObserver: ResizeObserver | null = null;

  constructor(private api: ApiService) {
    effect(() => {
      const container = this.chartContainer();
      const p = this.pair();
      if (!container || !p) return;
      if (!this.chart) this.initChart(container.nativeElement);
      this.loadData(p, '1m');
    });
  }

  private initChart(container: HTMLDivElement): void {
    this.chart = createChart(container, {
      width: container.clientWidth,
      height: this.height(),
      layout: { background: { color: '#0f1117' }, textColor: '#8895ad' },
      grid: { vertLines: { color: '#1e2130' }, horzLines: { color: '#1e2130' } },
      rightPriceScale: { borderColor: '#1e2130' },
      timeScale: { borderColor: '#1e2130', timeVisible: true, secondsVisible: false },
    });
    this.candleSeries = this.chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e', downColor: '#ef4444',
      borderUpColor: '#22c55e', borderDownColor: '#ef4444',
      wickUpColor: '#22c55e', wickDownColor: '#ef4444',
    });

    this.resizeObserver = new ResizeObserver(entries => {
      for (const e of entries) this.chart?.applyOptions({ width: e.contentRect.width });
    });
    this.resizeObserver.observe(container);
  }

  private loadData(pair: string, tf: '1m' | '5m' | '15m' | '1h'): void {
    this.api.fetchLiveCandles(pair, tf, 200).subscribe({
      next: (resp) => this.applyBars(resp.bars, resp.live),
      error: () => {},
    });
  }

  private applyBars(bars: LiveCandleBar[], live: LiveCandleBar | null): void {
    if (!this.candleSeries) return;
    const series: CandlestickData<Time>[] = bars.map(b => ({
      time: (b.t / 1000) as Time, open: b.open, high: b.high, low: b.low, close: b.close,
    }));
    if (live) series.push({
      time: (live.t / 1000) as Time,
      open: live.open, high: live.high, low: live.low, close: live.close,
    });
    this.candleSeries.setData(series);
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    if (this.chart) { this.chart.remove(); this.chart = null; }
  }
}
```

- [ ] **Step 2: Type-check**

Run: `cd dashboard/ui && npx tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts
git commit -m "feat(ui): add LiveCandleChartComponent scaffold (static snapshot)"
```

---

## Task 6: Frontend — 1 Hz polling + visibility-pause

Turn the static snapshot into a live-updating chart.

**Files:**
- Modify: `dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts`

- [ ] **Step 1: Add polling state + tick**

Replace the component class body with (keeping imports + template + styles):

```typescript
export class LiveCandleChartComponent implements OnDestroy {
  pair = input.required<string>();
  entry = input<number>(0);
  trailStop = input<number>(0);
  height = input<number>(160);

  chartContainer = viewChild<ElementRef<HTMLDivElement>>('chartContainer');

  private chart: IChartApi | null = null;
  private candleSeries: ISeriesApi<'Candlestick'> | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private pollTimer: any = null;
  private visHandler: (() => void) | null = null;
  private currentTf: '1m' | '5m' | '15m' | '1h' = '1m';
  private lastLiveBucketMs = 0;

  constructor(private api: ApiService) {
    effect(() => {
      const container = this.chartContainer();
      const p = this.pair();
      if (!container || !p) return;
      if (!this.chart) this.initChart(container.nativeElement);
      this.loadData(p, this.currentTf);
      this.startPolling();
    });
  }

  private initChart(container: HTMLDivElement): void {
    this.chart = createChart(container, {
      width: container.clientWidth,
      height: this.height(),
      layout: { background: { color: '#0f1117' }, textColor: '#8895ad' },
      grid: { vertLines: { color: '#1e2130' }, horzLines: { color: '#1e2130' } },
      rightPriceScale: { borderColor: '#1e2130' },
      timeScale: { borderColor: '#1e2130', timeVisible: true, secondsVisible: false },
    });
    this.candleSeries = this.chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e', downColor: '#ef4444',
      borderUpColor: '#22c55e', borderDownColor: '#ef4444',
      wickUpColor: '#22c55e', wickDownColor: '#ef4444',
    });

    this.resizeObserver = new ResizeObserver(entries => {
      for (const e of entries) this.chart?.applyOptions({ width: e.contentRect.width });
    });
    this.resizeObserver.observe(container);
  }

  private loadData(pair: string, tf: '1m' | '5m' | '15m' | '1h'): void {
    this.api.fetchLiveCandles(pair, tf, 200).subscribe({
      next: (resp) => {
        this.setAllBars(resp.bars, resp.live);
        this.lastLiveBucketMs = resp.live?.t ?? 0;
      },
      error: () => {},
    });
  }

  private setAllBars(bars: LiveCandleBar[], live: LiveCandleBar | null): void {
    if (!this.candleSeries) return;
    const series: CandlestickData<Time>[] = bars.map(b => ({
      time: (b.t / 1000) as Time, open: b.open, high: b.high, low: b.low, close: b.close,
    }));
    if (live) series.push({
      time: (live.t / 1000) as Time,
      open: live.open, high: live.high, low: live.low, close: live.close,
    });
    this.candleSeries.setData(series);
  }

  private startPolling(): void {
    this.stopPolling();
    this.pollTimer = setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      this.tick();
    }, 1000);
    this.visHandler = () => { if (document.visibilityState === 'visible') this.tick(); };
    document.addEventListener('visibilitychange', this.visHandler);
  }

  private stopPolling(): void {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
    if (this.visHandler) { document.removeEventListener('visibilitychange', this.visHandler); this.visHandler = null; }
  }

  private tick(): void {
    const p = this.pair();
    if (!p || !this.candleSeries) return;
    this.api.fetchLiveCandles(p, this.currentTf, 200).subscribe({
      next: (resp) => {
        const live = resp.live;
        const newestHistorical = resp.bars.length ? resp.bars[resp.bars.length - 1] : null;

        // If a new closed bar appeared (lastLiveBucketMs advanced), reload full window.
        if (live && this.lastLiveBucketMs && live.t !== this.lastLiveBucketMs) {
          this.setAllBars(resp.bars, live);
          this.lastLiveBucketMs = live.t;
          return;
        }
        // Otherwise just update the live-forming bar in place.
        if (live) {
          this.candleSeries!.update({
            time: (live.t / 1000) as Time,
            open: live.open, high: live.high, low: live.low, close: live.close,
          });
          if (!this.lastLiveBucketMs) this.lastLiveBucketMs = live.t;
        } else if (newestHistorical) {
          this.candleSeries!.update({
            time: (newestHistorical.t / 1000) as Time,
            open: newestHistorical.open, high: newestHistorical.high,
            low: newestHistorical.low, close: newestHistorical.close,
          });
        }
      },
      error: () => {},
    });
  }

  ngOnDestroy(): void {
    this.stopPolling();
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    if (this.chart) { this.chart.remove(); this.chart = null; }
  }
}
```

- [ ] **Step 2: Type-check**

Run: `cd dashboard/ui && npx tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts
git commit -m "feat(ui): LiveCandleChart — 1Hz polling with visibility-pause"
```

---

## Task 7: Frontend — timeframe toggles (1m/5m/15m/1h)

Add the tf button row above the chart.

**Files:**
- Modify: `dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts`

- [ ] **Step 1: Replace template + add toggle method**

Replace the `template:` string with:

```typescript
  template: `
    <div class="live-chart-root">
      <div class="chart-top">
        <div class="tf-group">
          <button class="tf-btn" [class.active]="currentTf === '1m'"  (click)="setTf('1m')">1m</button>
          <button class="tf-btn" [class.active]="currentTf === '5m'"  (click)="setTf('5m')">5m</button>
          <button class="tf-btn" [class.active]="currentTf === '15m'" (click)="setTf('15m')">15m</button>
          <button class="tf-btn" [class.active]="currentTf === '1h'"  (click)="setTf('1h')">1h</button>
        </div>
        <span class="live-pill">LIVE · 1Hz</span>
      </div>
      <div #chartContainer class="chart-container" [style.height.px]="height()"></div>
    </div>
  `,
```

Replace the `styles:` string with:

```typescript
  styles: [`
    :host { display: block; width: 100%; }
    .live-chart-root { width: 100%; background: #0f1117; border: 1px solid #2d3148; border-radius: 6px; overflow: hidden; }
    .chart-top { display: flex; justify-content: space-between; align-items: center; padding: 4px 6px; }
    .tf-group { display: flex; gap: 2px; }
    .tf-btn {
      background: transparent; color: #8895ad;
      border: 1px solid #2d3148; border-radius: 3px;
      padding: 2px 8px; font-size: 11px; cursor: pointer; font-family: inherit;
    }
    .tf-btn:hover { border-color: #3b82f6; color: #e6ecf5; }
    .tf-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
    .live-pill {
      background: rgba(34,197,94,.15); color: #22c55e;
      padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600;
      letter-spacing: .5px;
    }
    .live-pill::before {
      content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%;
      background: #22c55e; margin-right: 5px; animation: pulse 1s infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .3 } }
    .chart-container { width: 100%; }
  `],
```

Change `currentTf` from `private` to public (so template can read it), and add `setTf`:

```typescript
  public currentTf: '1m' | '5m' | '15m' | '1h' = '1m';
```

```typescript
  setTf(tf: '1m' | '5m' | '15m' | '1h'): void {
    if (tf === this.currentTf) return;
    this.currentTf = tf;
    this.lastLiveBucketMs = 0;
    const p = this.pair();
    if (p) this.loadData(p, tf);
  }
```

- [ ] **Step 2: Type-check + smoke-test in browser**

Run: `cd dashboard/ui && npx tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

Run: `cd dashboard/ui && npm run start` then open `http://localhost:4200` and toggle the timeframe buttons — the chart should reload bars each time.

- [ ] **Step 3: Commit**

```bash
git add dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts
git commit -m "feat(ui): LiveCandleChart — 1m/5m/15m/1h timeframe toggles"
```

---

## Task 8: Frontend — entry / trail / now price lines

Overlay the entry price (blue dashed), trail stop (red dashed), and live "now" price line (amber) via `createPriceLine`. The "now" line re-applies each tick.

**Files:**
- Modify: `dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts`

- [ ] **Step 1: Add price line state**

Add imports:

```typescript
import { IPriceLine } from 'lightweight-charts';
```

Inside the class (near the other private fields):

```typescript
  private entryLine: IPriceLine | null = null;
  private trailLine: IPriceLine | null = null;
  private nowLine: IPriceLine | null = null;
  private lastNowPrice = 0;
```

- [ ] **Step 2: Wire in the effect + update on every tick**

Add a second `effect` to the constructor, below the first:

```typescript
    effect(() => {
      const e = this.entry();
      const t = this.trailStop();
      if (!this.candleSeries) return;
      if (this.entryLine) { this.candleSeries.removePriceLine(this.entryLine); this.entryLine = null; }
      if (this.trailLine) { this.candleSeries.removePriceLine(this.trailLine); this.trailLine = null; }
      if (e > 0) {
        this.entryLine = this.candleSeries.createPriceLine({
          price: e, color: '#3b82f6', lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title: 'entry',
        });
      }
      if (t > 0) {
        this.trailLine = this.candleSeries.createPriceLine({
          price: t, color: '#ef4444', lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title: 'trail',
        });
      }
    });
```

In `setAllBars` (end of function) and `tick` (after `candleSeries.update` in both branches), add a call to `this.updateNowLine(bars, live)` — here's the helper, place it as a class method:

```typescript
  private updateNowLine(bars: LiveCandleBar[], live: LiveCandleBar | null): void {
    if (!this.candleSeries) return;
    const nowPrice = live?.close ?? (bars.length ? bars[bars.length - 1].close : 0);
    if (!nowPrice || nowPrice === this.lastNowPrice) return;
    if (this.nowLine) this.candleSeries.removePriceLine(this.nowLine);
    this.nowLine = this.candleSeries.createPriceLine({
      price: nowPrice, color: '#fbbf24', lineWidth: 1, lineStyle: 2,
      axisLabelVisible: true, title: 'now',
    });
    this.lastNowPrice = nowPrice;
  }
```

Update `setAllBars` to end with:

```typescript
    this.updateNowLine(bars, live);
```

Update `tick`'s success branch to call `this.updateNowLine(resp.bars, resp.live)` after either branch applies.

- [ ] **Step 3: Type-check + browser smoke**

Run: `cd dashboard/ui && npx tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

Browser-check: entry line (blue dashed), trail line (red dashed), now line (amber) all visible with right-axis labels.

- [ ] **Step 4: Commit**

```bash
git add dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts
git commit -m "feat(ui): LiveCandleChart — entry/trail/now price-line overlays"
```

---

## Task 9: Frontend — zoom / pan / snap-to-live

`lightweight-charts` handles mouse-wheel zoom and click-drag pan natively. We add: (a) a `● go live` pill that appears when the visible range is panned off the live edge, (b) double-click to snap back.

**Files:**
- Modify: `dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts`

- [ ] **Step 1: Add state + template elements**

Add imports:

```typescript
import { LogicalRange } from 'lightweight-charts';
```

Add state:

```typescript
  readonly pannedOff = signal(false);
  private barCount = 0;
```

Whenever bars are loaded or updated, update `barCount`. In `setAllBars`, at the top add:

```typescript
    this.barCount = bars.length + (live ? 1 : 0);
```

In `tick`'s new-bucket branch (after `setAllBars`), add:

```typescript
    this.barCount = resp.bars.length + (resp.live ? 1 : 0);
```

Update the template — add the `go live` pill as a positioned overlay inside `.live-chart-root`:

```html
      <button class="jump-live" [class.show]="pannedOff()" (click)="snapToLive()">● go live</button>
```

Add its CSS inside the existing `styles:`:

```css
    .live-chart-root { position: relative; }
    .jump-live {
      display: none; position: absolute; bottom: 10px; right: 60px;
      background: #22c55e; color: #0b0f17;
      border: 1px solid #22c55e; border-radius: 12px;
      padding: 3px 10px; font-size: 10px; font-weight: 700; cursor: pointer;
      font-family: inherit; letter-spacing: .3px;
      box-shadow: 0 2px 8px rgba(34,197,94,.4); z-index: 2;
    }
    .jump-live.show { display: inline-block; }
    .jump-live:hover { background: #16a34a; border-color: #16a34a; }
```

- [ ] **Step 2: Subscribe to visibleLogicalRangeChange + add snap method**

Inside `initChart`, after `this.candleSeries = …`, add:

```typescript
    this.chart.timeScale().subscribeVisibleLogicalRangeChange((range: LogicalRange | null) => {
      if (!range) { this.pannedOff.set(false); return; }
      const lastIdx = this.barCount - 1;
      // If the right edge of the visible range is >1 bar left of the last bar, we're panned off.
      this.pannedOff.set(range.to < lastIdx - 1);
    });
    // double-click to snap to live
    container.addEventListener('dblclick', () => this.snapToLive());
```

Add `snapToLive` as a class method:

```typescript
  snapToLive(): void {
    this.chart?.timeScale().scrollToRealTime();
    this.pannedOff.set(false);
  }
```

- [ ] **Step 3: Type-check + browser smoke**

Run: `cd dashboard/ui && npx tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

Browser-check:
- Mouse-wheel over chart → zoom in/out
- Click-and-drag left/right → pans through history
- When panned, `● go live` pill appears bottom-right
- Click pill OR double-click chart → snaps back to the live edge

- [ ] **Step 4: Commit**

```bash
git add dashboard/ui/src/app/components/live-candle-chart/live-candle-chart.component.ts
git commit -m "feat(ui): LiveCandleChart — zoom, pan, go-live snap-back"
```

---

## Task 10: Frontend — `HoldingCardChartModalComponent`

Modal wrapper that renders the same `LiveCandleChartComponent` at 460px height + a 4-cell info panel.

**Files:**
- Create: `dashboard/ui/src/app/components/holding-card-chart-modal/holding-card-chart-modal.component.ts`

- [ ] **Step 1: Create the modal component**

```typescript
import { Component, input, output } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { LiveCandleChartComponent } from '../live-candle-chart/live-candle-chart.component';

@Component({
  selector: 'app-holding-card-chart-modal',
  standalone: true,
  imports: [DecimalPipe, LiveCandleChartComponent],
  template: `
    <div class="modal-backdrop" (click)="close.emit()">
      <div class="modal" (click)="$event.stopPropagation()">
        <div class="modal-head">
          <div class="modal-title">{{ pair() }}</div>
          <button class="modal-close" (click)="close.emit()">close</button>
        </div>
        <div class="modal-body">
          <app-live-candle-chart
            [pair]="pair()"
            [entry]="entry()"
            [trailStop]="trailStop()"
            [height]="460"
          />
          <div class="info-panel">
            <div class="cell">
              <div class="label">Entry</div>
              <div class="value">{{ entry() | number:'1.4-6' }}</div>
            </div>
            <div class="cell">
              <div class="label">Now</div>
              <div class="value">{{ nowPrice() | number:'1.4-6' }}</div>
            </div>
            <div class="cell">
              <div class="label">Trail stop</div>
              <div class="value" style="color:#ef4444">{{ trailStop() | number:'1.4-6' }}</div>
            </div>
            <div class="cell">
              <div class="label">Peak (session)</div>
              <div class="value" style="color:#22c55e">{{ peakPrice() | number:'1.4-6' }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .modal-backdrop {
      position: fixed; inset: 0; background: rgba(0,0,0,.6);
      display: flex; align-items: center; justify-content: center; z-index: 100;
    }
    .modal {
      background: #161926; border: 1px solid #2d3148; border-radius: 8px;
      width: min(1080px, 94vw); max-height: 90vh; overflow: auto;
    }
    .modal-head {
      display: flex; justify-content: space-between; align-items: center;
      padding: 12px 16px; border-bottom: 1px solid #2d3148;
    }
    .modal-title { font-weight: 700; font-size: 16px; color: #e6ecf5; }
    .modal-close {
      background: transparent; color: #8895ad; border: 1px solid #2d3148;
      border-radius: 4px; padding: 4px 10px; cursor: pointer; font-family: inherit;
    }
    .modal-close:hover { color: #e6ecf5; border-color: #3b82f6; }
    .modal-body { padding: 12px 16px; }
    .info-panel {
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 10px; margin-top: 12px;
    }
    .cell {
      background: #0f1117; border: 1px solid #2d3148; border-radius: 6px;
      padding: 8px 12px;
    }
    .label { color: #8895ad; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; }
    .value { color: #e6ecf5; font-size: 16px; font-weight: 600; margin-top: 4px; }
  `],
})
export class HoldingCardChartModalComponent {
  pair = input.required<string>();
  entry = input<number>(0);
  trailStop = input<number>(0);
  nowPrice = input<number>(0);
  peakPrice = input<number>(0);
  close = output<void>();
}
```

- [ ] **Step 2: Type-check**

Run: `cd dashboard/ui && npx tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/ui/src/app/components/holding-card-chart-modal/holding-card-chart-modal.component.ts
git commit -m "feat(ui): add HoldingCardChartModal with 4-cell info panel"
```

---

## Task 11: Frontend — wire into `PositionCardsComponent`

Embed `<app-live-candle-chart>` below the PnL row, open the modal on click, stop the modal on close.

**Files:**
- Modify: `dashboard/ui/src/app/components/position-cards/position-cards.component.ts`

- [ ] **Step 1: Rewrite the component**

Replace the full contents of `dashboard/ui/src/app/components/position-cards/position-cards.component.ts` with:

```typescript
import { Component, input, computed, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { PositionData, MomentumHoldingData } from '../../services/api.service';
import { LiveCandleChartComponent } from '../live-candle-chart/live-candle-chart.component';
import { HoldingCardChartModalComponent } from '../holding-card-chart-modal/holding-card-chart-modal.component';

@Component({
  selector: 'app-position-cards',
  standalone: true,
  imports: [DecimalPipe, LiveCandleChartComponent, HoldingCardChartModalComponent],
  template: `
    <div class="cards-container">
      @for (pos of enrichedPositions(); track pos.pair) {
        <div class="pos-card" [style.border-left-color]="pos.isUp ? '#22c55e' : '#ef4444'">
          <div class="pos-header">
            <span class="pos-pair">{{ pos.ticker }}</span>
            <span class="pos-qty">{{ pos.quantity | number:'1.4-4' }} units</span>
          </div>
          <div class="pos-details">
            <span>Bought at <strong>{{ pos.entry_price | number:'1.4-6' }}</strong></span>
            <span class="sep">&rarr;</span>
            <span>target <strong>{{ pos.sellTarget | number:'1.4-6' }}</strong></span>
          </div>
          <div class="pos-current">
            Current <strong>{{ pos.current_price | number:'1.4-6' }}</strong>
            &mdash;
            <span [style.color]="pos.isUp ? '#22c55e' : '#ef4444'">
              needs {{ pos.pctToSell > 0 ? '+' : '' }}{{ pos.pctToSell | number:'1.1-1' }}% to sell
            </span>
          </div>
          <div class="pos-pnl" [style.color]="pos.unrealized_pnl >= 0 ? '#22c55e' : '#ef4444'">
            PnL: {{ pos.unrealized_pnl >= 0 ? '+' : '' }}{{ pos.unrealized_pnl | number:'1.2-2' }} USD
            ({{ pos.unrealized_pnl_pct >= 0 ? '+' : '' }}{{ pos.unrealized_pnl_pct | number:'1.2-2' }}%)
          </div>

          <div class="chart-wrap" (click)="openModal(pos.pair)">
            <app-live-candle-chart
              [pair]="pos.pair"
              [entry]="pos.entry_price"
              [trailStop]="trailStopFor(pos.pair)"
              [height]="160"
            />
          </div>
        </div>
      } @empty {
        <div class="no-positions">No open positions</div>
      }
    </div>

    @if (modalPair()) {
      @let p = positionByPair(modalPair()!);
      @if (p) {
        <app-holding-card-chart-modal
          [pair]="p.pair"
          [entry]="p.entry_price"
          [trailStop]="trailStopFor(p.pair)"
          [nowPrice]="p.current_price"
          [peakPrice]="peakPriceFor(p.pair)"
          (close)="closeModal()"
        />
      }
    }
  `,
  styles: [`
    .cards-container {
      display: flex; flex-wrap: wrap; gap: 12px; padding: 8px 0;
    }
    .pos-card {
      background: #161926; border: 1px solid #2d3148;
      border-left: 3px solid #22c55e; border-radius: 6px;
      padding: 10px 14px; min-width: 320px; flex: 1 1 320px; max-width: 460px;
    }
    .pos-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .pos-pair { font-weight: 600; font-size: 14px; color: #e1e4ed; }
    .pos-qty { font-size: 12px; color: #8b8fa3; }
    .pos-details { font-size: 12px; color: #a0a4b8; margin-bottom: 4px; }
    .pos-details strong { color: #e1e4ed; }
    .sep { margin: 0 4px; color: #555; }
    .pos-current { font-size: 12px; color: #a0a4b8; margin-bottom: 4px; }
    .pos-current strong { color: #e1e4ed; }
    .pos-pnl { font-size: 12px; font-weight: 500; margin-top: 4px; margin-bottom: 10px; }
    .chart-wrap { cursor: pointer; }
    .no-positions { color: #555; font-size: 13px; padding: 8px 0; }
  `],
})
export class PositionCardsComponent {
  positions = input<PositionData[]>([]);
  holdings = input<MomentumHoldingData[]>([]);

  readonly modalPair = signal<string | null>(null);

  enrichedPositions = computed(() => {
    return this.positions()
      .filter(p => p.quantity > 0)
      .map(pos => {
        const sellTarget = pos.entry_price * 1.05;
        const pctToSell = ((sellTarget - pos.current_price) / pos.current_price) * 100;
        const ticker = pos.pair.replace('-USD', '');
        const isUp = pos.current_price >= pos.entry_price;
        return { ...pos, sellTarget, pctToSell, ticker, isUp };
      });
  });

  private holdingByPair(pair: string): MomentumHoldingData | undefined {
    return this.holdings().find(h => h.pair === pair);
  }

  trailStopFor(pair: string): number {
    const h = this.holdingByPair(pair);
    // Prefer wall-aware stop when present, fall back to trail_stop_price.
    return h?.wall_aware_stop || h?.trail_stop_price || 0;
  }

  peakPriceFor(pair: string): number {
    return this.holdingByPair(pair)?.peak_price || 0;
  }

  positionByPair(pair: string): PositionData | undefined {
    return this.positions().find(p => p.pair === pair);
  }

  openModal(pair: string): void {
    this.modalPair.set(pair);
  }

  closeModal(): void {
    this.modalPair.set(null);
  }
}
```

- [ ] **Step 2: Wire `holdings` + drag-suppression from the parent**

`<app-position-cards>` has one consumer: [equity-curve.component.ts:103](../../../dashboard/ui/src/app/components/equity-curve/equity-curve.component.ts#L103). That component already imports `ApiService`. Add a getter above the template that exposes momentum holdings (they carry the trail-stop + peak values), and wire it into the child:

In the class body of `EquityCurveComponent` (after the existing fields), add:

```typescript
  readonly momentumHoldings = () => this.api.momentumStatus()?.holdings ?? [];
```

Update the template line from:

```html
<app-position-cards [positions]="positions()" />
```

to:

```html
<app-position-cards [positions]="positions()" [holdings]="momentumHoldings()" />
```

- [ ] **Step 3: Add drag-suppression for the chart click**

Inside `PositionCardsComponent`, the `<div class="chart-wrap" (click)="openModal(pos.pair)">` wrapper would open the modal even after a pan-drag on lightweight-charts. Add a pointer tracker:

Replace the `.chart-wrap` `<div>` with:

```html
<div
  class="chart-wrap"
  (pointerdown)="onChartPointerDown($event)"
  (pointerup)="onChartPointerUp($event, pos.pair)">
  <app-live-candle-chart
    [pair]="pos.pair"
    [entry]="pos.entry_price"
    [trailStop]="trailStopFor(pos.pair)"
    [height]="160"
  />
</div>
```

Add to the class:

```typescript
  private dragStartX = 0;
  private dragStartY = 0;

  onChartPointerDown(e: PointerEvent): void {
    this.dragStartX = e.clientX;
    this.dragStartY = e.clientY;
  }

  onChartPointerUp(e: PointerEvent, pair: string): void {
    const dx = Math.abs(e.clientX - this.dragStartX);
    const dy = Math.abs(e.clientY - this.dragStartY);
    if (dx < 4 && dy < 4) this.openModal(pair);
  }
```

- [ ] **Step 4: Type-check**

Run: `cd dashboard/ui && npx tsc --noEmit -p tsconfig.app.json`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add dashboard/ui/src/app/components/position-cards/position-cards.component.ts \
        dashboard/ui/src/app/components/equity-curve/equity-curve.component.ts
git commit -m "feat(ui): embed LiveCandleChart + modal into position cards"
```

---

## Task 12: Production build + manual smoke test

**Files:**
- Modify: none (verification only)

- [ ] **Step 1: Run a full production build**

Run: `cd dashboard/ui && npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 2: Start backend + frontend**

Run (two terminals):
```bash
py dashboard/api/app.py
```
```bash
cd dashboard/ui && npm run start
```

- [ ] **Step 3: Manual acceptance walkthrough**

Open `http://localhost:4200`. For each acceptance criterion in [the spec](../specs/2026-04-20-holding-card-live-chart-design.md#acceptance-criteria), verify visually:

1. Each open position shows a candle chart below PnL (1m, ~50 bars default).
2. The last candle visibly updates at 1 Hz as ticks arrive.
3. Entry (blue dashed) + trail (red dashed) lines with right-axis labels.
4. Clicking 1m / 5m / 15m / 1h reloads at the new timeframe; live updates continue.
5. Mouse-wheel zoom adjusts visible bar count.
6. Click-and-drag pans history; `● go live` pill appears when panned; click pill OR double-click chart → snap back.
7. Clicking the chart body opens the modal at 460px height with 4-cell info panel.
8. Closing the modal stops any orphan polling (open DevTools Network tab; traffic to `/api/candles/live` should stop for the modal chart).
9. Background the tab (switch to another tab) for 5s; Network polling pauses; return → polling resumes.
10. Other dashboard panels continue to refresh on the 60s cycle.

Record any failures in a git comment and treat each as a follow-up fix task.

- [ ] **Step 4: Commit the built assets** (only if this repo's deploy pipeline tracks them — this repo does)

```bash
git add dashboard/ui/dist/
git commit -m "build(ui): production bundle for holding-card live chart"
```

- [ ] **Step 5: Final sanity check**

Run: `git log --oneline -15`
Expected: a clean series of per-task commits ending in the build commit.

---

## Out of scope (per spec)

- Indicator overlays (BB/EMA/VWAP) — not on the mini chart
- Trade markers (buy/sell arrows) — future work
- Multi-position comparison chart
- Depth/orderbook overlay (lives in the L2 ladder)
- Pre-entry charts for coins we don't hold
- WebSocket push (1 Hz polling is the first implementation; upgrade later if latency matters)
