from __future__ import annotations

"""Flask REST API for CryptoBot trading dashboard.

Reads from data/candles.db (read-only) and serves candle, trade,
equity, indicator, and status data to the Angular frontend.

Usage:
    py dashboard/api/app.py
    # Serves on http://localhost:5001
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from flask import Flask, jsonify, redirect, request, send_from_directory, send_file
from flask_cors import CORS
from ta.trend import ADXIndicator, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.momentum import RSIIndicator
from ta.volume import OnBalanceVolumeIndicator

import hashlib
import hmac
import secrets
import time
import pyotp
import qrcode
import io
import base64

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "ui", "dist", "ui", "browser")

app = Flask(__name__, static_folder=None)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "candles.db")

# --- Auth config ---
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
TOTP_SECRET_PATH = os.path.join(DATA_DIR, ".totp_secret")
FLASK_SECRET_PATH = os.path.join(DATA_DIR, ".flask_secret")

def _get_flask_secret():
    """Load or generate Flask secret key for cookie signing."""
    if os.path.exists(FLASK_SECRET_PATH):
        with open(FLASK_SECRET_PATH, "r") as f:
            return f.read().strip()
    secret = secrets.token_hex(32)
    with open(FLASK_SECRET_PATH, "w") as f:
        f.write(secret)
    return secret

if AUTH_ENABLED:
    app.secret_key = _get_flask_secret()


@app.before_request
def check_auth():
    """Gate all requests behind TOTP auth when enabled."""
    if not AUTH_ENABLED:
        return None

    path = request.path

    # Always allow auth endpoints and static assets
    if path.startswith("/api/auth/"):
        return None
    if path in ("/login", "/setup"):
        return send_from_directory(STATIC_DIR, "index.html")
    # Static file extensions
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    if ext in ("js", "css", "ico", "png", "jpg", "svg", "woff", "woff2", "ttf", "map"):
        return None

    # Check if setup is needed
    if not os.path.exists(TOTP_SECRET_PATH):
        if path.startswith("/api/"):
            return jsonify({"error": "setup_required"}), 401
        return redirect("/setup")

    # Check session cookie
    session_token = request.cookies.get("bot_session")
    if not session_token or not _verify_session(session_token):
        if path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect("/login")

    return None


def _create_session_token():
    """Create a signed session token."""
    payload = f"{int(time.time())}"
    sig = hmac.new(app.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"

def _verify_session(token):
    """Verify a session token is valid and not expired."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        timestamp, sig = parts
        expected = hmac.new(app.secret_key.encode(), timestamp.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        # Check expiry (30 days)
        age = int(time.time()) - int(timestamp)
        return age < 30 * 86400
    except (ValueError, TypeError):
        return False


DEFAULT_NUM_GRIDS = 20


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------------------------------------------------
# Human-readable summary generators
# ------------------------------------------------------------------

def generate_status_summary(equity, pnl, total_trades, pairs_info, last_trade_time, uptime_seconds=0):
    """Turn raw status numbers into a friendly sentence."""
    parts = []

    # P&L sentence
    if pnl > 0:
        parts.append(f"You're up ${pnl:.2f}")
    elif pnl < 0:
        parts.append(f"You're down ${abs(pnl):.2f}")
    else:
        parts.append("Breaking even so far")

    # Trade activity
    if total_trades == 0:
        parts.append("No trades yet — the bot is watching and waiting for the right entry.")
    elif total_trades == 1:
        parts.append("1 trade completed so far.")
    else:
        parts.append(f"{total_trades} trades completed.")

    # Uptime
    if uptime_seconds > 0:
        if uptime_seconds < 3600:
            parts.append(f"Running for {uptime_seconds // 60} minutes.")
        elif uptime_seconds < 86400:
            parts.append(f"Running for {uptime_seconds // 3600} hours.")
        else:
            parts.append(f"Running for {uptime_seconds // 86400} days.")

    return " ".join(parts)


def generate_pair_summary(pair_data, grid_levels=None, position=None):
    """Turn a pair's raw stats into a friendly description."""
    name = pair_data["pair"].replace("-USD", "")
    regime = (pair_data.get("regime") or "").lower().replace("_", " ")
    held = pair_data.get("grid_held", 0)
    total = pair_data.get("grid_total", DEFAULT_NUM_GRIDS)
    trades = pair_data.get("trade_count", 0)

    # Regime description
    regime_map = {
        "ranging": f"{name} is bouncing in a range — good for grid trading.",
        "trending up": f"{name} is trending up. The grid is catching dips on the way.",
        "trending down": f"{name} is trending down. Being cautious with new buys.",
        "volatile": f"{name} is seeing big swings. Grid widened to handle the volatility.",
        "squeeze": f"{name} is very quiet right now. Waiting for a breakout.",
    }
    regime_text = regime_map.get(regime, f"{name} is active.")

    # Grid status
    if held == 0 and trades == 0:
        grid_text = f"No fills yet — waiting for price to reach the first buy level."
    elif held == 0:
        grid_text = f"All positions sold. Ready for the next dip."
    else:
        grid_text = f"{held} of {total} buy levels filled."

    # Next buy
    next_buy_text = ""
    if grid_levels and grid_levels.get("levels"):
        price = pair_data.get("price", 0)
        buy_levels = sorted(
            [l["price"] for l in grid_levels["levels"] if l["type"] == "buy"],
            reverse=True,
        )
        nxt = next((p for p in buy_levels if p <= price), buy_levels[-1] if buy_levels else None)
        if nxt:
            next_buy_text = f"Next buy at ${nxt:.6g}."

    parts = [regime_text, grid_text]
    if next_buy_text:
        parts.append(next_buy_text)
    return " ".join(parts)


def generate_health_summary(self_check_data):
    """Turn health bar stats into a friendly sentence."""
    if not self_check_data:
        return "No health data yet — the bot just started."

    parts = []
    daily = self_check_data.get("daily_pnl")
    weekly = self_check_data.get("weekly_pnl")
    streak = self_check_data.get("streak", {})

    # Daily P&L
    if daily is not None:
        if daily >= 0:
            parts.append(f"Good day so far — up ${daily:.2f}, well within the $30 daily limit.")
        elif daily > -15:
            parts.append(f"Down ${abs(daily):.2f} today, but within normal range.")
        else:
            parts.append(f"Rough day — down ${abs(daily):.2f}. Approaching the $30 safety limit.")

    # Streak
    s_type = streak.get("type", "none")
    s_days = streak.get("days", 0)
    if s_days > 0 and s_type == "winning":
        parts.append(f"On a {s_days}-day winning streak!")
    elif s_days > 0 and s_type == "losing":
        parts.append(f"{s_days}-day losing streak — the bot will adjust if it continues.")

    # Vol accuracy
    vol_acc = self_check_data.get("vol_accuracy_24h", {})
    vol_count = vol_acc.get("count", 0)
    vol_err = vol_acc.get("avg_error_pct", 0)
    if vol_count == 0:
        parts.append("Volatility model is still learning — not enough data yet.")
    elif vol_err <= 10:
        parts.append("Volatility predictions are accurate.")
    elif vol_err <= 25:
        parts.append("Volatility predictions are rough but usable.")
    else:
        parts.append("The volatility model isn't accurate yet, so the bot is using simple tracking instead. Normal for the first few weeks.")

    return " ".join(parts) if parts else "Everything is running normally."


def generate_trade_summary(trade):
    """Turn a raw trade event into a friendly sentence."""
    pair_name = trade["pair"].replace("-USD", "")
    side = trade.get("side", "")
    price = trade.get("price", 0)
    amount = trade.get("amount", 0)
    reason = trade.get("reason", "")
    net_profit = trade.get("net_profit")
    cost_usd = trade.get("cost_usd", 0)

    price_str = f"${price:.6g}"

    if side == "buy":
        text = f"Bought {amount:,.0f} {pair_name} at {price_str}"
        if cost_usd:
            text += f" for ${cost_usd:.2f}"
        if "grid" in reason.lower():
            # Extract level info from reason
            text += f" — {reason}"
    elif side == "sell":
        text = f"Sold {amount:,.0f} {pair_name} at {price_str}"
        if net_profit is not None:
            if net_profit >= 0:
                text += f" for ${net_profit:.2f} profit"
            else:
                text += f" for ${abs(net_profit):.2f} loss"
    else:
        text = f"{pair_name}: {reason}"
    return text


def generate_event_summary(event_type, title, detail):
    """Make activity log events more conversational."""
    if event_type == "boot":
        return title, detail
    elif event_type == "trade_buy":
        # Title is already like "Bought 42000 NKN at $0.0139"
        return title, detail or ""
    elif event_type == "trade_sell":
        return title, detail or ""
    elif event_type == "scan_complete":
        return title, detail or ""
    elif event_type == "range_recalc":
        return "Grid boundaries recalculated based on recent price action.", detail or ""
    elif event_type == "atr_adjust":
        return "Grid spacing adjusted — volatility changed.", detail or ""
    return title, detail or ""


def _migrate_db():
    """Ensure newer columns exist in sim_trades (matches trade_logger migrations)."""
    conn = sqlite3.connect(DB_PATH)
    for col, typedef in [
        ("regime", "TEXT DEFAULT ''"),
        ("adx", "REAL DEFAULT 0"),
        ("rsi", "REAL DEFAULT 0"),
        ("atr_multiplier", "REAL DEFAULT 1.0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE sim_trades ADD COLUMN {col} {typedef}")
        except Exception:
            pass
    conn.commit()
    conn.close()


_migrate_db()


def _get_active_pairs(conn) -> list[str]:
    """Get the pairs the bot is actively trading."""
    # 1. Check pair_scans for selected pairs (most accurate)
    try:
        row = conn.execute(
            "SELECT selected_pairs FROM pair_scans ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row and row["selected_pairs"]:
            selected = json.loads(row["selected_pairs"])
            pairs = [p["pair"] if isinstance(p, dict) else p for p in selected]
            if pairs:
                return sorted(pairs)
    except Exception:
        pass
    # 2. Pairs that have actual trades
    rows = conn.execute(
        "SELECT DISTINCT pair FROM sim_trades ORDER BY pair"
    ).fetchall()
    if rows:
        return [r["pair"] for r in rows]
    # 3. No scans and no trades — bot hasn't started trading yet
    return []


# ---------- /api/candles ----------

@app.route("/api/candles")
def api_candles():
    pair = request.args.get("pair", "DOGE-USD")
    hours = int(request.args.get("hours", 72))
    granularity = request.args.get("granularity", "ONE_HOUR")

    start = (datetime.now() - timedelta(hours=hours)).isoformat()
    conn = get_db()
    rows = conn.execute(
        """SELECT timestamp, open, high, low, close, volume
           FROM candles
           WHERE pair = ? AND granularity = ? AND timestamp >= ?
           ORDER BY timestamp ASC""",
        (pair, granularity, start),
    ).fetchall()
    conn.close()

    return jsonify([
        {
            "time": row["timestamp"],
            "open": row["open"],
            "high": row["high"],
            "low": row["low"],
            "close": row["close"],
            "volume": row["volume"],
        }
        for row in rows
    ])


# ---------- /api/trades ----------

@app.route("/api/trades")
def api_trades():
    pair = request.args.get("pair")
    limit = int(request.args.get("limit", 50))

    conn = get_db()

    # Fetch ALL trades chronologically to compute cost basis
    if pair:
        all_rows = conn.execute(
            """SELECT id, timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason,
                      regime, adx, rsi, atr_multiplier
               FROM sim_trades WHERE pair = ? ORDER BY id ASC""",
            (pair,),
        ).fetchall()
    else:
        all_rows = conn.execute(
            """SELECT id, timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason,
                      regime, adx, rsi, atr_multiplier
               FROM sim_trades ORDER BY id ASC""",
        ).fetchall()

    # Get current prices for live P&L on buys
    current_prices: dict[str, float] = {}
    active_pairs = _get_active_pairs(conn)
    for p_name in active_pairs:
        price_row = conn.execute(
            "SELECT close FROM candles WHERE pair = ? ORDER BY timestamp DESC LIMIT 1",
            (p_name,),
        ).fetchone()
        if price_row:
            current_prices[p_name] = price_row["close"]

    conn.close()

    # Walk all trades to compute round-trip P&L for sells.
    # Track per-pair FIFO cost basis: list of (qty, cost_per_unit_incl_fee, buy_timestamp, buy_price).
    fifo: dict[str, list] = {}  # pair -> [(qty, cost_per_unit_incl_fee, buy_timestamp, buy_price)]
    enriched = []
    cumulative_pnl = 0.0

    for row in all_rows:
        t = {
            "id": row["id"],
            "timestamp": row["timestamp"],
            "pair": row["pair"],
            "side": row["side"],
            "price": row["price"],
            "amount": row["amount"],
            "cost_usd": row["cost_usd"],
            "fee": row["fee"],
            "strategy": row["strategy"],
            "reason": row["reason"],
            "regime": row["regime"] if "regime" in row.keys() else "",
            "adx": row["adx"] if "adx" in row.keys() else 0,
            "rsi": row["rsi"] if "rsi" in row.keys() else 0,
            "atr_multiplier": row["atr_multiplier"] if "atr_multiplier" in row.keys() else 1.0,
            "cost_basis": None,
            "revenue": None,
            "net_profit": None,
            "cumulative_pnl": None,
            "live_pnl": None,
            "live_pnl_pct": None,
            "hold_duration_seconds": None,
            "entry_price": None,
        }

        p = row["pair"]
        if p not in fifo:
            fifo[p] = []

        if row["side"] == "buy":
            # cost_usd = total USD spent; amount = crypto received
            # cost per unit = total_spent / crypto_amount
            qty = row["amount"]
            total_spent = row["cost_usd"]  # includes fee
            if qty > 0:
                fifo[p].append((qty, total_spent / qty, row["timestamp"], row["price"]))

            # Compute live (unrealized) P&L for this buy
            cur_price = current_prices.get(p)
            if cur_price is not None and qty > 0:
                cost_per_unit = total_spent / qty
                live_value = cur_price * qty
                live_pnl = live_value - total_spent
                live_pnl_pct = ((cur_price / cost_per_unit) - 1) * 100 if cost_per_unit > 0 else 0
                t["live_pnl"] = round(live_pnl, 4)
                t["live_pnl_pct"] = round(live_pnl_pct, 2)

        elif row["side"] == "sell":
            sell_qty = row["amount"]
            sell_revenue = row["cost_usd"]  # net USD received (gross - sell_fee)
            sell_fee = row["fee"]

            # Match against FIFO buy lots to compute cost basis
            cost_basis = 0.0
            remaining = sell_qty
            lots = fifo.get(p, [])
            had_matching_lots = len(lots) > 0
            matched_buy_timestamp = None
            matched_buy_price = None
            total_matched_qty = 0.0
            weighted_price_sum = 0.0
            earliest_buy_timestamp = None

            while remaining > 1e-12 and lots:
                lot_qty, lot_cpu, lot_ts, lot_price = lots[0]
                take = min(remaining, lot_qty)
                cost_basis += take * lot_cpu
                total_matched_qty += take
                weighted_price_sum += take * lot_price
                if earliest_buy_timestamp is None:
                    earliest_buy_timestamp = lot_ts
                remaining -= take
                if take >= lot_qty - 1e-12:
                    lots.pop(0)
                else:
                    lots[0] = (lot_qty - take, lot_cpu, lot_ts, lot_price)

            # If no matching buy lots existed, this is an orphan sell — cost_basis = null
            if not had_matching_lots and remaining > 1e-12:
                t["cost_basis"] = None
            else:
                t["cost_basis"] = round(cost_basis, 4)

            # Revenue: cost_usd on sell = net USD received (already minus sell fee)
            # cost_basis from FIFO = total USD spent on buy (already includes buy fee)
            # net_profit = what we got back - what we paid
            net_revenue = row["cost_usd"]  # already net of sell fee
            gross_revenue = sell_qty * row["price"]
            if t["cost_basis"] is not None:
                net_profit = net_revenue - cost_basis
                t["net_profit"] = round(net_profit, 4)
                cumulative_pnl += net_profit
                t["cumulative_pnl"] = round(cumulative_pnl, 4)

            t["revenue"] = round(gross_revenue, 4)

            # Compute entry_price from matched buy lots (weighted average)
            if total_matched_qty > 1e-12:
                t["entry_price"] = round(weighted_price_sum / total_matched_qty, 8)

            # Compute hold_duration_seconds from earliest matched buy
            if earliest_buy_timestamp is not None:
                try:
                    buy_dt = datetime.fromisoformat(str(earliest_buy_timestamp).replace("Z", "+00:00"))
                    sell_dt = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
                    t["hold_duration_seconds"] = round((sell_dt - buy_dt).total_seconds())
                except Exception:
                    pass

        enriched.append(t)

    # Return most-recent-first, limited
    enriched.reverse()
    return jsonify(enriched[:limit])


# ---------- /api/equity ----------

@app.route("/api/equity")
def api_equity():
    hours = int(request.args.get("hours", 72))
    start = (datetime.now() - timedelta(hours=hours)).isoformat()

    conn = get_db()
    rows = conn.execute(
        """SELECT timestamp, equity, balance_usd, positions_value
           FROM equity_snapshots
           WHERE timestamp >= ?
           ORDER BY timestamp ASC""",
        (start,),
    ).fetchall()
    conn.close()

    return jsonify([
        {
            "time": row["timestamp"],
            "equity": row["equity"],
            "balance_usd": row["balance_usd"],
            "positions_value": row["positions_value"],
        }
        for row in rows
    ])


# ---------- /api/status ----------

@app.route("/api/status")
def api_status():
    conn = get_db()

    # Latest equity
    eq_row = conn.execute(
        "SELECT equity, balance_usd, positions_value FROM equity_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()

    starting_balance = 3000.0

    # Compute live positions value from trade history (FIFO)
    # This is more accurate than the equity_snapshots which may be stale
    live_positions_value = 0.0
    trade_rows = conn.execute(
        """SELECT pair, side, price, amount, cost_usd FROM sim_trades ORDER BY id ASC"""
    ).fetchall()

    # Build open lots per pair using FIFO
    open_lots: dict[str, list[tuple[float, float]]] = {}  # pair -> [(price, amount)]
    for tr in trade_rows:
        pair_key = tr["pair"]
        if tr["side"] == "buy":
            open_lots.setdefault(pair_key, []).append((tr["price"], tr["amount"]))
        elif tr["side"] == "sell":
            remaining = tr["amount"]
            lots = open_lots.get(pair_key, [])
            while remaining > 0 and lots:
                lot_price, lot_amt = lots[0]
                if lot_amt <= remaining:
                    remaining -= lot_amt
                    lots.pop(0)
                else:
                    lots[0] = (lot_price, lot_amt - remaining)
                    remaining = 0

    # Value open lots at current market price
    for pair_key, lots in open_lots.items():
        if not lots:
            continue
        price_row = conn.execute(
            "SELECT close FROM candles WHERE pair = ? ORDER BY timestamp DESC LIMIT 1",
            (pair_key,),
        ).fetchone()
        if price_row:
            current_price = price_row["close"]
            for _, amt in lots:
                live_positions_value += current_price * amt

    # Use equity snapshot for total equity, but override balance/positions with live data
    snapshot_equity = eq_row["equity"] if eq_row else starting_balance

    # Live cash: use cost_usd which already includes fees
    # For buys: cost_usd = total USD spent (fee included in deduction)
    # For sells: cost_usd = net USD received (fee already subtracted)
    total_spent = 0.0
    total_received = 0.0
    for tr in trade_rows:
        if tr["side"] == "buy":
            total_spent += tr["cost_usd"]
        else:
            total_received += tr["cost_usd"]

    live_cash = starting_balance - total_spent + total_received
    live_equity = live_cash + live_positions_value
    pnl = live_equity - starting_balance
    pnl_pct = (pnl / starting_balance) * 100 if starting_balance > 0 else 0.0
    equity = live_equity

    # Per-pair latest prices and trade counts
    active_pairs = _get_active_pairs(conn)
    pairs_info = []
    for pair in active_pairs:
        price_row = conn.execute(
            """SELECT close, timestamp FROM candles
               WHERE pair = ? ORDER BY timestamp DESC LIMIT 1""",
            (pair,),
        ).fetchone()

        trade_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM sim_trades WHERE pair = ?",
            (pair,),
        ).fetchone()["cnt"]

        # Grid fill: net held levels = buys - sells
        buys = conn.execute(
            "SELECT COUNT(*) as c FROM sim_trades WHERE pair = ? AND side = 'buy'",
            (pair,),
        ).fetchone()["c"]
        sells = conn.execute(
            "SELECT COUNT(*) as c FROM sim_trades WHERE pair = ? AND side = 'sell'",
            (pair,),
        ).fetchone()["c"]

        pairs_info.append({
            "pair": pair,
            "price": price_row["close"] if price_row else 0,
            "last_candle": price_row["timestamp"] if price_row else None,
            "trade_count": trade_count,
            "regime": _detect_regime_for_pair(conn, pair),
            "grid_held": max(0, buys - sells),
            "grid_total": DEFAULT_NUM_GRIDS,
        })

    # Last trade
    last_trade_row = conn.execute(
        "SELECT timestamp FROM sim_trades ORDER BY id DESC LIMIT 1"
    ).fetchone()

    conn.close()

    total_trades = sum(p["trade_count"] for p in pairs_info)

    # Generate human-readable summaries for each pair
    for p in pairs_info:
        p["summary"] = generate_pair_summary(p)

    status_summary = generate_status_summary(
        equity, pnl, total_trades, pairs_info,
        last_trade_row["timestamp"] if last_trade_row else None,
    )

    return jsonify({
        "equity": round(equity, 2),
        "balance_usd": round(live_cash, 2),
        "positions_value": round(live_positions_value, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "starting_balance": starting_balance,
        "total_trades": total_trades,
        "last_trade_time": last_trade_row["timestamp"] if last_trade_row else None,
        "pairs": pairs_info,
        "summary": status_summary,
    })


def _detect_regime_for_pair(conn, pair: str) -> str:
    """Quick regime detection from recent candles."""
    rows = conn.execute(
        """SELECT close, high, low, volume FROM candles
           WHERE pair = ? AND granularity = 'ONE_HOUR'
           ORDER BY timestamp DESC LIMIT 300""",
        (pair,),
    ).fetchall()

    if len(rows) < 50:
        return "ranging"  # Default during warmup

    rows = list(reversed(rows))
    closes = pd.Series([r["close"] for r in rows])
    highs = pd.Series([r["high"] for r in rows])
    lows = pd.Series([r["low"] for r in rows])
    volumes = pd.Series([r["volume"] for r in rows])

    adx_ind = ADXIndicator(highs, lows, closes, window=14)
    adx = adx_ind.adx().iloc[-1] if len(closes) >= 28 else None

    ema_fast_val = EMAIndicator(closes, window=50).ema_indicator().iloc[-1] if len(closes) >= 50 else None
    ema_fast = None if (ema_fast_val is None or pd.isna(ema_fast_val)) else float(ema_fast_val)
    ema_slow_val = EMAIndicator(closes, window=200).ema_indicator().iloc[-1] if len(closes) >= 200 else None
    ema_slow = None if (ema_slow_val is None or pd.isna(ema_slow_val)) else float(ema_slow_val)

    bb = BollingerBands(closes, window=20, window_dev=2)
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]
    bb_mid = bb.bollinger_mavg().iloc[-1]
    bb_width = ((bb_upper - bb_lower) / bb_mid * 100) if bb_mid > 0 else 0

    vol_avg = volumes.rolling(20).mean().iloc[-1]
    vol_ratio = (volumes.iloc[-1] / vol_avg) if vol_avg > 0 else 1.0

    price = closes.iloc[-1]

    adx_val = None if (adx is None or pd.isna(adx)) else float(adx)

    # Squeeze: very narrow BB + low ADX (only needs 20 candles)
    if adx_val is not None and bb_width < 3.0 and adx_val < 20:
        return "squeeze"

    # Volatile: wide BB + volume spike (only needs 20 candles)
    if bb_width > 8.0 and vol_ratio >= 1.5:
        return "volatile"

    # Trending: use ADX + BB for strength, EMA for direction when available
    if adx_val is not None and adx_val > 25:
        # Prefer EMA50/200 for trend direction
        if ema_fast and ema_slow:
            if ema_fast > ema_slow and price > ema_fast:
                return "trending_up"
            if ema_fast < ema_slow and price < ema_fast:
                return "trending_down"
        # Fallback: use EMA50 alone (needs only 50 candles)
        elif ema_fast:
            if price > ema_fast:
                return "trending_up"
            else:
                return "trending_down"
        # Fallback: use BB position for direction
        elif bb_mid > 0:
            if price > bb_mid and bb_width > 4.0:
                return "trending_up"
            elif price < bb_mid and bb_width > 4.0:
                return "trending_down"

    # Low ADX or no strong signal
    return "ranging"


# ---------- /api/indicators ----------

@app.route("/api/indicators")
def api_indicators():
    pair = request.args.get("pair", "DOGE-USD")
    hours = int(request.args.get("hours", 72))

    # Fetch extra history for indicator warmup
    warmup_hours = hours + 220
    start = (datetime.now() - timedelta(hours=warmup_hours)).isoformat()

    conn = get_db()
    rows = conn.execute(
        """SELECT timestamp, open, high, low, close, volume
           FROM candles
           WHERE pair = ? AND granularity = 'ONE_HOUR' AND timestamp >= ?
           ORDER BY timestamp ASC""",
        (pair, start),
    ).fetchall()
    conn.close()

    if len(rows) < 30:
        return jsonify([])

    timestamps = [r["timestamp"] for r in rows]
    closes = pd.Series([r["close"] for r in rows], dtype=float)
    highs = pd.Series([r["high"] for r in rows], dtype=float)
    lows = pd.Series([r["low"] for r in rows], dtype=float)
    volumes = pd.Series([r["volume"] for r in rows], dtype=float)

    # Calculate indicators
    adx_ind = ADXIndicator(highs, lows, closes, window=14)
    adx_series = adx_ind.adx()

    rsi_ind = RSIIndicator(closes, window=14)
    rsi_series = rsi_ind.rsi()

    bb = BollingerBands(closes, window=20, window_dev=2)
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()
    bb_mid = bb.bollinger_mavg()

    ema50 = EMAIndicator(closes, window=50).ema_indicator()
    ema200 = EMAIndicator(closes, window=200).ema_indicator()

    obv_ind = OnBalanceVolumeIndicator(closes, volumes)
    obv_series = obv_ind.on_balance_volume()

    vol_avg = volumes.rolling(20).mean()

    atr = AverageTrueRange(highs, lows, closes, window=14).average_true_range()

    # Trim to requested window
    trim_start = len(rows) - int(hours)
    if trim_start < 0:
        trim_start = 0

    result = []
    for i in range(trim_start, len(rows)):
        result.append({
            "time": timestamps[i],
            "adx": _safe(adx_series, i),
            "rsi": _safe(rsi_series, i),
            "bb_upper": _safe(bb_upper, i),
            "bb_lower": _safe(bb_lower, i),
            "bb_mid": _safe(bb_mid, i),
            "ema50": _safe(ema50, i),
            "ema200": _safe(ema200, i),
            "obv": _safe(obv_series, i),
            "volume": volumes.iloc[i],
            "volume_avg": _safe(vol_avg, i),
            "atr": _safe(atr, i),
        })

    return jsonify(result)


def _safe(series: pd.Series, idx: int):
    val = series.iloc[idx]
    if pd.isna(val):
        return None
    return round(float(val), 6)


# ---------- /api/grid-levels ----------

@app.route("/api/grid-levels")
def api_grid_levels():
    pair = request.args.get("pair", "BTC-USD")
    num_grids = int(request.args.get("grids", DEFAULT_NUM_GRIDS))

    # Auto-fit from recent candles
    conn = get_db()
    rows = conn.execute(
        """SELECT high, low FROM candles
           WHERE pair = ? AND granularity = 'ONE_HOUR'
           ORDER BY timestamp DESC LIMIT 720""",
        (pair,),
    ).fetchall()
    conn.close()

    if not rows:
        return jsonify({"levels": [], "pair": pair, "error": "No candle data"})

    lows = [r["low"] for r in rows]
    highs = [r["high"] for r in rows]
    lower = min(lows) * 0.95
    upper = max(highs) * 1.05

    mode = request.args.get("mode", "geometric")

    levels = []
    if mode == "geometric" and lower > 0:
        ratio = (upper / lower) ** (1.0 / num_grids)
        for i in range(num_grids + 1):
            price = lower * (ratio ** i)
            levels.append({
                "price": round(price, 8),
                "type": "buy" if i < num_grids // 2 else "sell",
                "index": i,
            })
    else:
        step = (upper - lower) / num_grids
        for i in range(num_grids + 1):
            price = lower + i * step
            levels.append({
                "price": round(price, 8),
                "type": "buy" if i < num_grids // 2 else "sell",
                "index": i,
            })

    return jsonify({
        "pair": pair,
        "lower": round(lower, 8),
        "upper": round(upper, 8),
        "num_grids": num_grids,
        "mode": mode,
        "levels": levels,
    })


# ---------- /api/positions ----------

@app.route("/api/positions")
def api_positions():
    """Reconstruct current open positions from trade history.

    For each pair, walk all trades chronologically using FIFO lots.
    BUYs add lots; SELLs consume them. Remaining lots form open positions.
    """
    conn = get_db()
    active_pairs = _get_active_pairs(conn)

    positions = []
    for pair in active_pairs:
        trades = conn.execute(
            """SELECT side, price, amount, fee, timestamp
               FROM sim_trades
               WHERE pair = ?
               ORDER BY id ASC""",
            (pair,),
        ).fetchall()

        # FIFO lots: (qty, price_per_unit, fee_per_unit, timestamp)
        lots: list[tuple] = []

        for t in trades:
            if t["side"] == "buy":
                buy_qty = t["amount"]
                buy_fee = t["fee"] or 0
                if buy_qty > 0:
                    lots.append((buy_qty, t["price"], buy_fee / buy_qty, t["timestamp"]))
            elif t["side"] == "sell":
                remaining = t["amount"]
                while remaining > 1e-12 and lots:
                    lot_qty, lot_price, lot_fpu, lot_ts = lots[0]
                    take = min(remaining, lot_qty)
                    remaining -= take
                    if take >= lot_qty - 1e-12:
                        lots.pop(0)
                    else:
                        lots[0] = (lot_qty - take, lot_price, lot_fpu, lot_ts)

        if not lots:
            continue

        # Compute position from remaining lots
        qty = sum(l[0] for l in lots)
        if qty < 1e-12:
            continue

        cost_basis = sum(l[0] * (l[1] + l[2]) for l in lots)  # price + fee_per_unit
        avg_entry = cost_basis / qty if qty > 0 else 0

        # hold_since = timestamp of earliest remaining lot
        hold_since = lots[0][3]

        # Estimate sell fee rate from recent sells, or use 0.6% as default
        avg_sell_fee_rate = 0.006
        recent_sells = conn.execute(
            """SELECT fee, amount, price FROM sim_trades
               WHERE pair = ? AND side = 'sell'
               ORDER BY id DESC LIMIT 5""",
            (pair,),
        ).fetchall()
        if recent_sells:
            rates = []
            for s in recent_sells:
                gross = s["amount"] * s["price"]
                if gross > 0:
                    rates.append(s["fee"] / gross)
            if rates:
                avg_sell_fee_rate = sum(rates) / len(rates)

        # breakeven_price = avg_entry_with_fees / (1 - sell_fee_rate)
        # So that selling at breakeven_price covers entry cost + estimated sell fee
        breakeven_price = avg_entry / (1 - avg_sell_fee_rate) if avg_sell_fee_rate < 1 else avg_entry

        # Current price from latest candle
        price_row = conn.execute(
            "SELECT close FROM candles WHERE pair = ? ORDER BY timestamp DESC LIMIT 1",
            (pair,),
        ).fetchone()
        current_price = price_row["close"] if price_row else 0

        unrealized_pnl = (current_price - avg_entry) * qty
        unrealized_pnl_pct = ((current_price / avg_entry) - 1) * 100 if avg_entry > 0 else 0

        positions.append({
            "pair": pair,
            "quantity": round(qty, 8),
            "entry_price": round(avg_entry, 8),
            "current_price": current_price,
            "cost_basis": round(cost_basis, 2),
            "market_value": round(current_price * qty, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            "hold_since": hold_since,
            "breakeven_price": round(breakeven_price, 8),
        })

    conn.close()
    return jsonify(positions)


# ---------- /api/pairs ----------

@app.route("/api/pairs")
def api_pairs():
    """Return list of active pairs from the database."""
    conn = get_db()
    pairs = _get_active_pairs(conn)
    conn.close()
    return jsonify(pairs)


# ---------- /api/ml/predictions ----------

@app.route("/api/ml/predictions")
def api_ml_predictions():
    """Return recent ML predictions."""
    pair = request.args.get("pair")
    limit = int(request.args.get("limit", 50))

    conn = get_db()

    # Check if table exists
    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ml_predictions'"
    ).fetchone()
    if not table_check:
        conn.close()
        return jsonify([])

    if pair:
        rows = conn.execute(
            """SELECT id, timestamp, pair, direction, confidence,
                      feature_values, feature_contributions,
                      top_bullish, top_bearish,
                      recommended_action, recommended_size_pct,
                      actual_outcome, actual_price_change
               FROM ml_predictions
               WHERE pair = ?
               ORDER BY id DESC LIMIT ?""",
            (pair, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, timestamp, pair, direction, confidence,
                      feature_values, feature_contributions,
                      top_bullish, top_bearish,
                      recommended_action, recommended_size_pct,
                      actual_outcome, actual_price_change
               FROM ml_predictions
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    conn.close()

    return jsonify([
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "pair": r["pair"],
            "direction": r["direction"],
            "confidence": r["confidence"],
            "feature_values": json.loads(r["feature_values"]) if r["feature_values"] else {},
            "feature_contributions": json.loads(r["feature_contributions"]) if r["feature_contributions"] else {},
            "top_bullish": json.loads(r["top_bullish"]) if r["top_bullish"] else [],
            "top_bearish": json.loads(r["top_bearish"]) if r["top_bearish"] else [],
            "recommended_action": r["recommended_action"],
            "recommended_size_pct": r["recommended_size_pct"],
            "actual_outcome": r["actual_outcome"],
            "actual_price_change": r["actual_price_change"],
        }
        for r in rows
    ])


# ---------- /api/ml/accuracy ----------

@app.route("/api/ml/accuracy")
def api_ml_accuracy():
    """Return ML prediction accuracy stats."""
    pair = request.args.get("pair")

    conn = get_db()

    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ml_predictions'"
    ).fetchone()
    if not table_check:
        conn.close()
        return jsonify({"total": 0, "evaluated": 0, "correct": 0, "accuracy": 0})

    if pair:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM ml_predictions WHERE pair = ?", (pair,)
        ).fetchone()["cnt"]
        evaluated = conn.execute(
            "SELECT COUNT(*) as cnt FROM ml_predictions WHERE pair = ? AND actual_outcome IS NOT NULL",
            (pair,),
        ).fetchone()["cnt"]
        # "correct" = predicted direction matches actual outcome
        correct = conn.execute(
            """SELECT COUNT(*) as cnt FROM ml_predictions
               WHERE pair = ? AND actual_outcome IS NOT NULL
               AND direction = actual_outcome""",
            (pair,),
        ).fetchone()["cnt"]
    else:
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM ml_predictions"
        ).fetchone()["cnt"]
        evaluated = conn.execute(
            "SELECT COUNT(*) as cnt FROM ml_predictions WHERE actual_outcome IS NOT NULL"
        ).fetchone()["cnt"]
        correct = conn.execute(
            """SELECT COUNT(*) as cnt FROM ml_predictions
               WHERE actual_outcome IS NOT NULL
               AND direction = actual_outcome"""
        ).fetchone()["cnt"]

    conn.close()

    accuracy = (correct / evaluated * 100) if evaluated > 0 else 0

    return jsonify({
        "total": total,
        "evaluated": evaluated,
        "correct": correct,
        "accuracy": round(accuracy, 1),
    })


# ---------- /api/ml/model-info ----------

@app.route("/api/ml/model-info")
def api_ml_model_info():
    """Return model metadata for all pairs with trained models."""
    models_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models")
    if not os.path.exists(models_dir):
        return jsonify([])

    models = []
    seen_pairs = set()
    for f in os.listdir(models_dir):
        # Prefer new format (_latest_meta.json), fall back to legacy (_metadata.json)
        if not (f.endswith("_latest_meta.json") or f.endswith("_metadata.json")):
            continue
        try:
            with open(os.path.join(models_dir, f)) as fp:
                meta = json.load(fp)
            pair = meta.get("pair", "")
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            # New format already includes feature_importance; legacy needs separate file
            if "feature_importance" not in meta:
                imp_path = os.path.join(models_dir, f.replace("_metadata.json", "_importance.json"))
                if os.path.exists(imp_path):
                    with open(imp_path) as fp:
                        meta["feature_importance"] = json.load(fp)

            # Add computed fields for dashboard
            trained_at = meta.get("trained_at", "")
            if trained_at:
                from datetime import datetime as _dt
                try:
                    age_h = (_dt.now() - _dt.fromisoformat(trained_at)).total_seconds() / 3600
                    meta["age_hours"] = round(age_h, 1)
                    expiry = 48  # default expiration hours
                    meta["next_retrain_hours"] = round(max(0, expiry - age_h), 1)
                    meta["model_health"] = "expired" if age_h > expiry else "healthy"
                except Exception:
                    pass
            meta.setdefault("feature_count", len(meta.get("feature_names", [])))
            meta.setdefault("validation_rmse", meta.get("validation_auc", 0))
            meta.setdefault("validation_r2", 0)

            # Trim feature importance to top 20 for API payload size
            imp = meta.get("feature_importance", {})
            if len(imp) > 20:
                meta["feature_importance"] = dict(sorted(imp.items(), key=lambda x: -x[1])[:20])

            models.append(meta)
        except Exception:
            pass

    return jsonify(models)


# ---------- /api/volatility ----------

@app.route("/api/volatility/predictions")
def api_vol_predictions():
    """Return recent volatility predictions."""
    pair = request.args.get("pair")
    limit = int(request.args.get("limit", 50))

    conn = get_db()

    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='vol_predictions'"
    ).fetchone()
    if not table_check:
        conn.close()
        return jsonify([])

    if pair:
        rows = conn.execute(
            """SELECT id, timestamp, pair, predicted_vol_12h, current_vol_12h,
                      vol_30d_avg, vol_regime, spacing_multiplier,
                      recommended_num_grids, confidence, garch_vol, feature_importance
               FROM vol_predictions WHERE pair = ?
               ORDER BY id DESC LIMIT ?""",
            (pair, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, timestamp, pair, predicted_vol_12h, current_vol_12h,
                      vol_30d_avg, vol_regime, spacing_multiplier,
                      recommended_num_grids, confidence, garch_vol, feature_importance
               FROM vol_predictions
               ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    conn.close()

    return jsonify([
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "pair": r["pair"],
            "predicted_vol_12h": r["predicted_vol_12h"],
            "current_vol_12h": r["current_vol_12h"],
            "vol_30d_avg": r["vol_30d_avg"],
            "vol_regime": r["vol_regime"],
            "spacing_multiplier": r["spacing_multiplier"],
            "recommended_num_grids": r["recommended_num_grids"],
            "confidence": r["confidence"],
            "garch_vol": r["garch_vol"],
            "feature_importance": json.loads(r["feature_importance"]) if r["feature_importance"] else {},
        }
        for r in rows
    ])


@app.route("/api/volatility/latest")
def api_vol_latest():
    """Return the latest volatility prediction per pair."""
    conn = get_db()

    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='vol_predictions'"
    ).fetchone()
    if not table_check:
        conn.close()
        return jsonify([])

    pairs = _get_active_pairs(conn)
    result = []
    for pair in pairs:
        row = conn.execute(
            """SELECT id, timestamp, pair, predicted_vol_12h, current_vol_12h,
                      vol_30d_avg, vol_regime, spacing_multiplier,
                      recommended_num_grids, confidence, garch_vol, feature_importance
               FROM vol_predictions WHERE pair = ?
               ORDER BY id DESC LIMIT 1""",
            (pair,),
        ).fetchone()
        if row:
            result.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "pair": row["pair"],
                "predicted_vol_12h": row["predicted_vol_12h"],
                "current_vol_12h": row["current_vol_12h"],
                "vol_30d_avg": row["vol_30d_avg"],
                "vol_regime": row["vol_regime"],
                "spacing_multiplier": row["spacing_multiplier"],
                "recommended_num_grids": row["recommended_num_grids"],
                "confidence": row["confidence"],
                "garch_vol": row["garch_vol"],
                "feature_importance": json.loads(row["feature_importance"]) if row["feature_importance"] else {},
            })

    conn.close()
    return jsonify(result)


