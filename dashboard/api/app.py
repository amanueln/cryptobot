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


def _get_active_pairs(conn) -> list[str]:
    """Get all pairs that have trades in the database."""
    rows = conn.execute(
        "SELECT DISTINCT pair FROM sim_trades ORDER BY pair"
    ).fetchall()
    if rows:
        return [r["pair"] for r in rows]
    # Fallback: get pairs from candles table
    rows = conn.execute(
        "SELECT DISTINCT pair FROM candles ORDER BY pair"
    ).fetchall()
    return [r["pair"] for r in rows]


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
            """SELECT id, timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason
               FROM sim_trades WHERE pair = ? ORDER BY id ASC""",
            (pair,),
        ).fetchall()
    else:
        all_rows = conn.execute(
            """SELECT id, timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason
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

            # Revenue is gross (before sell fee); net = revenue - sell_fee - cost_basis
            gross_revenue = sell_qty * row["price"]
            if t["cost_basis"] is not None:
                net_profit = gross_revenue - sell_fee - cost_basis
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
    equity = eq_row["equity"] if eq_row else starting_balance
    pnl = equity - starting_balance
    pnl_pct = (pnl / starting_balance) * 100 if starting_balance > 0 else 0.0

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
    pair = request.args.get("pair", "BTC-USD")
    num_grids = int(request.args.get("grids", 10))

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


# ---------- Static file serving ----------

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
