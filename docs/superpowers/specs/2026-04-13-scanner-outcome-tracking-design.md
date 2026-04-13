# Scanner Outcome Tracking & Signal Learning — Design Spec

## Goal

Make the early momentum scanner track how its alerts actually perform, learn which signal combinations win, and auto-adjust scores so the best combos rise to the top and weak ones get demoted. Show all of this transparently in the dashboard.

## Problem

1. Current outcome tracking checks price at exactly 12h — a coin that spiked +16.9% and round-tripped looks like "+0.4%"
2. No per-signal-combo performance tracking — can't tell which signal combos make money
3. No learning loop — detection rules are static, scores don't adapt to real results
4. 50 alerts shown with no filtering — most are score 2 noise, hard to find the good ones

## Design

### 1. Multi-Checkpoint Outcome Tracking

Replace the single `outcome_12h_pct` with checkpoint measurements at 1h, 4h, 12h, 24h after the alert, plus the peak price within that window.

**New DB columns on `early_scanner_alerts`:**

```sql
outcome_1h_pct REAL,      -- price change at 1h
outcome_4h_pct REAL,      -- price change at 4h
outcome_12h_pct REAL,     -- (already exists) price change at 12h
outcome_24h_pct REAL,     -- price change at 24h
outcome_peak_pct REAL,    -- highest price change within 12h window
outcome_peak_time TEXT,   -- when the peak occurred (ISO timestamp)
```

**Evaluation logic** in `evaluate_outcomes()`:

- Runs after every scan (already does)
- For each unevaluated alert older than the checkpoint time:
  - Fetch hourly candles from alert time to now
  - Calculate price at each checkpoint (1h, 4h, 12h, 24h)
  - Track peak high across all candles in the 12h window
  - Fill in whichever checkpoints are ready (1h fills first, then 4h, etc.)
- A "win" is defined as: `outcome_peak_pct >= 3.0` (peaked 3%+ within 12h)
- Evaluation is progressive — 1h and 4h checkpoints fill before 12h is ready

### 2. Signal Combo Performance Tracking

**New DB table `signal_combo_stats`:**

```sql
CREATE TABLE IF NOT EXISTS signal_combo_stats (
    combo_key TEXT PRIMARY KEY,    -- sorted signal names joined: "accumulation+bottom_bounce"
    total_alerts INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,        -- peaked 3%+ within 12h
    avg_peak_pct REAL DEFAULT 0,
    win_rate REAL DEFAULT 0,       -- wins/total * 100
    score_adj INTEGER DEFAULT 0,   -- -1, 0, or +1
    last_updated TEXT
)
```

**Combo key generation:** Sort the signal names alphabetically, join with `+`. E.g. signals `["bottom_bounce", "squeeze"]` → key `"bottom_bounce+squeeze"`.

**Stats update:** After evaluating an alert's 12h outcome (peak available):
1. Look up or create the combo's row
2. Increment `total_alerts`, increment `wins` if peak >= 3%
3. Recalculate `avg_peak_pct` as running average
4. Recalculate `win_rate`
5. Update `score_adj`:
   - If `total_alerts >= 10` and `win_rate >= 60`: `score_adj = +1`
   - If `total_alerts >= 10` and `win_rate < 35`: `score_adj = -1`
   - Otherwise: `score_adj = 0`

### 3. Auto-Adjust Scoring

When the scanner creates an alert, the effective score is:

```python
effective_score = base_score + combo_score_adj
effective_score = max(1, min(4, effective_score))  # clamp to 1-4
```

Where `combo_score_adj` comes from the `signal_combo_stats` table.

**Impact:**
- A score-2 alert with a +1 combo boost becomes effective score 3 → gets Discord notification
- A score-3 alert with a -1 combo penalty becomes effective score 2 → saved but no Discord
- The `DISCORD_MIN_SCORE = 3` check uses `effective_score`

**Guardrails:**
- Minimum 10 evaluated alerts before any adjustment applies
- Score adjustment bounded to -1/+1 (no runaway)
- Base score still stored in DB — adjustment is applied at notification time
- Dashboard shows both base score and adjustment so it's transparent