# ---------- /api/self-check ----------

@app.route("/api/self-check")
def api_self_check():
    """Return comprehensive self-check data for the dashboard."""
    conn = get_db()
    result = {}

    # --- Vol accuracy (last 24h and 7d) ---
    _ensure_table(conn, "vol_accuracy")
    for label, hours in [("24h", 24), ("7d", 168)]:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            "SELECT predicted_vol, actual_vol, error_pct FROM vol_accuracy WHERE timestamp >= ?",
            (cutoff,),
        ).fetchall()
        if rows:
            errors = [r["error_pct"] for r in rows]
            avg_error = sum(errors) / len(errors)
            result[f"vol_accuracy_{label}"] = {
                "count": len(rows),
                "avg_error_pct": round(avg_error, 1),
                "min_error_pct": round(min(errors), 1),
                "max_error_pct": round(max(errors), 1),
            }
        else:
            result[f"vol_accuracy_{label}"] = {"count": 0, "avg_error_pct": 0, "min_error_pct": 0, "max_error_pct": 0}

    # --- Grid performance by spacing level ---
    _ensure_table(conn, "grid_cycles")
    spacing_rows = conn.execute(
        """SELECT vol_regime, spacing_multiplier,
                  COUNT(*) as cycles, SUM(pnl_usd) as total_pnl,
                  AVG(pnl_usd) as avg_pnl, AVG(spacing_pct) as avg_spacing
           FROM grid_cycles
           GROUP BY vol_regime
           ORDER BY total_pnl DESC"""
    ).fetchall()
    result["grid_performance"] = [
        {
            "vol_regime": r["vol_regime"] or "unknown",
            "avg_spacing_mult": round(r["spacing_multiplier"] or 1.0, 2),
            "cycles": r["cycles"],
            "total_pnl": round(r["total_pnl"] or 0, 2),
            "avg_pnl": round(r["avg_pnl"] or 0, 4),
            "avg_spacing_pct": round(r["avg_spacing"] or 0, 2),
        }
        for r in spacing_rows
    ]

    # --- Consecutive winning/losing days ---
    day_rows = conn.execute(
        """SELECT DATE(timestamp) as day, SUM(pnl_usd) as day_pnl
           FROM grid_cycles
           GROUP BY DATE(timestamp)
           ORDER BY DATE(timestamp) DESC
           LIMIT 30"""
    ).fetchall()
    streak_type = ""
    streak_count = 0
    for r in day_rows:
        pnl = r["day_pnl"] or 0
        day_is_win = pnl > 0
        if streak_count == 0:
            streak_type = "winning" if day_is_win else "losing"
            streak_count = 1
        elif (day_is_win and streak_type == "winning") or (not day_is_win and streak_type == "losing"):
            streak_count += 1
        else:
            break
    result["streak"] = {"type": streak_type or "none", "days": streak_count}

    # --- Self-check events (auto-adjustments) ---
    _ensure_table(conn, "self_check_log")
    events = conn.execute(
        "SELECT timestamp, event_type, details FROM self_check_log ORDER BY id DESC LIMIT 20"
    ).fetchall()
    result["events"] = [
        {"timestamp": r["timestamp"], "event_type": r["event_type"], "details": r["details"]}
        for r in events
    ]

    # --- Trading pause status ---
    # Check for most recent pause event
    pause_event = conn.execute(
        """SELECT timestamp, event_type, details FROM self_check_log
           WHERE event_type LIKE '%_loss_pause'
           ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    if pause_event:
        result["trading_paused"] = {
            "paused": True,
            "reason": pause_event["details"],
            "since": pause_event["timestamp"],
        }
    else:
        result["trading_paused"] = {"paused": False, "reason": "", "since": ""}

    # --- Daily P&L ---
    today = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
    _ensure_table(conn, "equity_snapshots")
    day_start = conn.execute(
        "SELECT equity FROM equity_snapshots WHERE timestamp >= ? ORDER BY id ASC LIMIT 1",
        (today,),
    ).fetchone()
    day_latest = conn.execute(
        "SELECT equity FROM equity_snapshots WHERE timestamp >= ? ORDER BY id DESC LIMIT 1",
        (today,),
    ).fetchone()
    if day_start and day_latest:
        result["daily_pnl"] = round(day_latest["equity"] - day_start["equity"], 2)
    else:
        result["daily_pnl"] = 0

    # --- Weekly P&L ---
    week_start = (datetime.now() - timedelta(days=7)).isoformat()
    wk_start_row = conn.execute(
        "SELECT equity FROM equity_snapshots WHERE timestamp >= ? ORDER BY id ASC LIMIT 1",
        (week_start,),
    ).fetchone()
    wk_latest = conn.execute(
        "SELECT equity FROM equity_snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if wk_start_row and wk_latest:
        result["weekly_pnl"] = round(wk_latest["equity"] - wk_start_row["equity"], 2)
    else:
        result["weekly_pnl"] = 0

    conn.close()

    # Add human-readable summary
    result["summary"] = generate_health_summary(result)

    return jsonify(result)


def _ensure_table(conn, table_name: str) -> bool:
    """Check if a table exists, return True if it does."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


# ---------- /api/pair-scans ----------

@app.route("/api/pair-scans")
def api_pair_scans():
    """Return recent pair scan results."""
    limit = int(request.args.get("limit", 10))

    conn = get_db()

    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pair_scans'"
    ).fetchone()
    if not table_check:
        conn.close()
        return jsonify([])

    rows = conn.execute(
        """SELECT id, timestamp, scan_type, total_pairs_scanned,
                  results, selected_pairs, swapped_out, swapped_in
           FROM pair_scans
           ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()

    return jsonify([
        {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "scan_type": r["scan_type"],
            "total_pairs_scanned": r["total_pairs_scanned"],
            "results": json.loads(r["results"]) if r["results"] else [],
            "selected_pairs": json.loads(r["selected_pairs"]) if r["selected_pairs"] else [],
            "swapped_out": json.loads(r["swapped_out"]) if r["swapped_out"] else [],
            "swapped_in": json.loads(r["swapped_in"]) if r["swapped_in"] else [],
        }
        for r in rows
    ])


# ---------- /api/pair-scans/latest ----------

@app.route("/api/pair-scans/latest")
def api_pair_scans_latest():
    """Return the most recent pair scan result."""
    conn = get_db()

    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pair_scans'"
    ).fetchone()
    if not table_check:
        conn.close()
        return jsonify(None)

    row = conn.execute(
        """SELECT id, timestamp, scan_type, total_pairs_scanned,
                  results, selected_pairs, swapped_out, swapped_in
           FROM pair_scans
           ORDER BY id DESC LIMIT 1"""
    ).fetchone()
    conn.close()

    if not row:
        return jsonify(None)

    return jsonify({
        "id": row["id"],
        "timestamp": row["timestamp"],
        "scan_type": row["scan_type"],
        "total_pairs_scanned": row["total_pairs_scanned"],
        "results": json.loads(row["results"]) if row["results"] else [],
        "selected_pairs": json.loads(row["selected_pairs"]) if row["selected_pairs"] else [],
        "swapped_out": json.loads(row["swapped_out"]) if row["swapped_out"] else [],
        "swapped_in": json.loads(row["swapped_in"]) if row["swapped_in"] else [],
    })


# ---------- /api/pair-scans/progress ----------

SCAN_PROGRESS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scan_progress.json")

@app.route("/api/pair-scans/progress")
def api_pair_scans_progress():
    """Return live scan progress from the pair selector."""
    try:
        with open(SCAN_PROGRESS_PATH) as f:
            return jsonify(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({
            "scanning": False,
            "total_pairs": 0,
            "scanned": 0,
            "elapsed_seconds": 0,
            "estimated_remaining": 0,
        })


# ---------- /api/orderbook-check ----------

BOOK_URL = "https://api.coinbase.com/api/v3/brokerage/market/product_book"

@app.route("/api/orderbook-check")
def api_orderbook_check():
    """Check order book depth and spread for given pairs."""
    import requests as req

    pairs_param = request.args.get("pairs", "")
    if not pairs_param:
        # Default to latest scan's selected pairs
        conn = get_db()
        row = conn.execute(
            "SELECT selected_pairs FROM pair_scans ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row and row["selected_pairs"]:
            selected = json.loads(row["selected_pairs"])
            pairs_param = ",".join(p["pair"] if isinstance(p, dict) else p for p in selected)

    if not pairs_param:
        return jsonify([])

    pairs = [p.strip() for p in pairs_param.split(",") if p.strip()]
    results = []

    for pair in pairs:
        try:
            resp = req.get(BOOK_URL, params={"product_id": pair, "limit": 50}, timeout=10)
            resp.raise_for_status()
            pb = resp.json().get("pricebook", {})
            bids = [(float(b["price"]), float(b["size"])) for b in pb.get("bids", [])]
            asks = [(float(a["price"]), float(a["size"])) for a in pb.get("asks", [])]

            best_bid = bids[0][0] if bids else 0
            best_ask = asks[0][0] if asks else 0
            mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0

            spread_pct = ((best_ask - best_bid) / mid * 100) if mid else 0
            bid_depth = sum(p * s for p, s in bids if p >= mid * 0.98)
            ask_depth = sum(p * s for p, s in asks if p <= mid * 1.02)

            flags = []
            if spread_pct > 1.0:
                flags.append(f"spread {spread_pct:.1f}% > 1%")
            if bid_depth < 500:
                flags.append(f"bid depth ${bid_depth:.0f} < $500")
            if ask_depth < 500:
                flags.append(f"ask depth ${ask_depth:.0f} < $500")

            results.append({
                "pair": pair,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "mid": round(mid, 8),
                "spread_pct": round(spread_pct, 2),
                "bid_depth_2pct": round(bid_depth, 2),
                "ask_depth_2pct": round(ask_depth, 2),
                "low_liquidity": len(flags) > 0,
                "flags": flags,
            })
        except Exception as e:
            results.append({
                "pair": pair,
                "error": str(e),
                "low_liquidity": True,
                "flags": ["failed to fetch order book"],
            })

    return jsonify(results)


# ---------- /api/pnl-attribution ----------

@app.route("/api/pnl-attribution")
def api_pnl_attribution():
    """Break down P&L by source: legacy pairs vs auto-selected pairs."""
    conn = get_db()

    # Get the latest scan's selected pairs
    auto_pairs = set()
    table_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pair_scans'"
    ).fetchone()
    if table_check:
        row = conn.execute(
            "SELECT selected_pairs FROM pair_scans ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row and row["selected_pairs"]:
            selected = json.loads(row["selected_pairs"])
            auto_pairs = {p["pair"] if isinstance(p, dict) else p for p in selected}

    # Get all trades grouped by pair
    trades_check = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sim_trades'"
    ).fetchone()
    if not trades_check:
        conn.close()
        return jsonify({"legacy": {}, "auto_selected": {}, "auto_pairs": list(auto_pairs)})

    rows = conn.execute(
        """SELECT pair, side, price, amount, cost_usd, fee
           FROM sim_trades ORDER BY id ASC"""
    ).fetchall()
    conn.close()

    # Calculate per-pair P&L using cost basis tracking
    pair_stats: dict = {}
    pair_cost_basis: dict = {}  # pair -> list of (amount, price) buys
    for r in rows:
        pair = r["pair"]
        if pair not in pair_stats:
            pair_stats[pair] = {
                "pair": pair,
                "trades": 0,
                "buys": 0,
                "sells": 0,
                "total_cost": 0.0,
                "total_revenue": 0.0,
                "total_fees": 0.0,
                "realized_pnl": 0.0,
            }
            pair_cost_basis[pair] = []
        ps = pair_stats[pair]
        ps["trades"] += 1
        fee = r["fee"] or 0
        ps["total_fees"] += fee
        if r["side"] == "buy":
            ps["buys"] += 1
            ps["total_cost"] += (r["cost_usd"] or 0)
            pair_cost_basis[pair].append((r["amount"] or 0, r["price"] or 0))
        else:
            ps["sells"] += 1
            revenue = r["cost_usd"] or 0
            ps["total_revenue"] += revenue
            # FIFO cost basis for realized P&L
            sell_amount = r["amount"] or 0
            cost = 0.0
            while sell_amount > 0 and pair_cost_basis[pair]:
                buy_amt, buy_price = pair_cost_basis[pair][0]
                used = min(sell_amount, buy_amt)
                cost += used * buy_price
                sell_amount -= used
                if used >= buy_amt:
                    pair_cost_basis[pair].pop(0)
                else:
                    pair_cost_basis[pair][0] = (buy_amt - used, buy_price)
            ps["realized_pnl"] += revenue - cost - fee

    legacy = {}
    auto = {}
    for pair, stats in pair_stats.items():
        stats["realized_pnl"] = round(stats["realized_pnl"], 2)
        stats["total_fees"] = round(stats["total_fees"], 2)
        stats["source"] = "auto_selected" if pair in auto_pairs else "legacy"
        if pair in auto_pairs:
            auto[pair] = stats
        else:
            legacy[pair] = stats

    legacy_total = sum(s["realized_pnl"] for s in legacy.values())
    auto_total = sum(s["realized_pnl"] for s in auto.values())

    return jsonify({
        "legacy": legacy,
        "legacy_total_pnl": round(legacy_total, 2),
        "auto_selected": auto,
        "auto_total_pnl": round(auto_total, 2),
        "auto_pairs": list(auto_pairs),
    })


# ---------- Health & Update ----------

import subprocess
import time as _time

_app_start_time = _time.time()
_last_update_check: str | None = None
_update_status = "unknown"


# ---------- /api/events ----------

@app.route("/api/events")
def api_events():
    """Return recent bot events for the activity feed."""
    limit = min(int(request.args.get("limit", 50)), 500)
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


@app.route("/api/adaptations")
def api_adaptations():
    """Return recent learning/adaptation events."""
    limit = min(int(request.args.get("limit", 50)), 200)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_table(conn, "adaptations")
        rows = conn.execute(
            "SELECT * FROM adaptations ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception:
        return jsonify([])
    finally:
        conn.close()


@app.route("/api/health")
def api_health():
    """Health check for Docker / ZimaOS monitoring."""
    global _last_update_check, _update_status
    uptime = int(_time.time() - _app_start_time)

    # Bot status from DB
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT COUNT(*) as cnt, MAX(timestamp) as last_ts FROM trades"
        ).fetchone()
        total_trades = row["cnt"] if row else 0
        last_trade = row["last_ts"] if row else None
        conn.close()
    except Exception:
        total_trades = 0
        last_trade = None

    # Active pairs from status endpoint logic
    active_pairs = []
    model_status = {}
    models_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models")
    if os.path.isdir(models_dir):
        for f in os.listdir(models_dir):
            if f.endswith("_latest_meta.json"):
                pair = f.replace("_latest_meta.json", "").replace("_", "-")
                model_status[pair] = "active"
                active_pairs.append(pair)

    # Equity from latest equity snapshot
    equity, pnl = 0.0, 0.0
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT equity, balance_usd, positions_value FROM equity_curve ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if row:
            equity = row["equity"]
            starting = 3000  # default
            pnl = equity - starting
        conn.close()
    except Exception:
        pass

    return jsonify({
        "status": "ok",
        "bot_running": True,
        "uptime_seconds": uptime,
        "last_trade": last_trade,
        "active_pairs": active_pairs,
        "total_trades": total_trades,
        "equity": round(equity, 2),
        "pnl": round(pnl, 2),
        "last_update_check": _last_update_check,
        "update_status": _update_status,
        "model_status": model_status,
        "auth_enabled": AUTH_ENABLED,
    })


@app.route("/api/update", methods=["POST"])
def api_trigger_update():
    """Manually trigger git update check from the dashboard."""
    global _last_update_check, _update_status
    try:
        script = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "auto_update.sh")
        if not os.path.exists(script):
            return jsonify({"status": "error", "output": "auto_update.sh not found"}), 404

        result = subprocess.run(
            ["bash", script],
            capture_output=True, text=True, timeout=120,
            env={**os.environ},
            cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        )
        output = (result.stdout + result.stderr).strip()
        _last_update_check = datetime.now().isoformat()

        if "No updates available" in output:
            _update_status = "up to date"
        elif "Tests passed" in output:
            _update_status = "updated and restarting"
        elif "Tests FAILED" in output:
            _update_status = "update rolled back (tests failed)"
        else:
            _update_status = "checked"

        return jsonify({"status": "ok", "output": output, "update_status": _update_status})
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "output": "Update check timed out"}), 504
    except Exception as e:
        return jsonify({"status": "error", "output": str(e)}), 500


# ---------- /api/reset-data ----------

@app.route("/api/reset-data", methods=["POST"])
def api_reset_data():
    """Clear all trading/ML data for a clean $3,000 restart. Keeps candles."""
    try:
        conn = sqlite3.connect(DB_PATH)
        tables = [
            "sim_trades",
            "equity_snapshots",
            "bot_events",
            "ml_predictions",
            "grid_cycles",
            "vol_predictions",
            "vol_accuracy",
            "pair_scans",
            "adaptations",
            "self_checks",
        ]
        deleted = {}
        for table in tables:
            try:
                cur = conn.execute(f"DELETE FROM {table}")
                deleted[table] = cur.rowcount
            except Exception:
                deleted[table] = 0
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "deleted": deleted, "balance": 3000.0})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/download-db")
def api_download_db():
    """Download the SQLite database file."""
    db = os.path.abspath(DB_PATH)
    if not os.path.isfile(db):
        return jsonify({"status": "error", "message": "Database not found"}), 404
    return send_file(db, as_attachment=True, download_name="candles.db")


@app.route("/api/momentum/reset", methods=["POST"])
def api_momentum_reset():
    """Clear momentum trading data for a clean restart. Keeps candles."""
    try:
        conn = sqlite3.connect(DB_PATH)
        tables = ["momentum_trades", "momentum_equity", "momentum_events"]
        deleted = {}
        for table in tables:
            try:
                cur = conn.execute(f"DELETE FROM {table}")
                deleted[table] = cur.rowcount
            except Exception:
                deleted[table] = 0
        conn.commit()
        conn.close()

        # Clear progress file
        prog_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "momentum_progress.json")
        try:
            os.remove(prog_path)
        except Exception:
            pass

        # Write reset flag so the engine process reinitializes in-memory state
        reset_flag = os.path.join(os.path.dirname(__file__), "..", "..", "data", "momentum_reset.flag")
        try:
            with open(reset_flag, "w") as f:
                f.write("reset")
        except Exception:
            pass

        return jsonify({"status": "ok", "deleted": deleted})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/momentum/sell", methods=["POST"])
def api_momentum_sell():
    """Manual sell: write a flag file that the engine picks up on next poll."""
    data = request.get_json(silent=True) or {}
    pair = data.get("pair", "")
    if not pair:
        return jsonify({"status": "error", "message": "Missing pair"}), 400

    sell_flag = os.path.join(os.path.dirname(__file__), "..", "..", "data", "momentum_sell.flag")
    try:
        with open(sell_flag, "w") as f:
            f.write(pair)
        return jsonify({"status": "ok", "pair": pair})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/momentum/skip-cooldown", methods=["POST"])
def api_momentum_skip_cooldown():
    """Skip exit cooldown: write a flag file that the engine picks up on next poll."""
    flag_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "momentum_skip_cooldown.flag")
    try:
        with open(flag_path, "w") as f:
            f.write("skip")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------- Momentum Rotation Engine endpoints ----------

@app.route("/api/momentum/status")
def api_momentum_status():
    """Full status of the momentum rotation engine."""
    conn = get_db()

    # Latest equity snapshot
    try:
        eq_row = conn.execute(
            "SELECT * FROM momentum_equity ORDER BY id DESC LIMIT 1"
        ).fetchone()
    except Exception:
        conn.close()
        return jsonify({"error": "Momentum engine not active", "enabled": False})

    # Starting balance from config
    starting_balance = 3000.0
    try:
        import yaml
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "config", "bot_config.yaml")) as f:
            cfg = yaml.safe_load(f)
        starting_balance = float(cfg.get("momentum_rotation", {}).get("allocation_usd", 3000))
    except Exception:
        pass

    if not eq_row:
        conn.close()
        scanner_info = None
        try:
            scan_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "momentum_scan.json")
            if os.path.exists(scan_path):
                with open(scan_path) as f:
                    scanner_info = json.load(f)
        except Exception:
            pass
        return jsonify({
            "enabled": True, "status": "warming_up",
            "equity": starting_balance, "cash": starting_balance,
            "positions_value": 0, "pnl": 0, "pnl_pct": 0,
            "starting_balance": starting_balance,
            "trade_count": 0, "holdings": [],
            "scanner": scanner_info,
        })

    equity = eq_row["equity"]
    cash = eq_row["cash"]
    positions_value = eq_row["positions_value"]
    pnl = equity - starting_balance
    pnl_pct = (pnl / starting_balance) * 100 if starting_balance > 0 else 0

    # Holdings
    holdings = []
    try:
        holdings = json.loads(eq_row["holdings"] or "[]")
    except Exception:
        pass

    # Trade count
    trade_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM momentum_trades"
    ).fetchone()["cnt"]

    conn.close()

    # Scanner info (from persisted file)
    scanner_info = None
    try:
        scan_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "momentum_scan.json")
        if os.path.exists(scan_path):
            with open(scan_path) as f:
                scanner_info = json.load(f)
    except Exception:
        pass

    # Read live engine state (regime, cooldown, warmup, etc.)
    engine_state = {}
    try:
        state_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "momentum_status.json")
        if os.path.exists(state_path):
            with open(state_path) as f:
                engine_state = json.load(f)
    except Exception:
        pass

    result = {
        "enabled": True,
        "status": eq_row["status"],
        "equity": equity,
        "cash": cash,
        "positions_value": positions_value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "starting_balance": starting_balance,
        "trade_count": trade_count,
        "holdings": holdings,
        "scanner": scanner_info,
    }

    # Merge engine state fields the dashboard needs
    for key in ("regime_bullish", "regime_state", "regime_hysteresis",
                "exit_cooldown_remaining", "hours_in_position",
                "warmup_done", "was_cash", "next_rebal_hours",
                "btc_price", "btc_ma", "entry_rejections"):
        if key in engine_state:
            result[key] = engine_state[key]

    return jsonify(result)


@app.route("/api/momentum/equity")
def api_momentum_equity():
    """Equity history for the momentum engine."""
    hours = int(request.args.get("hours", 72))
    start = (datetime.now() - timedelta(hours=hours)).isoformat()

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT timestamp, equity, cash, positions_value, status
               FROM momentum_equity WHERE timestamp >= ?
               ORDER BY timestamp ASC""",
            (start,),
        ).fetchall()
    except Exception:
        conn.close()
        return jsonify([])

    conn.close()
    return jsonify([
        {
            "time": row["timestamp"],
            "equity": row["equity"],
            "cash": row["cash"],
            "positions_value": row["positions_value"],
            "status": row["status"],
        }
        for row in rows
    ])


