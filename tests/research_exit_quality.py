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


def iso_to_epoch(ts_iso: str) -> float:
    """Parse an ISO timestamp to UTC epoch seconds.

    candles.db stores timestamps as UTC-naive ISO text (e.g. '2026-04-17T02:54:56').
    Treat naive strings as UTC, not local. An explicit offset/Z is honored.
    """
    d = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


def epoch_to_iso(ts_epoch: float) -> str:
    """Format a UTC epoch as a naive UTC ISO string matching candles.db format."""
    return dt.datetime.fromtimestamp(ts_epoch, tz=dt.timezone.utc).replace(tzinfo=None).isoformat()


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


def _ema(values: list[float], period: int) -> list[float]:
    """Simple EMA. Returns list same length as input; first (period-1) entries padded with None."""
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
    ts_iso = epoch_to_iso(ts_epoch)
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


def signal_wall_state(
    con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float,
    entry_price: float,
) -> SignalResult:
    """Signal 4: most recent wall_decisions row for this pair before ts_epoch.

    +1 if action in ('anchor','shift') AND wall_aware_stop >= entry_price * 1.012 (fee buffer).
     0 if observed but below fee buffer (can't actually protect profit).
    -1 if action = 'cleared' (wall evaporated).
    None if no rows for this pair ever, or if entry_price <= 0 (can't compute buffer).
    """
    if entry_price <= 0:
        return SignalResult(None, {"reason": "no_entry_price"})
    ts_iso = epoch_to_iso(ts_epoch)
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


def signal_regime(con: duckdb.DuckDBPyConnection, pair: str, ts_epoch: float) -> SignalResult:
    """Signal 5: BTC-keyed regime snapshot (most recent ≤ ts_epoch).

    +1 if regime_bullish=1 AND btc_4h_return > 0.
    -1 if regime_bullish=0 AND btc_4h_return < 0.
     0 otherwise (mixed signals).
    None if no snapshot found.
    """
    ts_iso = epoch_to_iso(ts_epoch)
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
    if not exit_price or exit_price <= 0:
        return {"n": 0, "reason": "no_exit_price"}
    ts_iso_start = epoch_to_iso(exit_ts_epoch)
    ts_iso_end   = epoch_to_iso(exit_ts_epoch + 6 * 3600)
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
        target_iso = epoch_to_iso(target)
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
    exit_epoch = iso_to_epoch(ts_iso)

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
        exit_epoch = iso_to_epoch(ts_iso)
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


def _probe(con: duckdb.DuckDBPyConnection, pair: str, ts_iso: str, entry_price: float = 0.0) -> None:
    """Print every signal's value at (pair, ts_iso). For smoke-testing."""
    ts_epoch = iso_to_epoch(ts_iso)
    print(f"probe {pair} @ {ts_iso} entry={entry_price} (epoch {ts_epoch:.0f})")
    print(f"  tape_balance:   {signal_tape_balance(con, pair, ts_epoch)}")
    print(f"  book_imbalance: {signal_book_imbalance(con, pair, ts_epoch)}")
    print(f"  micro_trend:    {signal_micro_trend(con, pair, ts_epoch)}")
    print(f"  wall_state:     {signal_wall_state(con, pair, ts_epoch, entry_price)}")
    print(f"  regime:         {signal_regime(con, pair, ts_epoch)}")


def main() -> None:
    con = connect()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) >= 4 and sys.argv[1] == "probe":
        entry = float(sys.argv[4]) if len(sys.argv) >= 5 else 0.0
        _probe(con, sys.argv[2], sys.argv[3], entry)
        return
    if len(sys.argv) >= 6 and sys.argv[1] == "composite":
        # usage: composite <PAIR> <EXIT_ISO> <ENTRY_PRICE> <EXIT_PRICE>
        pair = sys.argv[2]
        ts_iso = sys.argv[3]
        entry_px = float(sys.argv[4])
        exit_px = float(sys.argv[5])
        ts_epoch = iso_to_epoch(ts_iso)
        c = compute_composite(con, pair, ts_epoch, entry_px)
        p = post_exit_path(con, pair, ts_epoch, exit_px)
        print(f"composite={c.composite}  available={c.n_available}/5")
        for name, s in c.signals.items():
            print(f"  {name}: {s.score}")
        print(f"post-exit: {p}")
        print(f"label: {label_trade(p)}")
        return
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
    if len(sys.argv) >= 2 and sys.argv[1] == "phase2":
        stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
        out_path = OUT_DIR / f"exit_quality_phase2_{stamp}.md"
        blocks = [f"# Phase 2 — last {LOOKBACK_DAYS}d closed trades — {stamp}\n",
                  freshness_report(con),
                  emit_phase2_table(con)]
        out_path.write_text("\n".join(blocks), encoding="utf-8")
        print(f"Wrote {out_path}")
        return
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    out_path = OUT_DIR / f"exit_quality_{stamp}.md"
    lines = [f"# Exit-Quality Analysis — {stamp}\n", freshness_report(con)]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