### 4. Dashboard UI Changes

**Stats bar** (4 items → 4 items, updated):
- Alerts (24h) — unchanged
- Total — unchanged  
- **Hit Rate (3%+ peak)** — replaces "Win Rate (12h)", based on peak move not 12h snapshot
- Evaluated — unchanged

**New section: Signal Performance table** (collapsible, above alerts):

| Combo | Alerts | Win% | Avg Peak | Score Adj |
|-------|--------|------|----------|-----------|

- Sorted by win rate descending
- Color-coded: green >=60%, amber 35-60%, red <35%
- Score Adj shown as badge: green +1, gray 0, red -1
- Collapsible to save space (expanded by default)
- Footer text: "Win = peaked 3%+ within 12h. Score adjustments after 10+ samples."

**Filter tabs** on alerts list:
- **"High Confidence"** (default) — shows only alerts with effective score >= 3
- **"All"** — shows everything (current behavior)
- Count shown in tab label: "High Confidence (7)" / "All (50)"

**Alert card changes:**
- **Checkpoint timeline** replaces old `1h: / 3h:` badges:
  `1h: +10.3% > 4h: +4.7% > Peak: +16.9% > 12h: +0.4%`
  - Each checkpoint color-coded (green positive, red negative, gray pending)
  - Peak gets bold border treatment
  - Pending checkpoints show "..." in italic
- **WIN/LOSS/pending verdict badge** on right side of timeline
  - WIN (green): peak >= 3%
  - LOSS (red): 12h evaluated and peak < 3%
  - pending (gray italic): not yet evaluated
- **Score adjustment indicator**: "+1" or "-1" shown next to score dots in green/red
  - Only shown when combo has earned an adjustment

### 5. API Changes

**`GET /api/early-scanner/alerts`** response adds fields:
```json
{
  "outcome_1h_pct": 10.3,
  "outcome_4h_pct": 4.7,
  "outcome_peak_pct": 16.9,
  "outcome_peak_time": "2026-04-13T13:04:00",
  "outcome_24h_pct": null,
  "score_adj": 1,
  "effective_score": 4
}
```

**`GET /api/early-scanner/stats`** response adds:
```json
{
  "hit_rate": 63.0,
  "combo_stats": [
    {
      "combo": "accumulation+bottom_bounce",
      "combo_display": "Accumulation + Bottom Bounce",
      "total": 12,
      "wins": 10,
      "win_rate": 83.3,
      "avg_peak_pct": 8.2,
      "score_adj": 1
    }
  ]
}
```

## Files Changed

### Backend (`engine/early_scanner.py`):
1. Add new DB columns via `ALTER TABLE` migration (with `try/except` for existing DBs)
2. Rewrite `evaluate_outcomes()` for progressive multi-checkpoint evaluation
3. Add `signal_combo_stats` table creation
4. Add `_update_combo_stats()` method
5. Add `_get_combo_key()` helper
6. Modify alert scoring to apply `score_adj` from combo stats
7. Update `get_stats()` to include combo stats and hit rate
8. Update `get_recent_alerts()` to include new outcome fields and effective score

### Backend (`dashboard/api/app.py`):
1. Update `/api/early-scanner/stats` to pass through combo stats
2. Update `/api/early-scanner/alerts` to include new fields

### Frontend (`dashboard/ui/src/app/services/api.service.ts`):
1. Extend `EarlyScannerAlert` interface with new checkpoint fields
2. Extend `EarlyScannerStats` interface with `combo_stats` array and `hit_rate`
3. Add `SignalComboStats` interface

### Frontend (`dashboard/ui/src/app/components/early-scanner/early-scanner.component.ts`):
1. Add Signal Performance collapsible table section
2. Add High Confidence / All filter tabs
3. Replace 1h/3h badges with checkpoint timeline
4. Add WIN/LOSS/pending verdict badge
5. Add score adjustment indicator to score dots
6. Update stats bar (hit rate label)
