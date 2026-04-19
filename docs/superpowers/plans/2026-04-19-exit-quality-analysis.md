# Exit-Quality Forensic Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `tests/research_exit_quality.py` — a one-shot read-only script that labels the last 14 days of closed momentum_trades as freak-out / legit / ambiguous by combining 5 in-position signals, and outputs a markdown report.

**Architecture:** Single Python script. DuckDB is the query engine, `ATTACH`ed to two SQLite DBs (`candles.db` + `market_tape.db`) pulled as fresh snapshots from Zima. Five signal functions each have signature `(pair, ts_epoch) -> (score, raw)` and live alongside a composite/scorer, a post-exit labeler, and two emitters (case-study + table). Output is a gitignored markdown file at `tests/out/exit_quality_<timestamp>.md`.

**Tech Stack:** Python 3.14, duckdb 1.5.2, sqlite3 stdlib, pandas (only if needed for EMA — else pure numpy/stdlib). No pytest — per spec, this is one-shot research validated by output inspection, not unit tests.

**Spec reference:** [docs/superpowers/specs/2026-04-19-exit-quality-analysis-design.md](../specs/2026-04-19-exit-quality-analysis-design.md)

---

## File Structure

| Path | Responsibility |
|---|---|
| `tests/research_exit_quality.py` | Single-file analysis script. All signals, composite, labeler, emitters, main. Already gitignored via `tests/research_*.py`. |
| `tests/out/` | Output directory for markdown reports. Gitignored. Created at runtime if missing. |
| `data_snapshots/` | Local DB snapshots pulled from Zima. Gitignored (or already under `data/` which is). Created at runtime. |

If the script exceeds ~500 lines we split into `tests/exit_quality/{signals,compose,emit,__main__}.py`. Not before.

---

## Task 0: Pull fresh data from Zima

**Files:**
- Create: `data_snapshots/candles.db` (via pscp)
- Create: `data_snapshots/market_tape.db` (via pscp after user stages it)

- [ ] **Step 1: User stages `market_tape.db` on Zima host**

Because `market_tape.db` lives only in the container overlay, the user must copy it to the host bind-mount first. This is a one-time manual step each time we pull.

Run on Zima (user does this — not the agent):
```bash
docker cp cryptobot:/app/src/data/market_tape.db /DATA/AppData/cryptobot/data/market_tape_snapshot.db
```

Expected: file appears at `/DATA/AppData/cryptobot/data/market_tape_snapshot.db`, ~1.5-1.7 GB.

- [ ] **Step 2: Create local snapshot dir**

```bash
mkdir -p data_snapshots
```

- [ ] **Step 3: pscp candles.db from Zima to local**

Run from the cryptobot repo root (git bash):
```bash
pscp -pw 'Butcher@1990!' -scp namanuel@192.168.1.185:/DATA/AppData/cryptobot/data/candles.db data_snapshots/candles.db
```

Expected: ~1.38 GB file. Takes ~30-60s on LAN. Redo if mtime stale.

- [ ] **Step 4: pscp market_tape.db from Zima to local**

```bash
pscp -pw 'Butcher@1990!' -scp namanuel@192.168.1.185:/DATA/AppData/cryptobot/data/market_tape_snapshot.db data_snapshots/market_tape.db
```

Expected: ~1.5-1.7 GB file.

- [ ] **Step 5: Verify freshness with a sqlite probe**

```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe -c "
import sqlite3
for name, q in [
    ('candles.db wall_decisions', 'SELECT MAX(timestamp), COUNT(*) FROM wall_decisions'),
    ('candles.db regime_snapshots', 'SELECT MAX(timestamp), COUNT(*) FROM regime_snapshots'),
    ('candles.db candles 1m',       \"SELECT MAX(timestamp), COUNT(*) FROM candles WHERE granularity='ONE_MINUTE'\"),
    ('candles.db momentum_trades',  \"SELECT MAX(timestamp), COUNT(*) FROM momentum_trades WHERE side='sell' AND pnl_pct IS NOT NULL\"),
]:
    db = 'data_snapshots/candles.db'
    c = sqlite3.connect(db)
    print(name, c.execute(q).fetchone())
for q in ['SELECT MAX(ts_epoch), COUNT(*) FROM ws_matches', 'SELECT MAX(ts_epoch), COUNT(*) FROM l2_snapshots']:
    c = sqlite3.connect('data_snapshots/market_tape.db')
    print(q, c.execute(q).fetchone())
"
```

Expected: max timestamps within last 1-2 hours (candles.db tables), last 1-24h (market_tape tables — market_tape snapshot was staged manually so may be slightly older).

**No commit — `data_snapshots/` is gitignored.**

---

## Task 1: Script skeleton + DuckDB ATTACH + freshness header

**Files:**
- Create: `tests/research_exit_quality.py`

- [ ] **Step 1: Write the script skeleton**

Create `tests/research_exit_quality.py` with:

```python
"""
Exit-quality forensic analysis.

Read-only analysis over fresh DB snapshots in data_snapshots/. For each closed
momentum_trade in the last 14 days, compute 5 in-position signals at exit time,
label post-exit price action, and emit a markdown report.

Spec: docs/superpowers/specs/2026-04-19-exit-quality-analysis-design.md
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "data_snapshots"
OUT_DIR = REPO_ROOT / "tests" / "out"
CANDLES_DB = SNAPSHOT_DIR / "candles.db"
MARKET_TAPE_DB = SNAPSHOT_DIR / "market_tape.db"

FEE_BUFFER_PCT = 0.012  # matches engine/momentum_engine.py:1146 wall-aware min_profit_buffer_pct
LOOKBACK_DAYS = 14
FREAK_OUT_UP_PCT = 3.0   # post-exit rise threshold to label freak-out
LEGIT_DOWN_PCT = 2.0     # post-exit drop threshold to label legit


def connect() -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection with both SQLite DBs attached read-only."""
    if not CANDLES_DB.exists():
        sys.exit(f"ERROR: {CANDLES_DB} missing. Run Task 0 to pull snapshots.")
    if not MARKET_TAPE_DB.exists():
        sys.exit(f"ERROR: {MARKET_TAPE_DB} missing. Run Task 0 to pull snapshots.")
    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{CANDLES_DB}' AS candles_db (TYPE SQLITE, READ_ONLY)")
    con.execute(f"ATTACH '{MARKET_TAPE_DB}' AS tape_db (TYPE SQLITE, READ_ONLY)")
    return con


def freshness_report(con: duckdb.DuckDBPyConnection) -> str:
    """Return a markdown block describing snapshot freshness."""
    rows = []
    for label, sql in [
        ("wall_decisions", "SELECT MAX(timestamp) FROM candles_db.wall_decisions"),
        ("regime_snapshots", "SELECT MAX(timestamp) FROM candles_db.regime_snapshots"),
        ("candles 1m", "SELECT MAX(timestamp) FROM candles_db.candles WHERE granularity='ONE_MINUTE'"),
        ("momentum_trades sells", "SELECT MAX(timestamp) FROM candles_db.momentum_trades WHERE side='sell' AND pnl_pct IS NOT NULL"),
        ("ws_matches", "SELECT MAX(ts) FROM tape_db.ws_matches"),
        ("l2_snapshots", "SELECT MAX(ts) FROM tape_db.l2_snapshots"),
    ]:
        latest = con.execute(sql).fetchone()[0]
        rows.append(f"| {label} | {latest} |")
    return "## Snapshot freshness\n\n| source | latest row |\n|---|---|\n" + "\n".join(rows) + "\n"


def main() -> None:
    con = connect()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    out_path = OUT_DIR / f"exit_quality_{stamp}.md"

    lines = [f"# Exit-Quality Analysis — {stamp}\n", freshness_report(con)]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the skeleton and verify it writes a report with freshness**

```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe tests/research_exit_quality.py
```

Expected output:
```
Wrote .../tests/out/exit_quality_2026-04-19-HHMM.md
```

Then inspect the file:
```bash
cat tests/out/exit_quality_*.md
```

Expected: a freshness table with 6 source rows, all with non-null recent timestamps.

- [ ] **Step 3: Commit the skeleton**

```bash
git add tests/research_exit_quality.py
git commit -m "feat(research): scaffold exit-quality forensic script"
```

Note: `tests/research_*.py` is gitignored. Use `git add -f` if git refuses:
```bash
git add -f tests/research_exit_quality.py
git commit -m "feat(research): scaffold exit-quality forensic script"
```

---

## Task 2: Signal 1 — Tape balance (ws_matches)

**Files:**
- Modify: `tests/research_exit_quality.py` — add `signal_tape_balance()` function + CLI flag to print signal-at-timestamp

- [ ] **Step 1: Add the signal function**

Insert after the `freshness_report` function in `tests/research_exit_quality.py`:

```python
@dataclass
class SignalResult:
    score: Optional[float]   # in [-1, +1], or None if no data
    raw: dict


def signal_tape_balance(con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float) -> SignalResult:
    """Signal 1: tape-order-flow balance over the 10 min before ts_epoch.

    (buy_usd - sell_usd) / total_usd using ws_matches.side uppercase BUY/SELL.
    Score in [-1, +1]. None if no trades in window.
    """
    lookback_s = 600.0
    row = con.execute("""
        SELECT
            SUM(CASE WHEN UPPER(side)='BUY'  THEN price*size ELSE 0 END) AS buy_usd,
            SUM(CASE WHEN UPPER(side)='SELL' THEN price*size ELSE 0 END) AS sell_usd,
            COUNT(*) AS n
        FROM tape_db.ws_matches
        WHERE pair = ?
          AND ts_epoch BETWEEN ? AND ?
    """, [pair, ts_epoch - lookback_s, ts_epoch]).fetchone()
    buy_usd, sell_usd, n = (row[0] or 0.0), (row[1] or 0.0), row[2]
    total = buy_usd + sell_usd
    if n == 0 or total <= 0:
        return SignalResult(None, {"n_trades": n, "reason": "no_trades_in_window"})
    score = (buy_usd - sell_usd) / total
    return SignalResult(score, {"n_trades": n, "buy_usd": buy_usd, "sell_usd": sell_usd})
```

- [ ] **Step 2: Add a CLI probe mode so we can smoke-test any signal**

Replace the `main()` function with:

```python
def _probe(con: duckdb.DuckDBPyConnection, pair: str, ts_iso: str) -> None:
    """Print every signal's value at (pair, ts_iso). For smoke-testing."""
    ts_epoch = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).timestamp()
    print(f"probe {pair} @ {ts_iso} (epoch {ts_epoch:.0f})")
    for name, fn in [
        ("tape_balance", signal_tape_balance),
        # others added in later tasks
    ]:
        r = fn(con, pair, ts_epoch)
        print(f"  {name}: score={r.score} raw={r.raw}")


