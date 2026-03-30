"""Flask REST API for CryptoBot trading dashboard.

Reads from data/candles.db (read-only) and serves candle, trade,
equity, indicator, and status data to the Angular frontend.

Usage:
    py dashboard/api/app.py
    # Serves on http://localhost:5001
"""

import os
import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from ta.trend import ADXIndicator, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.momentum import RSIIndicator
from ta.volume import OnBalanceVolumeIndicator

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "ui", "dist", "ui", "browser")

app = Flask(__name__, static_folder=None)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "candles.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
    if pair:
        rows = conn.execute(
            """SELECT id, timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason
               FROM sim_trades WHERE pair = ? ORDER BY id DESC LIMIT ?""",
            (pair, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason
               FROM sim_trades ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    conn.close()

    return jsonify([
        {
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
        }
        for row in rows
    ])


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
    equity = eq_row["equity"] if eq_row else starting_balance
    pnl = equity - starting_balance
    pnl_pct = (pnl / starting_balance) * 100 if starting_balance > 0 else 0.0

    # Per-pair latest prices and trade counts
    pairs_info = []
    for pair in ["DOGE-USD", "ETH-USD", "PEPE-USD"]:
        price_row = conn.execute(
            """SELECT close, timestamp FROM candles
               WHERE pair = ? ORDER BY timestamp DESC LIMIT 1""",
            (pair,),
        ).fetchone()

        trade_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM sim_trades WHERE pair = ?",
            (pair,),
        ).fetchone()["cnt"]

        pairs_info.append({
            "pair": pair,
            "price": price_row["close"] if price_row else 0,
            "last_candle": price_row["timestamp"] if price_row else None,
            "trade_count": trade_count,
            "regime": _detect_regime_for_pair(conn, pair),
        })

    # Last trade
    last_trade_row = conn.execute(
        "SELECT timestamp FROM sim_trades ORDER BY id DESC LIMIT 1"
    ).fetchone()

    conn.close()

    return jsonify({
        "equity": equity,
        "balance_usd": eq_row["balance_usd"] if eq_row else starting_balance,
        "positions_value": eq_row["positions_value"] if eq_row else 0,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "starting_balance": starting_balance,
        "total_trades": sum(p["trade_count"] for p in pairs_info),
        "last_trade_time": last_trade_row["timestamp"] if last_trade_row else None,
        "pairs": pairs_info,
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
    pair = request.args.get("pair", "DOGE-USD")

    # Read the pair's config to get grid params
    import yaml
    pair_key = pair.split("-")[0].lower()
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "strategies", f"{pair_key}.yaml")

    if not os.path.exists(config_path):
        return jsonify({"levels": [], "error": "Config not found"})

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Auto-fit from recent candles
    conn = get_db()
    rows = conn.execute(
        """SELECT high, low FROM candles
           WHERE pair = ? AND granularity = 'ONE_HOUR'
           ORDER BY timestamp DESC LIMIT 720""",
        (pair,),
    ).fetchall()
    conn.close()

    if rows:
        lows = [r["low"] for r in rows]
        highs = [r["high"] for r in rows]
        lower = min(lows) * 0.95
        upper = max(highs) * 1.05
    else:
        lower = config.get("lower_price", 0)
        upper = config.get("upper_price", 1)

    num_grids = config.get("num_grids", 10)
    step = (upper - lower) / num_grids

    levels = []
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
        "levels": levels,
    })


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
