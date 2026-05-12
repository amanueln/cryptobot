"""Daily Donchian-vs-Real comparison report.

Runs at 08:00 UTC via cron. For YESTERDAY (the most recent complete UTC day):

  1. Pull all donchian_shadow rows where ts is in [yesterday 00:00, yesterday 23:59:59].
  2. Replay each through the current exit logic (trail + 8% ATR stop + 24h cap)
     using Coinbase 5-min candles, fill in exit_*, pnl_pct, peak_pct, mae_pct,
     net_usd, replayed=1.
  3. Apply single-position queue (Option A): walk signals in time order,
     mark kept_in_queue=1 for first non-overlapping signal, skip those that
     overlap a prior open trade.
  4. Pull yesterday's real momentum_trades.
  5. Write/upsert one row to donchian_daily_compare for that date.
  6. Print a summary; optional Discord post (controlled via --discord flag).

Designed to be idempotent: re-running for the same date overwrites the row
and re-replays only unreplayed signals.

USAGE:
    python3 donchian_daily_compare.py [--date YYYY-MM-DD] [--discord]

Without --date, runs for yesterday UTC.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests


# Bot constants (match the live engine)
POSITION_USD = 3000.0
FEE_PCT_PER_SIDE = 0.6
MAX_HOLD_HOURS = 24
ATR_STOP_PCT = 8.0
TRAIL_TIERS = [(2.0, 1.0), (7.0, 1.5), (9.0, 0.75), (14.0, 0.35)]


# DB path resolution — bot uses data/candles.db relative to working dir.
# Override via env var for tests / local runs.
DB_PATH = os.environ.get("CRYPTOBOT_DB_PATH",
                         "/app/src/data/candles.db" if os.path.exists("/app/src") else "data/candles.db")
CANDLE_URL = "https://api.coinbase.com/api/v3/brokerage/market/products"


# ---------------- Candle fetch ----------------

def fetch_5min_candles(pair: str, start_ts: int, hours: int = MAX_HOLD_HOURS + 1):
    """Fetch 5-min Coinbase candles from start_ts forward `hours` hours."""
    end_ts = start_ts + hours * 3600
    params = {
        "start": str(start_ts),
        "end": str(end_ts),
        "granularity": "FIVE_MINUTE",
    }
    for attempt in range(3):
        try:
            r = requests.get(f"{CANDLE_URL}/{pair}/candles", params=params, timeout=15)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            if r.status_code != 200:
                return []
            data = r.json().get("candles", [])
            out = []
            for c in reversed(data):
                out.append({
                    "ts": int(c["start"]),
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                })
            return out
        except Exception:
            time.sleep(1)
    return []


# ---------------- Trade simulation ----------------

def compute_trail_stop(peak_price, entry_price, tiers):
    if peak_price is None or entry_price <= 0:
        return None
    peak_pct = (peak_price - entry_price) / entry_price * 100
    chosen = None
    for thresh, trail_pct in tiers:
        if peak_pct >= thresh:
            chosen = trail_pct
    return peak_price * (1 - chosen / 100) if chosen is not None else None


def simulate_exit(candles, entry_price):
    """Walk forward applying trail + ATR stop + 24h cap. Return dict or None."""
    if not candles:
        return None
    stop_price = entry_price * (1 - ATR_STOP_PCT / 100)
    peak = entry_price
    trough = entry_price
    trail_stop = None
    entry_ts = candles[0]["ts"]

    for c in candles:
        if c["high"] > peak: peak = c["high"]
        if c["low"] < trough: trough = c["low"]
        new_trail = compute_trail_stop(peak, entry_price, TRAIL_TIERS)
        if new_trail is not None and (trail_stop is None or new_trail > trail_stop):
            trail_stop = new_trail
        hours_held = (c["ts"] - entry_ts) / 3600
        if trail_stop is not None and c["low"] <= trail_stop:
            return {"reason": "trail", "exit_ts": c["ts"], "exit_price": trail_stop,
                    "pnl_pct": (trail_stop - entry_price) / entry_price * 100,
                    "peak_pct": (peak - entry_price) / entry_price * 100,
                    "mae_pct": (trough - entry_price) / entry_price * 100,
                    "hours": hours_held}
        if c["low"] <= stop_price:
            return {"reason": "stop", "exit_ts": c["ts"], "exit_price": stop_price,
                    "pnl_pct": (stop_price - entry_price) / entry_price * 100,
                    "peak_pct": (peak - entry_price) / entry_price * 100,
                    "mae_pct": (trough - entry_price) / entry_price * 100,
                    "hours": hours_held}
        if hours_held >= MAX_HOLD_HOURS:
            return {"reason": "time", "exit_ts": c["ts"], "exit_price": c["close"],
                    "pnl_pct": (c["close"] - entry_price) / entry_price * 100,
                    "peak_pct": (peak - entry_price) / entry_price * 100,
                    "mae_pct": (trough - entry_price) / entry_price * 100,
                    "hours": hours_held}
    # Ran out of candles before 24h
    last = candles[-1]
    hours_held = (last["ts"] - entry_ts) / 3600
    return {"reason": "data_end", "exit_ts": last["ts"], "exit_price": last["close"],
            "pnl_pct": (last["close"] - entry_price) / entry_price * 100,
            "peak_pct": (peak - entry_price) / entry_price * 100,
            "mae_pct": (trough - entry_price) / entry_price * 100,
            "hours": hours_held}


# ---------------- Date window helpers ----------------

def utc_date_bounds(date_str: str):
    """For 'YYYY-MM-DD' return (start_iso, end_iso) in UTC."""
    start = datetime.fromisoformat(date_str + "T00:00:00+00:00")
    end = start + timedelta(days=1) - timedelta(microseconds=1)
    return start.isoformat(), end.isoformat()


# ---------------- Replay ----------------

def replay_shadows_for_date(conn, date_str: str) -> int:
    """For each unreplayed donchian_shadow row in date_str, fetch candles
    and fill in exit_*, pnl_pct, etc. Returns number of rows updated."""
    start_iso, end_iso = utc_date_bounds(date_str)
    rows = list(conn.execute(
        "SELECT id, ts, pair, entry_price FROM donchian_shadow "
        "WHERE ts BETWEEN ? AND ? AND replayed = 0",
        (start_iso, end_iso)
    ).fetchall())
    if not rows:
        return 0

    updated = 0
    for row in rows:
        row_id, ts_str, pair, entry_price = row
        ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        candles = fetch_5min_candles(pair, int(ts_dt.timestamp()))
        if not candles:
            # Mark as replayed with no data to avoid retrying forever
            conn.execute(
                "UPDATE donchian_shadow SET replayed=1, exit_reason='no_candles' "
                "WHERE id=?", (row_id,)
            )
            continue
        out = simulate_exit(candles, entry_price)
        if out is None:
            conn.execute(
                "UPDATE donchian_shadow SET replayed=1, exit_reason='sim_failed' "
                "WHERE id=?", (row_id,)
            )
            continue
        fees = POSITION_USD * (FEE_PCT_PER_SIDE / 100) * 2
        net_usd = POSITION_USD * (out["pnl_pct"] / 100) - fees
        exit_ts_iso = datetime.fromtimestamp(out["exit_ts"], tz=timezone.utc).isoformat()
        conn.execute(
            "UPDATE donchian_shadow SET replayed=1, exit_ts=?, exit_price=?, "
            "exit_reason=?, pnl_pct=?, peak_pct=?, mae_pct=?, hours_held=?, net_usd=? "
            "WHERE id=?",
            (exit_ts_iso, out["exit_price"], out["reason"], out["pnl_pct"],
             out["peak_pct"], out["mae_pct"], out["hours"], net_usd, row_id)
        )
        updated += 1
        time.sleep(0.1)  # rate-limit safety
    conn.commit()
    return updated


def apply_single_position_queue(conn, date_str: str) -> None:
    """Mark kept_in_queue=1 for shadows that fit a single-position queue
    starting from each day. Resets the flag first for that day to be idempotent.
    """
    start_iso, end_iso = utc_date_bounds(date_str)
    conn.execute(
        "UPDATE donchian_shadow SET kept_in_queue=0 "
        "WHERE ts BETWEEN ? AND ?", (start_iso, end_iso)
    )
    rows = list(conn.execute(
        "SELECT id, ts, exit_ts FROM donchian_shadow "
        "WHERE ts BETWEEN ? AND ? AND replayed = 1 AND exit_ts IS NOT NULL "
        "ORDER BY ts",
        (start_iso, end_iso)
    ))
    cooldown_until_iso = "1970-01-01T00:00:00+00:00"
    for row_id, ts, exit_ts in rows:
        if ts >= cooldown_until_iso:
            conn.execute(
                "UPDATE donchian_shadow SET kept_in_queue=1 WHERE id=?", (row_id,)
            )
            cooldown_until_iso = exit_ts
    conn.commit()


# ---------------- Real-trade pull ----------------

def real_trades_for_date(conn, date_str: str):
    """Get yesterday's CLOSED real momentum trades (paired buys+sells).
    A trade 'belongs to' a date if its SELL happened on that date."""
    start_iso, end_iso = utc_date_bounds(date_str)
    # Pull all buys+sells touching the window
    win_start = (datetime.fromisoformat(date_str + "T00:00:00+00:00")
                 - timedelta(hours=72)).isoformat()
    rows = list(conn.execute(
        "SELECT timestamp, pair, side, pnl_pct, fee, cost_usd "
        "FROM momentum_trades "
        "WHERE timestamp >= ? AND timestamp <= ? "
        "ORDER BY timestamp",
        (win_start, end_iso)
    ))
    open_b = {}
    trades = []
    for ts, pair, side, pnl_pct, fee, cost_usd in rows:
        if side == "buy":
            open_b[pair] = (ts, cost_usd or POSITION_USD, fee or 0)
        else:
            bp = open_b.pop(pair, None)
            if bp is None or pnl_pct is None:
                continue
            sell_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            # Only count if sell is in target date
            if ts < start_iso or ts > end_iso:
                continue
            net = bp[1] * (pnl_pct / 100) - (bp[2] + (fee or 0))
            trades.append({"pair": pair, "buy_ts": bp[0], "sell_ts": ts,
                           "pnl_pct": pnl_pct, "net": net})
    return trades


# ---------------- Aggregate + write ----------------

def write_daily_row(conn, date_str: str):
    start_iso, end_iso = utc_date_bounds(date_str)

    # Donchian aggregates (kept_in_queue=1 only — single-position simulation)
    cur = conn.execute(
        "SELECT COUNT(*) FROM donchian_shadow "
        "WHERE ts BETWEEN ? AND ?", (start_iso, end_iso)
    )
    n_signals = cur.fetchone()[0]
    kept_rows = list(conn.execute(
        "SELECT pnl_pct, net_usd, hours_held FROM donchian_shadow "
        "WHERE ts BETWEEN ? AND ? AND kept_in_queue = 1 "
        "AND replayed = 1 AND net_usd IS NOT NULL",
        (start_iso, end_iso)
    ))
    donch_n = len(kept_rows)
    donch_wins = sum(1 for r in kept_rows if r[0] is not None and r[0] > 0)
    donch_pnl = sum(r[1] for r in kept_rows if r[1] is not None) if kept_rows else 0.0
    donch_max_win = max((r[1] for r in kept_rows if r[1] is not None), default=None)
    donch_max_loss = min((r[1] for r in kept_rows if r[1] is not None), default=None)
    donch_avg_hold = (sum(r[2] for r in kept_rows if r[2] is not None) / donch_n
                      if donch_n else None)

    # Real trades
    real = real_trades_for_date(conn, date_str)
    real_n = len(real)
    real_wins = sum(1 for t in real if t["pnl_pct"] > 0)
    real_pnl = sum(t["net"] for t in real)
    real_max_win = max((t["net"] for t in real), default=None)
    real_max_loss = min((t["net"] for t in real), default=None)
    in_cash_flag = 1 if real_n == 0 else 0

    delta = donch_pnl - real_pnl
    now_iso = datetime.utcnow().isoformat()

    conn.execute("""
        INSERT INTO donchian_daily_compare (
            date, donch_n_signals, donch_n_kept, donch_wins, donch_pnl_usd,
            donch_biggest_win, donch_biggest_loss, donch_avg_hold_h,
            real_n, real_wins, real_pnl_usd, real_biggest_win, real_biggest_loss,
            delta_usd, real_in_cash_all_day, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(date) DO UPDATE SET
            donch_n_signals = excluded.donch_n_signals,
            donch_n_kept = excluded.donch_n_kept,
            donch_wins = excluded.donch_wins,
            donch_pnl_usd = excluded.donch_pnl_usd,
            donch_biggest_win = excluded.donch_biggest_win,
            donch_biggest_loss = excluded.donch_biggest_loss,
            donch_avg_hold_h = excluded.donch_avg_hold_h,
            real_n = excluded.real_n,
            real_wins = excluded.real_wins,
            real_pnl_usd = excluded.real_pnl_usd,
            real_biggest_win = excluded.real_biggest_win,
            real_biggest_loss = excluded.real_biggest_loss,
            delta_usd = excluded.delta_usd,
            real_in_cash_all_day = excluded.real_in_cash_all_day,
            created_at = excluded.created_at
    """, (date_str, n_signals, donch_n, donch_wins, donch_pnl, donch_max_win,
          donch_max_loss, donch_avg_hold, real_n, real_wins, real_pnl,
          real_max_win, real_max_loss, delta, in_cash_flag, now_iso))
    conn.commit()

    return {
        "date": date_str, "donch_n_signals": n_signals, "donch_n_kept": donch_n,
        "donch_pnl": donch_pnl, "real_n": real_n, "real_pnl": real_pnl,
        "delta": delta, "real_in_cash_all_day": in_cash_flag,
    }


# ---------------- Decision rule ----------------

def evaluate_decision(conn) -> dict:
    """Look at full compare history; return a decision status."""
    rows = list(conn.execute(
        "SELECT date, donch_n_kept, donch_pnl_usd, real_pnl_usd, delta_usd, "
        "       real_in_cash_all_day "
        "FROM donchian_daily_compare ORDER BY date"
    ))
    if not rows:
        return {"status": "no_data", "days": 0, "message": "no daily rows yet"}

    n_days = len(rows)
    fair_days = [r for r in rows if not r[5]]  # exclude real_in_cash_all_day
    if not fair_days:
        return {"status": "gathering", "days": n_days,
                "message": f"only {n_days} day(s); all were 'real in cash' — not fair"}

    total_donch = sum(r[2] for r in rows)
    total_real = sum(r[3] for r in rows)
    total_delta = total_donch - total_real
    total_kept = sum(r[1] for r in rows)
    # Winning days: Donch beats Real on a fair day
    winning_days = sum(1 for r in fair_days if r[4] > 0)
    fair_n = len(fair_days)
    consistency_threshold = max(1, int(0.6 * fair_n + 0.5))

    if n_days >= 14:
        status = "decision_time"
        message = f"14-day window complete. Donch ${total_donch:+.2f} vs Real ${total_real:+.2f}."
    elif n_days >= 7:
        if total_delta >= 200 and total_kept >= 20 and winning_days >= consistency_threshold:
            status = "early_ship_eligible"
            message = (f"Day {n_days}: Donch ${total_donch:+.2f}, Real ${total_real:+.2f}, "
                       f"Δ ${total_delta:+.2f}, {total_kept} kept trades, "
                       f"{winning_days}/{fair_n} winning days. ELIGIBLE — manual review.")
        else:
            status = "gathering"
            message = (f"Day {n_days}: insufficient signal for early ship "
                       f"(Δ ${total_delta:+.2f}, kept {total_kept}, winning days {winning_days}/{fair_n})")
    else:
        status = "gathering"
        message = f"Day {n_days}: gathering data, decision at day 7+"

    return {
        "status": status, "days": n_days, "fair_days": fair_n,
        "winning_days": winning_days, "winning_threshold": consistency_threshold,
        "total_donch_pnl": round(total_donch, 2),
        "total_real_pnl": round(total_real, 2),
        "total_delta": round(total_delta, 2),
        "total_donch_kept": total_kept,
        "message": message,
    }


# ---------------- Main ----------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD (default: yesterday UTC)")
    parser.add_argument("--discord", action="store_true", help="Send Discord summary")
    args = parser.parse_args()

    if args.date:
        date_str = args.date
    else:
        date_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"=== Donchian daily compare for {date_str} ===")
    print(f"DB: {DB_PATH}")

    # Ensure schemas exist (idempotent)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    try:
        from engine.donchian_shadow_schema import init_schema
        init_schema(DB_PATH)
    except Exception as e:
        print(f"WARN: schema init failed: {e}")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        # 1. Replay any unreplayed shadows for the date
        n_replayed = replay_shadows_for_date(conn, date_str)
        print(f"Replayed {n_replayed} shadow rows")

        # 2. Apply single-position queue
        apply_single_position_queue(conn, date_str)
        print("Applied single-position queue")

        # 3. Write daily compare row
        result = write_daily_row(conn, date_str)
        print(f"Daily summary: Donch {result['donch_n_kept']} kept "
              f"(${result['donch_pnl']:+.2f}), "
              f"Real {result['real_n']} ({result['real_pnl']:+.2f}), "
              f"Δ ${result['delta']:+.2f}"
              + (" [REAL IN CASH ALL DAY]" if result['real_in_cash_all_day'] else ""))

        # 4. Decision rule
        decision = evaluate_decision(conn)
        print(f"Decision: {decision['status']} — {decision['message']}")

        # 5. Discord (optional)
        if args.discord:
            send_discord_summary(result, decision)
    finally:
        conn.close()


def send_discord_summary(result, decision):
    """Optional Discord post. Reads webhook from config/bot_config.yaml."""
    try:
        import yaml
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "config",
                               "bot_config.yaml")) as f:
            cfg = yaml.safe_load(f)
        webhook = cfg.get("early_scanner", {}).get("discord_webhook")
        if not webhook:
            return
        flag = " 🟡 *Real in cash all day*" if result['real_in_cash_all_day'] else ""
        msg = (f"**Donchian Daily ({result['date']})**\n"
               f"• Donch: {result['donch_n_kept']} trades, ${result['donch_pnl']:+.2f}\n"
               f"• Real:  {result['real_n']} trades, ${result['real_pnl']:+.2f}\n"
               f"• Δ:     ${result['delta']:+.2f}{flag}\n\n"
               f"_{decision['message']}_")
        requests.post(webhook, json={"content": msg}, timeout=10)
    except Exception as e:
        print(f"discord post failed: {e}")


if __name__ == "__main__":
    main()