@app.route("/api/momentum/trades")
def api_momentum_trades():
    """Recent momentum rotation trades with P&L computed for sells."""
    limit = int(request.args.get("limit", 50))

    conn = get_db()
    try:
        # Get all trades to compute P&L (need full history for matching)
        all_rows = conn.execute(
            """SELECT id, timestamp, pair, side, price, amount, cost_usd, fee, reason
               FROM momentum_trades ORDER BY id ASC"""
        ).fetchall()
    except Exception:
        conn.close()
        return jsonify([])
    conn.close()

    # Match buys to sells for P&L and status
    # Track open buy cost basis per pair (FIFO)
    buy_costs: dict[str, list[dict]] = {}  # pair -> [{id, cost_usd, amount}]
    sold_buy_ids: set[int] = set()  # buy trade IDs that have been closed
    results = []

    for row in all_rows:
        r = dict(row)
        if r["side"] == "buy":
            buy_costs.setdefault(r["pair"], []).append({
                "id": r["id"], "cost_usd": r["cost_usd"], "amount": r["amount"],
            })
            r["net_pnl"] = None
            r["entry_price"] = None
        elif r["side"] == "sell":
            # Find matching buy(s) for this pair
            buys = buy_costs.get(r["pair"], [])
            total_buy_cost = 0.0
            entry_price = None
            if buys:
                # Simple: pop the most recent buy (momentum only holds 1 at a time)
                matched = buys.pop(0)
                total_buy_cost = matched["cost_usd"]
                sold_buy_ids.add(matched["id"])
                entry_price = total_buy_cost / matched["amount"] if matched["amount"] else None
            r["net_pnl"] = r["cost_usd"] - total_buy_cost if total_buy_cost else None
            r["entry_price"] = entry_price
        results.append(r)

    # Mark buys that have been sold
    for r in results:
        if r["side"] == "buy":
            r["closed"] = r["id"] in sold_buy_ids

    # Return most recent first, limited
    results.reverse()
    return jsonify(results[:limit])


