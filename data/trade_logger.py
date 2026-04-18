from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from exchange.models import Trade


class TradeLogger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    cost_usd REAL NOT NULL,
                    fee REAL NOT NULL,
                    strategy TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    regime TEXT DEFAULT '',
                    adx REAL DEFAULT 0,
                    rsi REAL DEFAULT 0,
                    atr_multiplier REAL DEFAULT 1.0
                )
            """)
            # Migrate existing tables
            for col, typedef in [
                ("regime", "TEXT DEFAULT ''"),
                ("adx", "REAL DEFAULT 0"),
                ("rsi", "REAL DEFAULT 0"),
                ("atr_multiplier", "REAL DEFAULT 1.0"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE sim_trades ADD COLUMN {col} {typedef}")
                except Exception:
                    pass  # Column already exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS equity_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    equity REAL NOT NULL,
                    balance_usd REAL NOT NULL,
                    positions_value REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ml_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    feature_values TEXT NOT NULL,
                    feature_contributions TEXT NOT NULL,
                    top_bullish TEXT NOT NULL,
                    top_bearish TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    recommended_size_pct REAL NOT NULL,
                    actual_outcome TEXT,
                    actual_price_change REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pair_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    scan_type TEXT NOT NULL,
                    total_pairs_scanned INTEGER,
                    results TEXT NOT NULL,
                    selected_pairs TEXT NOT NULL,
                    swapped_out TEXT,
                    swapped_in TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vol_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    predicted_vol_12h REAL NOT NULL,
                    current_vol_12h REAL NOT NULL,
                    vol_30d_avg REAL NOT NULL,
                    vol_regime TEXT NOT NULL,
                    spacing_multiplier REAL NOT NULL,
                    recommended_num_grids INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    garch_vol REAL NOT NULL,
                    feature_importance TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vol_accuracy (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    predicted_vol REAL NOT NULL,
                    actual_vol REAL NOT NULL,
                    error_pct REAL NOT NULL,
                    window_hours INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS grid_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    buy_price REAL NOT NULL,
                    sell_price REAL NOT NULL,
                    amount REAL NOT NULL,
                    pnl_usd REAL NOT NULL,
                    spacing_pct REAL NOT NULL,
                    vol_regime TEXT,
                    spacing_multiplier REAL,
                    hold_seconds INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS self_check_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details TEXT NOT NULL
                )
            """)
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS adaptations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    loop_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    old_value REAL,
                    new_value REAL
                )
            """)
            # --- Momentum rotation engine tables ---
            conn.execute("""
                CREATE TABLE IF NOT EXISTS momentum_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    cost_usd REAL NOT NULL,
                    fee REAL NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS momentum_equity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    equity REAL NOT NULL,
                    cash REAL NOT NULL,
                    positions_value REAL NOT NULL,
                    status TEXT NOT NULL,
                    holdings TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS momentum_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wall_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT,
                    current_price REAL,
                    wall_aware_stop REAL,
                    entry_price REAL,
                    peak_price REAL,
                    wall_price REAL,
                    wall_usd REAL,
                    wall_age_ms INTEGER,
                    book_bids TEXT,
                    book_asks TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS regime_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    btc_price REAL,
                    btc_ma REAL,
                    regime_state TEXT,
                    regime_bullish INTEGER,
                    btc_4h_return REAL,
                    btc_24h_return REAL,
                    scans_pass INTEGER,
                    scans_fail INTEGER,
                    holdings_count INTEGER,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS momentum_gate_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    accel REAL NOT NULL,
                    result TEXT NOT NULL,
                    blocked_by TEXT,
                    green_count INTEGER,
                    body_ratio REAL,
                    chg3h_atr REAL,
                    ath_dist REAL,
                    mom_age INTEGER,
                    time_at_level INTEGER,
                    price REAL,
                    created_at TEXT NOT NULL,
                    price_6h REAL,
                    price_12h REAL,
                    price_24h REAL,
                    price_48h REAL,
                    pnl_6h REAL,
                    pnl_12h REAL,
                    pnl_24h REAL,
                    pnl_48h REAL
                )
            """)
            # Migrate: add follow-up and ranking columns to existing momentum_gate_log
            for col, ctype in [
                ("price_6h", "REAL"), ("price_12h", "REAL"),
                ("price_24h", "REAL"), ("price_48h", "REAL"),
                ("pnl_6h", "REAL"), ("pnl_12h", "REAL"),
                ("pnl_24h", "REAL"), ("pnl_48h", "REAL"),
                ("rank", "INTEGER"), ("picked", "INTEGER"),
                ("reason_not_picked", "TEXT"),
                ("rsi", "REAL"), ("adx", "REAL"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE momentum_gate_log ADD COLUMN {col} {ctype}")
                except Exception:
                    pass  # column already exists
            # Migrate: add exit snapshot columns to momentum_trades
            for col, ctype in [
                ("entry_price", "REAL"),
                ("exit_price", "REAL"),
                ("pnl_pct", "REAL"),
                ("hold_hours", "REAL"),
                ("peak_price", "REAL"),
                ("peak_pnl_pct", "REAL"),
                ("drawdown_from_peak", "REAL"),
                ("trail_stop", "REAL"),
                ("atr_stop", "REAL"),
                ("exit_accel", "REAL"),
                ("exit_reason_detail", "TEXT"),
                ("exit_green_count", "INTEGER"),
                ("exit_body_ratio", "REAL"),
                ("exit_ath_dist", "REAL"),
                ("exit_time_at_level", "INTEGER"),
                ("ticks_since_new_peak", "INTEGER"),
                ("max_adverse_pct", "REAL"),
                ("max_favorable_pct", "REAL"),
                ("trough_price", "REAL"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE momentum_trades ADD COLUMN {col} {ctype}")
                except Exception:
                    pass  # column already exists
            # Migrate: add new columns for regression predictions
            for col, ctype in [
                ("predicted_change_pct", "REAL"),
                ("do_predict", "INTEGER"),
                ("di_value", "REAL"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE ml_predictions ADD COLUMN {col} {ctype}")
                except sqlite3.OperationalError:
                    pass  # column already exists
            conn.commit()
        finally:
            conn.close()

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

    def log_equity(
        self, timestamp: datetime, equity: float, balance_usd: float, positions_value: float
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO equity_snapshots
                   (timestamp, equity, balance_usd, positions_value)
                   VALUES (?, ?, ?, ?)""",
                (timestamp.isoformat(), equity, balance_usd, positions_value),
            )
            conn.commit()
        finally:
            conn.close()

    def get_trades(self, limit: int = 100) -> list[Trade]:
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason
                   FROM sim_trades ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        finally:
            conn.close()

        return [
            Trade(
                timestamp=datetime.fromisoformat(row[0]),
                pair=row[1],
                side=row[2],
                price=row[3],
                amount=row[4],
                cost_usd=row[5],
                fee=row[6],
                strategy=row[7],
                reason=row[8] or "",
            )
            for row in rows
        ]

    def log_ml_prediction(self, prediction) -> int:
        """Log an ML prediction. Returns the row ID for later outcome update."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO ml_predictions
                   (timestamp, pair, direction, confidence, feature_values,
                    feature_contributions, top_bullish, top_bearish,
                    recommended_action, recommended_size_pct,
                    predicted_change_pct, do_predict, di_value)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prediction.timestamp.isoformat(),
                    prediction.pair,
                    prediction.direction,
                    prediction.confidence,
                    json.dumps(prediction.feature_values),
                    json.dumps(prediction.feature_contributions),
                    json.dumps(prediction.top_bullish_factors),
                    json.dumps(prediction.top_bearish_factors),
                    prediction.recommended_action,
                    prediction.recommended_size_pct,
                    getattr(prediction, "predicted_change_pct", None),
                    getattr(prediction, "do_predict", None),
                    getattr(prediction, "di_value", None),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_ml_outcome(self, prediction_id: int, outcome: str, price_change: float) -> None:
        """Fill in actual outcome for a prediction (4 candles later)."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """UPDATE ml_predictions
                   SET actual_outcome = ?, actual_price_change = ?
                   WHERE id = ?""",
                (outcome, price_change, prediction_id),
            )
            conn.commit()
        finally:
            conn.close()

    def log_vol_prediction(self, prediction) -> int:
        """Log a volatility prediction."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO vol_predictions
                   (timestamp, pair, predicted_vol_12h, current_vol_12h,
                    vol_30d_avg, vol_regime, spacing_multiplier,
                    recommended_num_grids, confidence, garch_vol, feature_importance)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prediction.timestamp.isoformat(),
                    prediction.pair,
                    prediction.predicted_vol_12h,
                    prediction.current_vol_12h,
                    prediction.vol_30d_avg,
                    prediction.vol_regime,
                    prediction.spacing_multiplier,
                    prediction.recommended_num_grids,
                    prediction.confidence,
                    prediction.garch_vol,
                    json.dumps(prediction.feature_importance),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def log_vol_accuracy(self, pair: str, predicted_vol: float, actual_vol: float,
                         window_hours: int = 12) -> None:
        """Log predicted vs actual volatility for accuracy tracking."""
        error_pct = abs(predicted_vol - actual_vol) / actual_vol * 100 if actual_vol > 0 else 0
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO vol_accuracy
                   (timestamp, pair, predicted_vol, actual_vol, error_pct, window_hours)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), pair, predicted_vol, actual_vol,
                 error_pct, window_hours),
            )
            conn.commit()
        finally:
            conn.close()

    def log_grid_cycle(self, pair: str, buy_price: float, sell_price: float,
                       amount: float, pnl_usd: float, spacing_pct: float,
                       vol_regime: str = "", spacing_multiplier: float = 1.0,
                       hold_seconds: int = 0) -> None:
        """Log a completed grid cycle (buy + sell)."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO grid_cycles
                   (timestamp, pair, buy_price, sell_price, amount, pnl_usd,
                    spacing_pct, vol_regime, spacing_multiplier, hold_seconds)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), pair, buy_price, sell_price, amount,
                 pnl_usd, spacing_pct, vol_regime, spacing_multiplier, hold_seconds),
            )
            conn.commit()
        finally:
            conn.close()

    def log_self_check(self, event_type: str, details: str) -> None:
        """Log a self-check event (auto-retrain, loss limit, etc.)."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO self_check_log
                   (timestamp, event_type, details)
                   VALUES (?, ?, ?)""",
                (datetime.now().isoformat(), event_type, details),
            )
            conn.commit()
        finally:
            conn.close()

    def log_event(self, event_type: str, title: str, detail: str = "", pair: str = "") -> None:
        """Log a bot event for the activity feed (trade, ATR adjust, scan, etc.)."""
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO bot_events (timestamp, event_type, pair, title, detail, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (now, event_type, pair, title, detail, now),
            )
            conn.commit()
        finally:
            conn.close()

    def log_pair_scan(self, scan_result_dict: dict) -> None:
        """Log a pair scan result."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO pair_scans
                   (timestamp, scan_type, total_pairs_scanned, results,
                    selected_pairs, swapped_out, swapped_in)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    scan_result_dict["timestamp"],
                    scan_result_dict["scan_type"],
                    scan_result_dict["total_scanned"],
                    json.dumps(scan_result_dict["ranked"]),
                    json.dumps(scan_result_dict["selected"]),
                    json.dumps(scan_result_dict.get("swapped_out", [])),
                    json.dumps(scan_result_dict.get("swapped_in", [])),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Momentum rotation engine helpers
    # ------------------------------------------------------------------

    def log_momentum_trade(self, trade: Trade) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO momentum_trades
                   (timestamp, pair, side, price, amount, cost_usd, fee, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade.timestamp.isoformat(), trade.pair, trade.side,
                    trade.price, trade.amount, trade.cost_usd, trade.fee,
                    trade.reason, datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def log_exit_snapshot(self, snapshot: dict) -> None:
        """Persist exit-side state to the momentum_trades row for this sell."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """UPDATE momentum_trades
                   SET entry_price = ?, exit_price = ?, pnl_pct = ?, hold_hours = ?,
                       peak_price = ?, peak_pnl_pct = ?, drawdown_from_peak = ?,
                       trail_stop = ?, atr_stop = ?, exit_accel = ?,
                       exit_reason_detail = ?, exit_green_count = ?, exit_body_ratio = ?,
                       exit_ath_dist = ?, exit_time_at_level = ?, ticks_since_new_peak = ?,
                       max_adverse_pct = ?, max_favorable_pct = ?, trough_price = ?
                   WHERE id = (
                       SELECT id FROM momentum_trades
                       WHERE pair = ? AND side = 'sell'
                       ORDER BY id DESC LIMIT 1
                   )""",
                (
                    snapshot.get("entry_price"),
                    snapshot.get("exit_price"),
                    snapshot.get("pnl_pct"),
                    snapshot.get("hold_hours"),
                    snapshot.get("peak_price"),
                    snapshot.get("peak_pnl_pct"),
                    snapshot.get("drawdown_from_peak"),
                    snapshot.get("trail_stop"),
                    snapshot.get("atr_stop"),
                    snapshot.get("exit_accel"),
                    snapshot.get("exit_reason"),
                    snapshot.get("exit_green_count"),
                    snapshot.get("exit_body_ratio"),
                    snapshot.get("exit_ath_dist"),
                    snapshot.get("exit_time_at_level"),
                    snapshot.get("ticks_since_new_peak"),
                    snapshot.get("max_adverse_pct"),
                    snapshot.get("max_favorable_pct"),
                    snapshot.get("trough_price"),
                    snapshot.get("pair"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def log_momentum_equity(self, timestamp: datetime, equity: float, cash: float,
                            positions_value: float, status: str, holdings: str = "[]") -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO momentum_equity
                   (timestamp, equity, cash, positions_value, status, holdings)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (timestamp.isoformat(), equity, cash, positions_value, status, holdings),
            )
            conn.commit()
        finally:
            conn.close()

    def backfill_gate_outcomes(self) -> int:
        """Fill in follow-up prices for gate log entries that are old enough.

        Looks up candle prices at +6h, +12h, +24h, +48h after each evaluation
        and computes the PnL% if we had bought at evaluation time.
        Returns number of rows updated.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        updated = 0
        try:
            # Find rows that need backfilling (have price but missing follow-up)
            rows = conn.execute("""
                SELECT id, timestamp, pair, price FROM momentum_gate_log
                WHERE price IS NOT NULL AND pnl_24h IS NULL
                AND created_at < datetime('now', 'localtime', '-25 hours')
            """).fetchall()

            for row in rows:
                pair = row["pair"]
                eval_ts = row["timestamp"]
                entry_price = row["price"]
                if not entry_price or entry_price <= 0:
                    continue

                # Get candles after the evaluation timestamp
                candles = conn.execute("""
                    SELECT timestamp, close FROM candles
                    WHERE pair = ? AND timestamp > ?
                    ORDER BY timestamp ASC LIMIT 49
                """, (pair, eval_ts)).fetchall()

                if len(candles) < 6:
                    continue

                prices = {}
                for target_h, col in [(6, "6h"), (12, "12h"), (24, "24h"), (48, "48h")]:
                    if len(candles) >= target_h:
                        p = candles[target_h - 1]["close"]
                        pnl = (p - entry_price) / entry_price * 100
                        prices[f"price_{col}"] = round(p, 6)
                        prices[f"pnl_{col}"] = round(pnl, 2)

                if prices:
                    sets = ", ".join(f"{k} = ?" for k in prices.keys())
                    vals = list(prices.values()) + [row["id"]]
                    conn.execute(f"UPDATE momentum_gate_log SET {sets} WHERE id = ?", vals)
                    updated += 1

            conn.commit()
        finally:
            conn.close()
        return updated

    def log_momentum_gates(self, gates: list[dict]) -> None:
        """Log gate evaluation results for every candidate each scan cycle."""
        if not gates:
            return
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                """INSERT INTO momentum_gate_log
                   (timestamp, pair, accel, result, blocked_by,
                    green_count, body_ratio, chg3h_atr,
                    ath_dist, mom_age, time_at_level, price, created_at,
                    rank, picked, reason_not_picked, rsi, adx)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        g.get("timestamp", now), g["pair"], g["accel"],
                        g["result"], g.get("blocked_by"),
                        g.get("green_count"), g.get("body_ratio"), g.get("chg3h_atr"),
                        g.get("ath_dist"), g.get("mom_age"), g.get("time_at_level"),
                        g.get("price"), now,
                        g.get("rank"), g.get("picked", 0), g.get("reason_not_picked"),
                        g.get("rsi"), g.get("adx"),
                    )
                    for g in gates
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def log_wall_decisions(self, decisions: list[dict]) -> None:
        """Persist a batch of wall-aware trail decisions for later analysis.

        Each decision dict may contain: ts, pair, action, detail,
        current_price, wall_aware_stop, entry_price, peak_price,
        wall_price, wall_usd, wall_age_ms, book_bids (list), book_asks (list).
        """
        if not decisions:
            return
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                """INSERT INTO wall_decisions
                   (timestamp, pair, action, detail,
                    current_price, wall_aware_stop, entry_price, peak_price,
                    wall_price, wall_usd, wall_age_ms,
                    book_bids, book_asks, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        d.get("ts", now),
                        d.get("pair"),
                        d.get("action"),
                        d.get("detail"),
                        d.get("current_price"),
                        d.get("wall_aware_stop"),
                        d.get("entry_price"),
                        d.get("peak_price"),
                        d.get("wall_price"),
                        d.get("wall_usd"),
                        d.get("wall_age_ms"),
                        json.dumps(d["book_bids"]) if d.get("book_bids") is not None else None,
                        json.dumps(d["book_asks"]) if d.get("book_asks") is not None else None,
                        now,
                    )
                    for d in decisions
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def log_regime_snapshot(self, snap: dict) -> None:
        """Persist a single BTC regime snapshot from a scan cycle.

        Expected keys: btc_price, btc_ma, regime_state, regime_bullish,
        btc_4h_return, btc_24h_return, scans_pass, scans_fail, holdings_count.
        """
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO regime_snapshots
                   (timestamp, btc_price, btc_ma, regime_state, regime_bullish,
                    btc_4h_return, btc_24h_return,
                    scans_pass, scans_fail, holdings_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snap.get("ts", now),
                    snap.get("btc_price"),
                    snap.get("btc_ma"),
                    snap.get("regime_state"),
                    1 if snap.get("regime_bullish") else 0,
                    snap.get("btc_4h_return"),
                    snap.get("btc_24h_return"),
                    snap.get("scans_pass"),
                    snap.get("scans_fail"),
                    snap.get("holdings_count"),
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def log_momentum_event(self, event_type: str, title: str, detail: str = "") -> None:
        now = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO momentum_events (timestamp, event_type, title, detail, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (now, event_type, title, detail, now),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Feedback loop helpers
    # ------------------------------------------------------------------

    def log_adaptation(self, pair: str, loop_type: str, description: str,
                       old_value: float = 0.0, new_value: float = 0.0) -> None:
        """Log a learning/adaptation event."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO adaptations
                   (timestamp, pair, loop_type, description, old_value, new_value)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), pair, loop_type, description,
                 old_value, new_value),
            )
            conn.commit()
        finally:
            conn.close()

    def get_spacing_stats(self, pair: str, since_days: int = 7) -> list[dict]:
        """Get avg profit per cycle grouped by spacing bucket."""
        cutoff = (datetime.now() - timedelta(days=since_days)).isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT ROUND(spacing_pct, 1) as spacing_bucket,
                          AVG(pnl_usd) as avg_pnl,
                          COUNT(*) as cycle_count,
                          SUM(pnl_usd) as total_pnl
                   FROM grid_cycles
                   WHERE pair = ? AND timestamp >= ?
                   GROUP BY ROUND(spacing_pct, 1)
                   ORDER BY avg_pnl DESC""",
                (pair, cutoff),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_vol_accuracy_history(self, pair: str, limit: int = 10) -> list[dict]:
        """Get recent vol accuracy checks for a pair."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT error_pct, timestamp
                   FROM vol_accuracy
                   WHERE pair = ?
                   ORDER BY id DESC LIMIT ?""",
                (pair, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_pair_actual_pnl(self, pair: str, since_hours: int = 48) -> float:
        """Get total P&L from completed grid cycles in the last N hours."""
        cutoff = (datetime.now() - timedelta(hours=since_hours)).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                """SELECT COALESCE(SUM(pnl_usd), 0) as total
                   FROM grid_cycles
                   WHERE pair = ? AND timestamp >= ?""",
                (pair, cutoff),
            ).fetchone()
            return row[0] if row else 0.0
        finally:
            conn.close()

    def get_pair_first_trade_time(self, pair: str) -> str | None:
        """Get the timestamp of the first trade for a pair."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT MIN(timestamp) FROM sim_trades WHERE pair = ?",
                (pair,),
            ).fetchone()
            return row[0] if row and row[0] else None
        finally:
            conn.close()

    def get_recent_adaptations(self, limit: int = 50) -> list[dict]:
        """Get recent adaptation/learning events."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM adaptations ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
        finally:
            conn.close()

    def get_session_pnl(self, starting_balance: float) -> dict:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT equity, balance_usd, positions_value FROM equity_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return {"equity": starting_balance, "pnl": 0.0, "pnl_pct": 0.0}

        equity = row[0]
        pnl = equity - starting_balance
        pnl_pct = (pnl / starting_balance) * 100 if starting_balance > 0 else 0.0
        return {"equity": equity, "pnl": pnl, "pnl_pct": pnl_pct}