def main() -> None:
    con = connect()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) >= 3 and sys.argv[1] == "probe":
        # usage: python research_exit_quality.py probe <PAIR> <ISO_TS>
        _probe(con, sys.argv[2], sys.argv[3])
        return
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    out_path = OUT_DIR / f"exit_quality_{stamp}.md"
    lines = [f"# Exit-Quality Analysis — {stamp}\n", freshness_report(con)]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")
```

- [ ] **Step 3: Smoke-test against a known closed trade**

AXL-USD exit was `2026-04-17T02:54:56.556199` with peak_pnl +28.84%. Probe tape balance at exit:
```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe tests/research_exit_quality.py probe AXL-USD 2026-04-17T02:54:56.556199
```

Expected: a `tape_balance:` line with a score in `[-1, +1]` and `raw` showing non-zero `n_trades`, `buy_usd`, `sell_usd`. If score is near 0, that's fine — it means the tape was balanced at exit. If `n_trades=0`, investigate: was AXL subscribed in ws_matches at that time? Check with:
```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe -c "
import sqlite3
c = sqlite3.connect('data_snapshots/market_tape.db')
print(c.execute(\"SELECT COUNT(*) FROM ws_matches WHERE pair='AXL-USD'\").fetchone())
print(c.execute(\"SELECT MIN(ts), MAX(ts) FROM ws_matches WHERE pair='AXL-USD'\").fetchone())
"
```

If AXL has zero ws_matches rows for that date, that's a coverage gap to note in the final report — not a signal bug.

- [ ] **Step 4: Commit**

```bash
git add -f tests/research_exit_quality.py
git commit -m "feat(research): add signal 1 tape-balance + probe CLI"
```

---

## Task 3: Signal 2 — Book imbalance (l2_snapshots)

**Files:**
- Modify: `tests/research_exit_quality.py` — add `signal_book_imbalance()`

- [ ] **Step 1: Add the signal function**

Insert after `signal_tape_balance`:

```python
def signal_book_imbalance(con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float) -> SignalResult:
    """Signal 2: nearest L2 snapshot, bid-vs-ask USD within ±2% of mid.

    bids/asks are JSON '[[price,size],...]' strings. Score = (bid_usd - ask_usd) / total.
    None if no snapshot within 5 min before ts_epoch.
    """
    max_age_s = 300.0
    row = con.execute("""
        SELECT ts_epoch, mid, bids, asks
        FROM tape_db.l2_snapshots
        WHERE pair = ?
          AND ts_epoch BETWEEN ? AND ?
        ORDER BY ts_epoch DESC
        LIMIT 1
    """, [pair, ts_epoch - max_age_s, ts_epoch]).fetchone()
    if row is None:
        return SignalResult(None, {"reason": "no_snapshot_within_5min"})
    snap_ts, mid, bids_json, asks_json = row
    if mid is None or mid <= 0:
        return SignalResult(None, {"reason": "bad_mid", "ts_epoch": snap_ts})
    band_lo = mid * 0.98
    band_hi = mid * 1.02
    bids = json.loads(bids_json)
    asks = json.loads(asks_json)
    bid_usd = sum(p * s for p, s in bids if band_lo <= p <= mid)
    ask_usd = sum(p * s for p, s in asks if mid <= p <= band_hi)
    total = bid_usd + ask_usd
    if total <= 0:
        return SignalResult(None, {"reason": "no_liquidity_in_band", "mid": mid})
    score = (bid_usd - ask_usd) / total
    snap_age = ts_epoch - snap_ts
    return SignalResult(score, {"bid_usd": bid_usd, "ask_usd": ask_usd, "mid": mid, "snap_age_s": snap_age})
```

- [ ] **Step 2: Wire into probe mode**

In the `_probe` function, extend the signals list:
```python
    for name, fn in [
        ("tape_balance", signal_tape_balance),
        ("book_imbalance", signal_book_imbalance),
    ]:
```

- [ ] **Step 3: Smoke-test**

```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe tests/research_exit_quality.py probe AXL-USD 2026-04-17T02:54:56.556199
```

Expected: a `book_imbalance:` line. Reasonable scores in [-0.9, +0.9] for most moments. Check `raw.snap_age_s` — should be small (seconds to a couple minutes) if AXL was in the L2 subscription set at that time. If `raw.reason='no_snapshot_within_5min'`, that's a coverage gap.

- [ ] **Step 4: Commit**

```bash
git add -f tests/research_exit_quality.py
git commit -m "feat(research): add signal 2 book-imbalance"
```

---

## Task 4: Signal 3 — Micro-trend (1m candles EMA slope)

**Files:**
- Modify: `tests/research_exit_quality.py` — add `signal_micro_trend()`

- [ ] **Step 1: Add the signal function**

Insert after `signal_book_imbalance`:

```python
def _ema(values: list[float], period: int) -> list[float]:
    """Simple EMA. Returns list same length as input; first (period-1) entries use SMA seed."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    out = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(out[-1] + k * (v - out[-1]))
    # pad front with Nones so index aligns with input
    return [None] * (period - 1) + out


def signal_micro_trend(con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float) -> SignalResult:
    """Signal 3: 1m EMA5 vs EMA20 over the last 60 minutes before ts_epoch.

    Score = sign(EMA5 - EMA20) * min(1, abs(slope_per_min)/0.001),
    where slope_per_min is (EMA5_now - EMA5_60min_ago) / 60 / close_now.
    None if fewer than 25 1m candles available (need enough for EMA20 + slope window).
    """
    ts_iso = dt.datetime.fromtimestamp(ts_epoch).isoformat()
    rows = con.execute("""
        SELECT timestamp, close
        FROM candles_db.candles
        WHERE pair = ?
          AND granularity = 'ONE_MINUTE'
          AND timestamp <= ?
        ORDER BY timestamp DESC
        LIMIT 60
    """, [pair, ts_iso]).fetchall()
    if len(rows) < 25:
        return SignalResult(None, {"reason": "insufficient_candles", "n": len(rows)})
    # reverse to chronological
    rows = rows[::-1]
    closes = [r[1] for r in rows]
    ema5 = _ema(closes, 5)
    ema20 = _ema(closes, 20)
    if ema5[-1] is None or ema20[-1] is None:
        return SignalResult(None, {"reason": "ema_not_computed"})
    ema5_now, ema20_now = ema5[-1], ema20[-1]
    ema5_ago = ema5[max(0, len(ema5) - 60)] if len(ema5) >= 60 and ema5[len(ema5)-60] is not None else ema5[20]
    close_now = closes[-1]
    if close_now <= 0:
        return SignalResult(None, {"reason": "bad_close"})
    window_min = max(1, len(ema5) - 1 - max(0, len(ema5) - 60))
    slope_per_min = (ema5_now - ema5_ago) / window_min / close_now
    direction = 1.0 if ema5_now > ema20_now else -1.0 if ema5_now < ema20_now else 0.0
    magnitude = min(1.0, abs(slope_per_min) / 0.001)
    score = direction * magnitude
    return SignalResult(score, {
        "ema5": ema5_now, "ema20": ema20_now, "close": close_now,
        "slope_per_min": slope_per_min, "n_candles": len(rows),
    })
```

- [ ] **Step 2: Wire into probe mode**

Add `("micro_trend", signal_micro_trend),` to the `_probe` signals list.

- [ ] **Step 3: Smoke-test**

```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe tests/research_exit_quality.py probe AXL-USD 2026-04-17T02:54:56.556199
```

Expected: a `micro_trend:` line. For AXL at exit (after a +28% run that reversed), we'd expect the score to be slightly positive (ema5 still above ema20 at exit) or negative (if the reversal was already in progress). `raw.n_candles` should be 60.

Sanity: run probe for the same pair 30 min BEFORE peak, 30 min AFTER exit, and verify the sign changes direction. Note values in a scratch comment.

- [ ] **Step 4: Commit**

```bash
git add -f tests/research_exit_quality.py
git commit -m "feat(research): add signal 3 micro-trend"
```

---

## Task 5: Signal 4 — Wall state (wall_decisions)

**Files:**
- Modify: `tests/research_exit_quality.py` — add `signal_wall_state()`

- [ ] **Step 1: Add the signal function**

Insert after `signal_micro_trend`:

```python
def signal_wall_state(
    con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float,
    entry_price: float,
) -> SignalResult:
    """Signal 4: most recent wall_decisions row for this pair before ts_epoch.

    +1 if action in ('anchor','shift') AND wall_aware_stop >= entry_price * 1.012 (fee buffer).
     0 if observed but below fee buffer (can't actually protect profit).
    -1 if action = 'cleared' (wall evaporated).
    None if no rows for this pair ever.
    """
    ts_iso = dt.datetime.fromtimestamp(ts_epoch).isoformat()
    row = con.execute("""
        SELECT timestamp, action, wall_aware_stop, wall_price, wall_usd, wall_age_ms
        FROM candles_db.wall_decisions
        WHERE pair = ?
          AND timestamp <= ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, [pair, ts_iso]).fetchone()
    if row is None:
        return SignalResult(None, {"reason": "no_wall_history"})
    ts, action, wall_stop, wall_px, wall_usd, wall_age = row
    buffer_price = entry_price * (1 + FEE_BUFFER_PCT)
    if action == "cleared":
        return SignalResult(-1.0, {"action": action, "ts": ts, "wall_stop": wall_stop})
    if action in ("anchor", "shift"):
        if wall_stop is not None and wall_stop >= buffer_price:
            return SignalResult(1.0, {"action": action, "ts": ts, "wall_stop": wall_stop,
                                      "buffer_price": buffer_price, "wall_usd": wall_usd,
                                      "wall_age_ms": wall_age})
        return SignalResult(0.0, {"action": action, "ts": ts, "wall_stop": wall_stop,
                                  "buffer_price": buffer_price, "reason": "below_fee_buffer"})
    # toggle or other — treat as neutral
    return SignalResult(0.0, {"action": action, "ts": ts, "reason": "other_action"})
```

- [ ] **Step 2: Probe mode needs entry_price for wall signal — extend probe**

Update `_probe` to accept an optional entry price. Replace `_probe` with:

```python
def _probe(con: duckdb.DuckDBPyConnection, pair: str, ts_iso: str, entry_price: float = 0.0) -> None:
    ts_epoch = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).timestamp()
    print(f"probe {pair} @ {ts_iso} entry={entry_price} (epoch {ts_epoch:.0f})")
    print(f"  tape_balance:   {signal_tape_balance(con, pair, ts_epoch)}")
    print(f"  book_imbalance: {signal_book_imbalance(con, pair, ts_epoch)}")
    print(f"  micro_trend:    {signal_micro_trend(con, pair, ts_epoch)}")
    print(f"  wall_state:     {signal_wall_state(con, pair, ts_epoch, entry_price)}")
```

And update the CLI dispatch in `main()`:
```python
    if len(sys.argv) >= 4 and sys.argv[1] == "probe":
        entry = float(sys.argv[4]) if len(sys.argv) >= 5 else 0.0
        _probe(con, sys.argv[2], sys.argv[3], entry)
        return
```

- [ ] **Step 3: Smoke-test**

AXL entry was at $0.0568 approximately (derive: exit $0.0631 with +6.41% pnl → entry ≈ 0.0631 / 1.0641 ≈ 0.0593). Use the actual entry price from the sell row:

```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe -c "
import sqlite3
c = sqlite3.connect('data_snapshots/candles.db')
print(c.execute(\"SELECT entry_price, exit_price, pnl_pct FROM momentum_trades WHERE id=59\").fetchone())
"
```

Use the printed entry_price:
```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe tests/research_exit_quality.py probe AXL-USD 2026-04-17T02:54:56.556199 <ENTRY_PRICE>
```

Expected: `wall_state:` line with one of: +1.0 (wall anchored above buffer), 0.0 (wall observed but below buffer), -1.0 (wall cleared), or None (no wall ever for AXL).

- [ ] **Step 4: Commit**

```bash
git add -f tests/research_exit_quality.py
git commit -m "feat(research): add signal 4 wall-state"
```

---

## Task 6: Signal 5 — Regime (regime_snapshots)

**Files:**
- Modify: `tests/research_exit_quality.py` — add `signal_regime()`

- [ ] **Step 1: Add the signal function**

Insert after `signal_wall_state`:

```python
def signal_regime(con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float) -> SignalResult:
    """Signal 5: BTC-keyed regime snapshot (most recent ≤ ts_epoch).

    +1 if regime_bullish=1 AND btc_4h_return > 0.
    -1 if regime_bullish=0 AND btc_4h_return < 0.
     0 otherwise (mixed signals).
    None if no snapshot found.
    """
    ts_iso = dt.datetime.fromtimestamp(ts_epoch).isoformat()
    row = con.execute("""
        SELECT timestamp, regime_bullish, btc_4h_return, btc_24h_return
        FROM candles_db.regime_snapshots
        WHERE timestamp <= ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, [ts_iso]).fetchone()
    if row is None:
        return SignalResult(None, {"reason": "no_regime_snapshot"})
    ts, bullish, r4h, r24h = row
    if bullish == 1 and (r4h or 0) > 0:
        score = 1.0
    elif bullish == 0 and (r4h or 0) < 0:
        score = -1.0
    else:
        score = 0.0
    return SignalResult(score, {"ts": ts, "bullish": bullish, "btc_4h": r4h, "btc_24h": r24h})
```

- [ ] **Step 2: Wire into probe**

Add to `_probe`:
```python
    print(f"  regime:         {signal_regime(con, pair, ts_epoch)}")
```

- [ ] **Step 3: Smoke-test**

```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe tests/research_exit_quality.py probe AXL-USD 2026-04-17T02:54:56.556199 <ENTRY>
```

Expected: `regime:` line with score ∈ {-1, 0, +1} and raw showing actual BTC returns. For Apr 17 we saw `regime_bullish=1, btc_4h_return=0.309, btc_24h_return=3.42` in local sample — so expect +1 on AXL exit.

- [ ] **Step 4: Commit**

```bash
git add -f tests/research_exit_quality.py
git commit -m "feat(research): add signal 5 regime"
```

---

## Task 7: Composite score + post-exit labeler

**Files:**
- Modify: `tests/research_exit_quality.py` — add `compute_composite()`, `post_exit_path()`, `label_trade()`

- [ ] **Step 1: Add the composite + path + labeler**

Insert after `signal_regime`:

```python
@dataclass
class CompositeResult:
    composite: Optional[float]  # mean of non-None signal scores, or None if all None
    signals: dict               # name -> SignalResult
    n_available: int


def compute_composite(
    con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float, entry_price: float,
) -> CompositeResult:
    """Compute all 5 signals and return equal-weighted mean over available ones."""
    sigs = {
        "tape_balance":   signal_tape_balance(con, pair, ts_epoch),
        "book_imbalance": signal_book_imbalance(con, pair, ts_epoch),
        "micro_trend":    signal_micro_trend(con, pair, ts_epoch),
        "wall_state":     signal_wall_state(con, pair, ts_epoch, entry_price),
        "regime":         signal_regime(con, pair, ts_epoch),
    }
    scores = [s.score for s in sigs.values() if s.score is not None]
    composite = sum(scores) / len(scores) if scores else None
    return CompositeResult(composite, sigs, len(scores))


def post_exit_path(
    con: duckdb.DuckDBPyConnection, pair: str, exit_ts_epoch: float, exit_price: float,
) -> dict:
    """Pull 1m closes for the 6 hours AFTER exit; return key offsets + max up/down."""
    ts_iso_start = dt.datetime.fromtimestamp(exit_ts_epoch).isoformat()
    ts_iso_end   = dt.datetime.fromtimestamp(exit_ts_epoch + 6 * 3600).isoformat()
    rows = con.execute("""
        SELECT timestamp, close, high, low
        FROM candles_db.candles
        WHERE pair = ?
          AND granularity = 'ONE_MINUTE'
          AND timestamp BETWEEN ? AND ?
        ORDER BY timestamp
    """, [pair, ts_iso_start, ts_iso_end]).fetchall()
    if not rows:
        return {"n": 0, "reason": "no_post_exit_candles"}
    highs = [r[2] for r in rows]
    lows  = [r[3] for r in rows]
    def pct(p): return (p - exit_price) / exit_price * 100.0
    def at_offset(offset_min: int) -> Optional[float]:
        target = exit_ts_epoch + offset_min * 60
        target_iso = dt.datetime.fromtimestamp(target).isoformat()
        for ts, close, *_ in rows:
            if ts >= target_iso:
                return close
        return None
    return {
        "n": len(rows),
        "p_15min":  at_offset(15),
        "p_30min":  at_offset(30),
        "p_1h":     at_offset(60),
        "p_3h":     at_offset(180),
        "p_6h":     at_offset(360),
        "max_up_pct":   pct(max(highs)),
        "max_down_pct": pct(min(lows)),
    }


def label_trade(path: dict) -> str:
    """Label a trade as freak-out / legit / ambiguous per post-exit price action."""
    if path.get("n", 0) == 0:
        return "no_data"
    up = path["max_up_pct"]
    down = path["max_down_pct"]
    if up > FREAK_OUT_UP_PCT:
        return "freak-out"
    if down < -LEGIT_DOWN_PCT:
        return "legit"
    return "ambiguous"
```

- [ ] **Step 2: Add composite mode to CLI**

Replace the `main()` dispatch to add a `composite` command:

```python
def main() -> None:
    con = connect()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) >= 2 and sys.argv[1] == "probe":
        entry = float(sys.argv[4]) if len(sys.argv) >= 5 else 0.0
        _probe(con, sys.argv[2], sys.argv[3], entry)
        return

    if len(sys.argv) >= 6 and sys.argv[1] == "composite":
        # usage: composite <PAIR> <EXIT_ISO> <ENTRY_PRICE> <EXIT_PRICE>
        pair = sys.argv[2]
        ts_iso = sys.argv[3]
        entry_px = float(sys.argv[4])
        exit_px = float(sys.argv[5])
        ts_epoch = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).timestamp()
        c = compute_composite(con, pair, ts_epoch, entry_px)
        p = post_exit_path(con, pair, ts_epoch, exit_px)
        print(f"composite={c.composite}  available={c.n_available}/5")
        for name, s in c.signals.items():
            print(f"  {name}: {s.score}")
        print(f"post-exit: {p}")
        print(f"label: {label_trade(p)}")
        return

    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    out_path = OUT_DIR / f"exit_quality_{stamp}.md"
    lines = [f"# Exit-Quality Analysis — {stamp}\n", freshness_report(con)]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")
```

- [ ] **Step 3: Smoke-test end-to-end on AXL**

Pull AXL's exit row to get exact entry/exit prices:
```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe -c "
import sqlite3
c = sqlite3.connect('data_snapshots/candles.db')
print(c.execute(\"SELECT timestamp, entry_price, exit_price FROM momentum_trades WHERE id=59\").fetchone())
"
```

Then:
```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe tests/research_exit_quality.py composite AXL-USD 2026-04-17T02:54:56.556199 <ENTRY_PRICE> <EXIT_PRICE>
```

Expected:
- `composite=<float>  available=<n>/5` (n should be 4 or 5 if all data is present)
- Each signal's score printed
- `post-exit:` with price offsets and max_up/down
- `label: freak-out | legit | ambiguous | no_data`

AXL gave back 22% from peak; the post-exit 6h might show continued dump (label = legit) or a rebound (label = freak-out). Whichever it is, the composite value at exit tells us whether signals agreed.

- [ ] **Step 4: Commit**

```bash
git add -f tests/research_exit_quality.py
git commit -m "feat(research): add composite scorer + post-exit labeler"
```

---

## Task 8: Phase 1 — Case study emitter

**Files:**
- Modify: `tests/research_exit_quality.py` — add `emit_case_study()`, add `phase1` CLI mode

- [ ] **Step 1: Add case-study emitter**

Insert after `label_trade`:

```python
def emit_case_study(
    con: duckdb.DuckDBPyConnection,
    trade_id: int,
) -> str:
    """Emit a markdown block for one trade: signals at 7 offsets + post-exit path."""
    t = con.execute("""
        SELECT id, timestamp, pair, entry_price, exit_price, pnl_pct, hold_hours,
               peak_pnl_pct, reason
        FROM candles_db.momentum_trades
        WHERE id = ? AND side = 'sell'
    """, [trade_id]).fetchone()
    if t is None:
        return f"## Trade {trade_id}\n\n*(not found)*\n"
    (tid, ts_iso, pair, entry_px, exit_px, pnl, hold_h, peak_pnl, reason) = t
    exit_epoch = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).timestamp()

    offsets_min = [-5, -1, 0, 1, 5, 30, 360]
    lines = [
        f"## Case: trade #{tid} — {pair}",
        f"- entry: ${entry_px}  exit: ${exit_px}  pnl: {pnl:+.2f}%  peak_pnl: {peak_pnl:+.2f}%  hold: {hold_h}h",
        f"- reason: `{reason}`",
        f"- exit_ts: `{ts_iso}`",
        "",
        "### Signals at key offsets",
        "| offset | composite | tape | book | micro | wall | regime |",
        "|---|---|---|---|---|---|---|",
    ]
    for off in offsets_min:
        probe_epoch = exit_epoch + off * 60
        c = compute_composite(con, pair, probe_epoch, entry_px)
        def fmt(s):
            if s.score is None:
                return "–"
            return f"{s.score:+.2f}"
        comp = f"{c.composite:+.2f}" if c.composite is not None else "–"
        lines.append(
            f"| T{off:+d}m | {comp} | "
            f"{fmt(c.signals['tape_balance'])} | "
            f"{fmt(c.signals['book_imbalance'])} | "
            f"{fmt(c.signals['micro_trend'])} | "
            f"{fmt(c.signals['wall_state'])} | "
            f"{fmt(c.signals['regime'])} |"
        )

    p = post_exit_path(con, pair, exit_epoch, exit_px)
    up_s = f"{p['max_up_pct']:+.2f}%" if p.get("n", 0) > 0 else "–"
    dn_s = f"{p['max_down_pct']:+.2f}%" if p.get("n", 0) > 0 else "–"
    lines += [
        "",
        "### Post-exit price path",
        f"- max_up (6h): {up_s} · max_down (6h): {dn_s}",
        f"- +15m: {p.get('p_15min')}  +30m: {p.get('p_30min')}  +1h: {p.get('p_1h')}  +3h: {p.get('p_3h')}  +6h: {p.get('p_6h')}",
        f"- **label: `{label_trade(p)}`**",
        "",
    ]
    return "\n".join(lines)
```

- [ ] **Step 2: Wire phase1 CLI mode**

Add to `main()` dispatch, before the default report block:
```python
    if len(sys.argv) >= 2 and sys.argv[1] == "phase1":
        # usage: phase1 <id1> [<id2> ...]
        ids = [int(x) for x in sys.argv[2:]]
        stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
        out_path = OUT_DIR / f"exit_quality_phase1_{stamp}.md"
        blocks = [f"# Phase 1 Case Study — {stamp}\n", freshness_report(con)]
        for tid in ids:
            blocks.append(emit_case_study(con, tid))
        out_path.write_text("\n".join(blocks), encoding="utf-8")
        print(f"Wrote {out_path}")
        return
```

- [ ] **Step 3: Run Phase 1 on AXL (id=59) + AVNT (id=69)**

```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe tests/research_exit_quality.py phase1 59 69
```

Expected: file `tests/out/exit_quality_phase1_<stamp>.md` with two case-study sections, each showing signal evolution over 7 timestamps and the post-exit path.

Inspect the output and ask: do the signals make narrative sense at T=0 (exit)?
- If AXL label is "freak-out" and all signals are +ve at T=0 → the composite DID detect it, engine was wrong to exit.
- If AXL label is "legit" and signals are -ve at T=0 → engine was right, composite agrees.
- If signals are mixed/contradictory → the composite approach needs more thought.

Write a 2-3 sentence observation at the top of the markdown file by hand after inspection (or re-run if signal code has bugs).

- [ ] **Step 4: Commit**

```bash
git add -f tests/research_exit_quality.py
git commit -m "feat(research): phase 1 case-study emitter"
```

---

## Task 9: Phase 2 — Scale to all 14-day closed trades

**Files:**
- Modify: `tests/research_exit_quality.py` — add `emit_phase2_table()`, `phase2` CLI mode

- [ ] **Step 1: Add phase 2 emitter**

Insert after `emit_case_study`:

```python
def emit_phase2_table(con: duckdb.DuckDBPyConnection, lookback_days: int = LOOKBACK_DAYS) -> str:
    """Emit a markdown table: one row per closed trade in lookback window."""
    cutoff_iso = (dt.datetime.now() - dt.timedelta(days=lookback_days)).isoformat()
    trades = con.execute("""
        SELECT id, timestamp, pair, entry_price, exit_price, pnl_pct, peak_pnl_pct, hold_hours, reason
        FROM candles_db.momentum_trades
        WHERE side = 'sell'
          AND pnl_pct IS NOT NULL
          AND timestamp >= ?
        ORDER BY timestamp DESC
    """, [cutoff_iso]).fetchall()

    header = [
        "## Phase 2 — all closed trades (last 14d)",
        "",
        "| id | exit_ts | pair | pnl% | peak% | comp | tape | book | micro | wall | regime | max_up | max_down | label |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    rows = []
    label_counts = {"freak-out": 0, "legit": 0, "ambiguous": 0, "no_data": 0}
    per_signal_by_label: dict[str, dict[str, list[float]]] = {}
    for t in trades:
        tid, ts_iso, pair, entry_px, exit_px, pnl, peak_pnl, hold_h, _reason = t
        exit_epoch = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).timestamp()
        c = compute_composite(con, pair, exit_epoch, entry_px)
        p = post_exit_path(con, pair, exit_epoch, exit_px)
        lbl = label_trade(p)
        label_counts[lbl] = label_counts.get(lbl, 0) + 1
        per_signal_by_label.setdefault(lbl, {"tape":[], "book":[], "micro":[], "wall":[], "regime":[]})
        for short, full in [("tape","tape_balance"),("book","book_imbalance"),
                             ("micro","micro_trend"),("wall","wall_state"),("regime","regime")]:
            s = c.signals[full].score
            if s is not None:
                per_signal_by_label[lbl][short].append(s)
        def fmt(s): return f"{s.score:+.2f}" if s.score is not None else "–"
        comp_s = f"{c.composite:+.2f}" if c.composite is not None else "–"
        up_s = f"{p['max_up_pct']:+.2f}" if p.get("n", 0) > 0 else "–"
        dn_s = f"{p['max_down_pct']:+.2f}" if p.get("n", 0) > 0 else "–"
        rows.append(
            f"| {tid} | {ts_iso[:16]} | {pair} | {pnl:+.2f} | {peak_pnl:+.2f} | "
            f"{comp_s} | "
            f"{fmt(c.signals['tape_balance'])} | {fmt(c.signals['book_imbalance'])} | "
            f"{fmt(c.signals['micro_trend'])} | {fmt(c.signals['wall_state'])} | "
            f"{fmt(c.signals['regime'])} | "
            f"{up_s} | {dn_s} | "
            f"**{lbl}** |"
        )

    summary = [
        "",
        "### Summary",
        "",
        f"- n_trades analyzed: {len(trades)}",
        f"- label counts: {label_counts}",
        "",
        "### Mean signal scores by label",
        "",
        "| label | n | tape | book | micro | wall | regime |",
        "|---|---|---|---|---|---|---|",
    ]
    for lbl, buckets in per_signal_by_label.items():
        def mean(xs): return f"{sum(xs)/len(xs):+.2f}" if xs else "–"
        n = label_counts.get(lbl, 0)
        summary.append(
            f"| {lbl} | {n} | {mean(buckets['tape'])} | {mean(buckets['book'])} | "
            f"{mean(buckets['micro'])} | {mean(buckets['wall'])} | {mean(buckets['regime'])} |"
        )

    return "\n".join(header + rows + summary) + "\n"
```

- [ ] **Step 2: Wire phase2 CLI mode**

Add to `main()`:
```python
    if len(sys.argv) >= 2 and sys.argv[1] == "phase2":
        stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
        out_path = OUT_DIR / f"exit_quality_phase2_{stamp}.md"
        blocks = [f"# Phase 2 — last {LOOKBACK_DAYS}d closed trades — {stamp}\n",
                  freshness_report(con),
                  emit_phase2_table(con)]
        out_path.write_text("\n".join(blocks), encoding="utf-8")
        print(f"Wrote {out_path}")
        return
```

- [ ] **Step 3: Run Phase 2**

```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe tests/research_exit_quality.py phase2
```

Expected: `tests/out/exit_quality_phase2_<stamp>.md` with:
- Freshness block
- Table of 8 trades with all signals + labels
- Summary with label counts
- Mean signal scores per label (shows which signal differentiates freak-outs from legit exits best)

- [ ] **Step 4: Spot-check 3 random rows**

Pick 3 trade IDs from the output table. For each, manually verify the numbers against the source DB:
```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe -c "
import sqlite3
c = sqlite3.connect('data_snapshots/candles.db')
for tid in [<id1>, <id2>, <id3>]:
    r = c.execute('SELECT id,pair,timestamp,entry_price,exit_price,pnl_pct FROM momentum_trades WHERE id=?', [tid]).fetchone()
    print(r)
"
```

And for one, manually compute tape balance by querying ws_matches directly:
```bash
/c/Users/Nathan/AppData/Local/Python/pythoncore-3.14-64/python.exe -c "
import sqlite3
c = sqlite3.connect('data_snapshots/market_tape.db')
# adjust pair + ts_epoch window to match the chosen trade
print(c.execute(\"\"\"
SELECT SUM(CASE WHEN UPPER(side)='BUY' THEN price*size ELSE 0 END) as buy,
       SUM(CASE WHEN UPPER(side)='SELL' THEN price*size ELSE 0 END) as sell,
       COUNT(*)
FROM ws_matches WHERE pair=? AND ts_epoch BETWEEN ? AND ?
\"\"\", ['<PAIR>', <EPOCH>-600, <EPOCH>]).fetchone())
"
```

Confirm the numbers roughly match what the script reported (modulo rounding).

- [ ] **Step 5: Commit**

```bash
git add -f tests/research_exit_quality.py
git commit -m "feat(research): phase 2 full-universe table + summary"
```

---

## Task 10: Final review + update memory

**Files:**
- Modify: `MEMORY.md` + new memory entry if there are surprising findings

- [ ] **Step 1: Read the generated reports**

```bash
cat tests/out/exit_quality_phase1_*.md
cat tests/out/exit_quality_phase2_*.md
```

- [ ] **Step 2: Save a project memory summarizing findings**

If the analysis revealed anything non-obvious (e.g., "signal X is the strongest predictor," "composite threshold Y separates labels cleanly," "wall_state is mostly None and doesn't help"), capture it in a new project memory at `C:\Users\Nathan\.claude\projects\c--Users-Nathan-cryptobot\memory\project_exit_quality_findings.md`.

Structure: lead with the finding, **Why:** the context, **How to apply:** what this means for a future Phase 3 (live integration). Add a one-line pointer to `MEMORY.md`.

If nothing surprising came out, skip this step — don't save a memory that just restates the spec.

- [ ] **Step 3: Commit**

```bash
git add -f tests/out/exit_quality_phase1_*.md tests/out/exit_quality_phase2_*.md
git commit -m "research(exit-quality): phase 1 + phase 2 output snapshots"
```

(`tests/out/` is gitignored — use `-f` to force. This preserves the raw research output alongside the code.)

---

## Done

After Task 10, the analysis is complete. Next decisions (out of scope for this plan):

- If results are clean → write Phase 3 spec proposing a live "continue-vs-rollover" composite gate
- If results are noisy → reconsider signal definitions or collect more data before tuning
- If market_tape.db overlay-persistence issue matters → separate GitHub issue for a bind-mount fix (out of scope here)