@app.route("/api/momentum/events")
def api_momentum_events():
    """Activity log for momentum engine."""
    limit = int(request.args.get("limit", 50))

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT timestamp, event_type, title, detail
               FROM momentum_events ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    except Exception:
        conn.close()
        return jsonify([])

    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/momentum/progress")
def api_momentum_progress():
    """Warmup/scan progress for the momentum engine."""
    prog_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "momentum_progress.json")
    try:
        if os.path.exists(prog_path):
            with open(prog_path) as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify({"step": "unknown", "pct": 0})


@app.route("/api/momentum/accel")
def api_momentum_accel():
    """Compute current acceleration scores for all scanned momentum pairs."""
    # Read scanner pairs
    scan_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "momentum_scan.json")
    try:
        with open(scan_path) as f:
            scan_info = json.load(f)
        pairs = scan_info.get("pairs", [])
    except Exception:
        return jsonify([])

    if not pairs:
        return jsonify([])

    # Compute acceleration from stored candles
    conn = get_db()
    SHORT_LB = 336   # 14 days
    LONG_LB = 720    # 30 days
    scores = []

    for pair in pairs:
        try:
            rows = conn.execute(
                """SELECT open, high, low, close FROM candles
                   WHERE pair=? AND granularity='ONE_HOUR'
                   ORDER BY timestamp DESC LIMIT ?""",
                (pair, LONG_LB + 1),
            ).fetchall()
            if len(rows) < LONG_LB + 1:
                continue
            rows_chron = list(reversed(rows))
            closes = [r["close"] for r in rows_chron]
            cur = closes[-1]
            # Skip sub-penny coins — too noisy for momentum signals
            if cur < 0.01:
                continue
            short_ago = closes[-SHORT_LB]
            long_ago = closes[-LONG_LB]
            if short_ago <= 0 or long_ago <= 0:
                continue
            short_mom = cur / short_ago - 1
            long_mom = cur / long_ago - 1
            accel = short_mom - (long_mom * SHORT_LB / LONG_LB)
            if accel > 0:
                # Entry quality gates
                opens = [r["open"] for r in rows_chron]
                highs = [r["high"] for r in rows_chron]
                lows = [r["low"] for r in rows_chron]

                # Gate 1: green count (>= 2 of last 6)
                green_count = sum(1 for c, o in zip(closes[-6:], opens[-6:]) if c >= o)
                gate_green = green_count >= 2

                # Gate 2: body ratio (>= 0.3 avg of last 3)
                body_ratios = []
                for c, o, h, l in zip(closes[-3:], opens[-3:], highs[-3:], lows[-3:]):
                    rng = h - l
                    body_ratios.append(abs(c - o) / rng if rng > 0 else 0)
                avg_body = sum(body_ratios) / len(body_ratios) if body_ratios else 0.5
                gate_body = avg_body >= 0.3

                # Gate 3: chg_3h not overextended vs ATR
                gate_ext = True
                if len(closes) >= 4 and len(highs) >= 12:
                    chg_3h = (closes[-1] - closes[-4]) / closes[-4] * 100
                    atr_vals = [h - l for h, l in zip(highs[-12:], lows[-12:])]
                    avg_atr = sum(atr_vals) / len(atr_vals)
                    atr_pct = avg_atr / cur * 100 if cur > 0 else 1
                    chg_3h_atr = chg_3h / atr_pct if atr_pct > 0 else 0
                    gate_ext = chg_3h_atr < 3.0
                else:
                    chg_3h_atr = 0

                # Gate 4: ATH proximity (block if within 5% of all-time high)
                ath = max(highs)
                ath_dist = (cur - ath) / ath * 100 if ath > 0 else -100
                gate_ath = ath_dist < -5

                # Gate 5: freshness (block stale momentum above threshold 100+ hours)
                ACCEL_ENTRY = 0.20
                mom_age = 0
                for j in range(len(closes) - 1, max(LONG_LB, len(closes) - 200), -1):
                    if j < LONG_LB or j < SHORT_LB:
                        break
                    sm_j = closes[j] / closes[j - SHORT_LB] - 1
                    lm_j = closes[j] / closes[j - LONG_LB] - 1
                    ac_j = sm_j - (lm_j * SHORT_LB / LONG_LB)
                    if ac_j >= ACCEL_ENTRY:
                        mom_age += 1
                    else:
                        break
                gate_fresh = mom_age < 100

                # Gate 6: time at level (block if stuck in 3% band for 30+ of last 100h)
                time_at_lvl = sum(1 for c in closes[-100:] if abs(c - cur) / cur < 0.03)
                gate_level = time_at_lvl <= 30

                all_pass = gate_green and gate_body and gate_ext and gate_ath and gate_fresh and gate_level

                scores.append({
                    "pair": pair, "accel": round(accel, 4), "price": round(cur, 6),
                    "quality": {
                        "green": gate_green, "greenCount": green_count,
                        "body": gate_body, "bodyRatio": round(avg_body, 2),
                        "ext": gate_ext, "chg3hAtr": round(chg_3h_atr, 1),
                        "pass": all_pass,
                    },
                    "structural": {
                        "ath": gate_ath, "athDist": round(ath_dist, 1),
                        "fresh": gate_fresh, "momAge": mom_age,
                        "level": gate_level, "timeAtLevel": time_at_lvl,
                        "pass": gate_ath and gate_fresh and gate_level,
                    },
                })
        except Exception:
            continue

    conn.close()
    scores.sort(key=lambda s: s["accel"], reverse=True)
    return jsonify(scores[:10])  # top 10


