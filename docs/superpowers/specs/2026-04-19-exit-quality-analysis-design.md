# Exit-Quality Forensic Analysis — Design

**Date:** 2026-04-19
**Status:** Read-only research, no production code changes
**Deliverable:** `tests/research_exit_quality.py` (gitignored per `tests/research_*.py` pattern)

## Problem

Momentum bot round-trip taker fee on $3k notional is ~$36 (0.6% × 2 sides). False exits — selling into a dip that recovers — compound the fee drag catastrophically. Last weekend's sessions showed multiple stalled-out trades where the exit reason may or may not have matched what the market actually did next.

We want to forensically reconstruct, for each recently closed trade, whether the bot's exit was **legit** (price genuinely rolled over) or a **freak-out** (price rallied shortly after we sold). We have five independent in-position signal streams already collecting. The question is whether, combined, they would have told us the difference at exit time.

**Explicit non-goal:** we are not changing exit logic tonight. We are asking "what does the data say about recent exits" before proposing any rule changes.

## Scope

- Read-only analysis over DB snapshots pulled from Zima (live bot is authoritative)
- Operates over closed `momentum_trades` from the last 14 days
- No new tables, no engine changes, no live integration, no signal weight tuning
- Output is a markdown file in `tests/out/exit_quality_<timestamp>.md` (gitignored)

## The five signals

Each signal is a pure function `(pair: str, ts_epoch: int) → (score: float in [-1, +1], raw: dict)`.

| # | Signal | Source table | Lookback | Score formula |
|---|---|---|---|---|
| 1 | **Tape balance** | `market_tape.ws_matches` | 10 min before ts | `(buy_usd - sell_usd) / total_usd` |
| 2 | **Book imbalance** | `market_tape.l2_snapshots` | most recent snapshot ≤ ts | `(bid_usd - ask_usd) / total_usd` within ±2% of mid |
| 3 | **Micro-trend** | `candles.candles_1m` | 60 min before ts | `sign(EMA5 - EMA20) × min(1, abs(slope_per_min) / 0.001)` |
| 4 | **Wall state** | `trades.wall_decisions` | most recent row ≤ ts, same pair | +1 if `action in (anchor, shift)` **and** `wall_aware_stop >= entry_price * 1.012`; 0 if observed but below fee buffer; −1 if `action = cleared` |
| 5 | **Regime** | `trades.regime_snapshots` | most recent ≤ ts | +1 if `regime_bullish=1 and btc_4h_return > 0`; −1 if `regime_bullish=0 and btc_4h_return < 0`; else 0 |

**Composite score:** unweighted arithmetic mean of the five. Range [-1, +1]. Positive = signals agree price wants to continue up (freak-out risk if we exit); negative = signals agree price wants to roll over (legit exit).

Equal weighting is deliberate — tuning requires a labeled outcome first. Phase 2 produces that labeling.

## Execution — two phases

### Phase 1 — Case study (deep-dive, human-readable)

Pick 1-2 known-bad weekend exits from the last 14 days (bot decided + user remembers regretting).

For each selected trade, print signals at seven snapshots around exit:
- T-5min, T-1min, T (exit), T+1min, T+5min, T+30min, T+6h

Plus post-exit price path: `exit_price, p_15min, p_30min, p_1h, p_3h, p_6h, max_up_6h, max_down_6h`.

**Purpose:** verify the signal plumbing gives sensible values on known cases before scaling. If Phase 1 shows the composite is pure noise on clear-cut examples, we stop and revisit before Phase 2.

Output format: one markdown section per trade, each with a signal-over-time table and a post-exit price-path table.

### Phase 2 — Scale to last 14 days

Query all closed `momentum_trades` rows in the last 14 days. For each trade:

1. Compute composite score at exit timestamp.
2. Pull post-exit price path (15min / 30min / 1h / 3h / 6h).
3. Compute `max_up_6h` and `max_down_6h` relative to exit_price.
4. Label:
   - **freak-out**: `max_up_6h > 3%` (we sold, it ran up)
   - **legit**: `max_down_6h > 2%` (we sold, it kept dropping)
   - **ambiguous**: neither threshold met

5. Emit one row per trade to a markdown table:
   ```
   | pair | entry_ts | exit_ts | pnl_pct | composite | s1 | s2 | s3 | s4 | s5 | max_up_6h | max_down_6h | label |
   ```

Summary section at the top: counts per label, mean composite per label, per-signal correlation with label (Spearman against ordinal {freak-out=+1, ambiguous=0, legit=-1}).

## Architecture

**Single script** — `tests/research_exit_quality.py`. No new modules. If signal code grows unwieldy (>400 lines), split into `tests/exit_quality/` package but not before.

**Query engine** — DuckDB with `ATTACH` to the three SQLite databases (trades, market_tape, candles). Matches our storage decision: DuckDB reads live SQLite for analytics; live writes stay on SQLite.

**Data source** — local snapshots pulled from Zima at analysis-start. Per `feedback_fresh_data_for_sims`: script prints DB freshness at top of output (max `ts_epoch` per table, age in hours). Warn if >1h, don't block — this is offline research, user can re-pull if they care.

**Output** — `tests/out/exit_quality_<YYYY-MM-DD-HHMM>.md`. Phase 1 case study on top, Phase 2 table below.

## Signal implementation notes

**Tape balance (1):** `ws_matches.side` is `buy` / `sell` (verified in `exchange/market_tape.py:86-127`). Sum `price × size` grouped by side over the 10min window.

**Book imbalance (2):** `l2_snapshots.bids` and `.asks` are JSON arrays. Load the most recent snapshot ≤ ts for the pair. Filter levels within 2% of `mid`. Sum `price × size` per side.

**Micro-trend (3):** `candles.candles_1m` exists (~8.8M rows). Pull last 60 1m bars before ts. Compute EMA5, EMA20 on close. Slope = (EMA5_now - EMA5_60min_ago) / 60 / close_now.

**Wall state (4):** `wall_decisions` is state-transitions, not observations. For a given (pair, ts) the "current state" is the most recent row ≤ ts for that pair. The fee buffer check `entry_price * 1.012` matches the gate in `engine/momentum_engine.py:1146-1148` — a wall observed below that is "recorded but ineffective."

**Regime (5):** `regime_snapshots` is global (BTC-keyed), not per-pair. Most recent ≤ ts.

## Error handling

- Missing data for a signal at a given ts: score = `None`, not zero. Composite computed over the non-None signals with a `signals_available` count in the raw dict.
- Trade with no 6h post-exit window (too recent): exclude from Phase 2 table, log count at the top.
- Empty wall_decisions for a pair: signal 4 = 0 with `raw.reason = "no_wall_history"`.

## Testing

This is research code, not production. No unit tests. Self-test by: (a) Phase 1 output has to look sane on known cases before running Phase 2; (b) spot-check 3 random Phase 2 rows against dashboard / DB directly.

## Scope fences (explicit non-work)

- ❌ No changes to `engine/momentum_engine.py` or any exit logic
- ❌ No new logging, no new tables, no new columns
- ❌ No signal weight tuning — if the equal-weighted composite correlates poorly with labels, that's a Phase 3 question, not tonight
- ❌ No live integration — this runs offline against snapshots
- ❌ No dashboard surface — results are a markdown file

## What success looks like

Phase 1 output gives us a qualitative gut-check: "yes, on trade X, signals 1/2/3 were clearly positive at exit — we freaked out" or "no, signals were mixed noise, this composite approach doesn't work." Phase 2 gives us the quantitative label counts and per-signal correlations.

If signals correlate with labels, that's the evidence base for a Phase 3 design doc proposing a live "continue vs. rollover" gate. If they don't, we've ruled out the current data shape and know we need different streams (not more of the same).