# ---------- Early Momentum Scanner ----------

import threading

_early_scanner = None
_early_scanner_lock = threading.Lock()
_early_scanner_running = False
_early_scanner_last_run = None

def _get_early_scanner():
    global _early_scanner
    if _early_scanner is None:
        try:
            import sys
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            from engine.early_scanner import EarlyScanner
            # Try config file first, then env var
            webhook = os.environ.get("DISCORD_WEBHOOK", "")
            try:
                import yaml
                cfg_path = os.path.join(project_root, "config", "bot_config.yaml")
                with open(cfg_path) as f:
                    cfg = yaml.safe_load(f)
                webhook = cfg.get("early_scanner", {}).get("discord_webhook", "") or webhook
            except Exception:
                pass
            _early_scanner = EarlyScanner(db_path=DB_PATH, discord_webhook=webhook or None)
        except Exception as e:
            import traceback
            print(f"Early scanner init error: {e}")
            traceback.print_exc()
    return _early_scanner

def _run_early_scan():
    global _early_scanner_running, _early_scanner_last_run
    with _early_scanner_lock:
        if _early_scanner_running:
            return
        _early_scanner_running = True
    try:
        scanner = _get_early_scanner()
        if scanner:
            scanner.scan()
            scanner.evaluate_outcomes()
            _early_scanner_last_run = datetime.now().isoformat()
    except Exception as e:
        print(f"Early scanner error: {e}")
    finally:
        _early_scanner_running = False


@app.route("/api/early-scanner/alerts")
def early_scanner_alerts():
    limit = int(request.args.get("limit", 50))
    scanner = _get_early_scanner()
    if not scanner:
        return jsonify([])
    return jsonify(scanner.get_recent_alerts(limit))


@app.route("/api/early-scanner/stats")
def early_scanner_stats():
    scanner = _get_early_scanner()
    if not scanner:
        return jsonify({"total_alerts": 0, "alerts_24h": 0, "evaluated": 0, "wins": 0, "win_rate": 0})
    stats = scanner.get_stats()
    stats["running"] = _early_scanner_running
    stats["last_run"] = _early_scanner_last_run
    return jsonify(stats)


@app.route("/api/early-scanner/scan", methods=["POST"])
def early_scanner_trigger():
    """Trigger a manual scan."""
    if _early_scanner_running:
        return jsonify({"status": "already_running"})
    thread = threading.Thread(target=_run_early_scan, daemon=True)
    thread.start()
    return jsonify({"status": "started"})


def _start_auto_scan_loop(interval_minutes=10):
    """Background loop that runs the early scanner every N minutes."""
    import time as _t
    def loop():
        _t.sleep(30)  # initial delay to let the server start
        while True:
            try:
                _run_early_scan()
            except Exception as e:
                print(f"Auto-scan error: {e}")
            _t.sleep(interval_minutes * 60)
    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

# Start auto-scan on server boot (only in the reloader child process to avoid double-start)
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
    _start_auto_scan_loop(10)


# ---------- Auth endpoints ----------

@app.route("/api/auth/setup", methods=["GET"])
def auth_setup():
    """Generate TOTP secret and QR code for first-time setup."""
    if os.path.exists(TOTP_SECRET_PATH):
        return jsonify({"error": "already_setup"}), 400
    secret = pyotp.random_base32()
    app.config["_pending_totp_secret"] = secret
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name="CryptoBot", issuer_name="CryptoBot Dashboard")
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({"secret": secret, "qr_png": qr_b64})


@app.route("/api/auth/setup/confirm", methods=["POST"])
def auth_setup_confirm():
    """Verify TOTP code and save secret permanently."""
    secret = app.config.get("_pending_totp_secret")
    if not secret:
        return jsonify({"error": "no_pending_setup"}), 400
    code = (request.json or {}).get("code", "")
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "invalid_code"}), 401
    with open(TOTP_SECRET_PATH, "w") as f:
        f.write(secret)
    app.config.pop("_pending_totp_secret", None)
    resp = jsonify({"status": "ok"})
    resp.set_cookie("bot_session", _create_session_token(),
                     max_age=30 * 86400, httponly=True, samesite="Lax")
    return resp


@app.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    """Verify TOTP code and create session."""
    if not os.path.exists(TOTP_SECRET_PATH):
        return jsonify({"error": "setup_required"}), 401
    with open(TOTP_SECRET_PATH, "r") as f:
        secret = f.read().strip()
    code = (request.json or {}).get("code", "")
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "invalid_code"}), 401
    resp = jsonify({"status": "ok"})
    resp.set_cookie("bot_session", _create_session_token(),
                     max_age=30 * 86400, httponly=True, samesite="Lax")
    return resp


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Clear session cookie."""
    resp = jsonify({"status": "ok"})
    resp.delete_cookie("bot_session")
    return resp


# ---------- Static file serving ----------

@app.after_request
def add_no_cache_headers(response):
    """Prevent browsers from serving stale frontend files."""
    if "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.route("/")
def serve_index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:path>")
def serve_frontend(path):
    """Serve Angular SPA — static files or index.html for client-side routes."""
    full = os.path.join(STATIC_DIR, path)
    if os.path.isfile(full):
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


if __name__ == "__main__":
    print(f"\n  CryptoBot Dashboard")
    print(f"  DB: {os.path.abspath(DB_PATH)}")
    print(f"  UI: {os.path.abspath(STATIC_DIR)}")
    print(f"  Open http://localhost:5001\n")
    app.run(host="0.0.0.0", port=5001, debug=True)
