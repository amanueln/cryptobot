"""WebSocket tick recorder — captures real-time prices during trades for analysis."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import websocket

logger = logging.getLogger(__name__)

WS_URL = "wss://advanced-trade-ws.coinbase.com"
DB_DIR = Path("data")


class WSRecorder:
    """Records WebSocket ticker data for a pair while a position is open.

    After the position closes, call compare_stops() to see how
    real-time ticks vs 60s polling would have differed on stop execution.
    """

    def __init__(self, db_path: Path | None = None):
        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._pair: str | None = None
        self._running = False
        self._ticks: list[dict] = []
        self._db_path = db_path or DB_DIR / "ws_ticks.db"
        self._trade_id: str | None = None
        self._ensure_db()

    def _ensure_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ws_ticks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    pair TEXT,
                    price REAL,
                    volume_24h REAL,
                    timestamp TEXT,
                    ts_epoch REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ws_comparisons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    pair TEXT,
                    entry_price REAL,
                    sell_price_poll REAL,
                    sell_price_ws REAL,
                    sell_time_poll TEXT,
                    sell_time_ws TEXT,
                    diff_usd REAL,
                    diff_seconds REAL,
                    total_ticks INTEGER,
                    duration_seconds REAL,
                    created_at TEXT
                )
            """)

    def start(self, pair: str, trade_id: str | None = None):
        """Start recording ticks for a pair."""
        if self._running:
            self.stop()

        self._pair = pair
        self._trade_id = trade_id or f"{pair}_{int(time.time())}"
        self._ticks = []
        self._running = True

        def _on_open(ws):
            logger.info("WS recorder connected — subscribing to %s", pair)
            ws.send(json.dumps({
                "type": "subscribe",
                "product_ids": [pair],
                "channel": "ticker",
            }))

        def _on_message(ws, message):
            data = json.loads(message)
            if data.get("channel") == "ticker":
                for event in data.get("events", []):
                    for ticker in event.get("tickers", []):
                        tick = {
                            "trade_id": self._trade_id,
                            "pair": ticker.get("product_id", pair),
                            "price": float(ticker.get("price", 0)),
                            "volume_24h": float(ticker.get("volume_24_h", 0)),
                            "timestamp": datetime.now().isoformat(),
                            "ts_epoch": time.time(),
                        }
                        self._ticks.append(tick)
                        # Batch write every 50 ticks
                        if len(self._ticks) % 50 == 0:
                            self._flush_ticks()

        def _on_error(ws, error):
            logger.warning("WS recorder error: %s", error)

        def _on_close(ws, status_code, msg):
            logger.info("WS recorder disconnected (code=%s)", status_code)
            if self._running:
                # Reconnect after brief pause
                time.sleep(2)
                self._connect(_on_open, _on_message, _on_error, _on_close)

        self._connect(_on_open, _on_message, _on_error, _on_close)

    def _connect(self, on_open, on_message, on_error, on_close):
        if not self._running:
            return
        self._ws = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._thread = threading.Thread(target=self._ws.run_forever, daemon=True)
        self._thread.start()

    def _flush_ticks(self):
        """Write buffered ticks to SQLite."""
        if not self._ticks:
            return
        to_write = self._ticks.copy()
        self._ticks = []
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.executemany(
                    "INSERT INTO ws_ticks (trade_id, pair, price, volume_24h, timestamp, ts_epoch) "
                    "VALUES (:trade_id, :pair, :price, :volume_24h, :timestamp, :ts_epoch)",
                    to_write,
                )
        except Exception as e:
            logger.error("WS recorder flush error: %s", e)

    def get_status(self) -> dict:
        """Return current recorder status for dashboard display."""
        return {
            "active": self._running,
            "pair": self._pair,
            "trade_id": self._trade_id,
            "tick_count": len(self._ticks) + self._get_tick_count(),
        }

    def stop(self) -> int:
        """Stop recording and flush remaining ticks. Returns tick count."""
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        self._flush_ticks()
        count = self._get_tick_count()
        logger.info("WS recorder stopped — %d ticks recorded for %s", count, self._pair)
        return count

    def _get_tick_count(self) -> int:
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM ws_ticks WHERE trade_id = ?",
                    (self._trade_id,)
                ).fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def compare_stops(self, entry_price: float, atr_stop: float, trail_stop: float,
                      actual_sell_price: float) -> dict | None:
        """Compare where 60s polling vs real-time WebSocket would have triggered the stop.

        Returns comparison dict or None if not enough data.
        """
        if not self._trade_id:
            return None

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT price, ts_epoch, timestamp FROM ws_ticks "
                    "WHERE trade_id = ? ORDER BY ts_epoch",
                    (self._trade_id,)
                ).fetchall()
        except Exception as e:
            logger.error("WS compare error: %s", e)
            return None

        if len(rows) < 10:
            return None

        effective_stop = max(atr_stop, trail_stop)
        if effective_stop <= 0:
            return None

        # Simulate real-time: check every tick
        ws_sell_price = None
        ws_sell_time = None
        for row in rows:
            if row["price"] <= effective_stop:
                ws_sell_price = row["price"]
                ws_sell_time = row["timestamp"]
                break

        # Simulate 60s polling: sample every 60s
        poll_sell_price = None
        poll_sell_time = None
        start_epoch = rows[0]["ts_epoch"]
        next_poll = start_epoch + 60
        for row in rows:
            if row["ts_epoch"] >= next_poll:
                if row["price"] <= effective_stop:
                    poll_sell_price = row["price"]
                    poll_sell_time = row["timestamp"]
                    break
                next_poll = row["ts_epoch"] + 60

        duration = rows[-1]["ts_epoch"] - rows[0]["ts_epoch"]

        # Calculate difference
        # If neither triggered, the stop wasn't hit during recording
        if ws_sell_price is None and poll_sell_price is None:
            result = {
                "trade_id": self._trade_id,
                "pair": self._pair,
                "entry_price": entry_price,
                "sell_price_poll": actual_sell_price,
                "sell_price_ws": actual_sell_price,
                "sell_time_poll": None,
                "sell_time_ws": None,
                "diff_usd": 0.0,
                "diff_seconds": 0.0,
                "total_ticks": len(rows),
                "duration_seconds": duration,
                "summary": "Stop not hit during recording — triggered on candle boundary",
            }
        elif ws_sell_price and poll_sell_price:
            # Both triggered — compare timing
            ws_epoch = next(r["ts_epoch"] for r in rows if r["timestamp"] == ws_sell_time)
            poll_epoch = next(r["ts_epoch"] for r in rows if r["timestamp"] == poll_sell_time)
            time_diff = poll_epoch - ws_epoch
            price_diff = poll_sell_price - ws_sell_price
            result = {
                "trade_id": self._trade_id,
                "pair": self._pair,
                "entry_price": entry_price,
                "sell_price_poll": poll_sell_price,
                "sell_price_ws": ws_sell_price,
                "sell_time_poll": poll_sell_time,
                "sell_time_ws": ws_sell_time,
                "diff_usd": price_diff,
                "diff_seconds": time_diff,
                "total_ticks": len(rows),
                "duration_seconds": duration,
                "summary": f"WS caught stop {time_diff:.0f}s earlier, price diff ${abs(price_diff):.4f}/coin",
            }
        elif ws_sell_price:
            result = {
                "trade_id": self._trade_id,
                "pair": self._pair,
                "entry_price": entry_price,
                "sell_price_poll": actual_sell_price,
                "sell_price_ws": ws_sell_price,
                "sell_time_poll": None,
                "sell_time_ws": ws_sell_time,
                "diff_usd": actual_sell_price - ws_sell_price,
                "diff_seconds": None,
                "total_ticks": len(rows),
                "duration_seconds": duration,
                "summary": f"WS would have caught stop but poll missed it within window",
            }
        else:
            result = {
                "trade_id": self._trade_id,
                "pair": self._pair,
                "entry_price": entry_price,
                "sell_price_poll": poll_sell_price,
                "sell_price_ws": actual_sell_price,
                "sell_time_poll": poll_sell_time,
                "sell_time_ws": None,
                "diff_usd": 0.0,
                "diff_seconds": 0.0,
                "total_ticks": len(rows),
                "duration_seconds": duration,
                "summary": "Poll caught it, WS didn't — unusual",
            }

        # Save comparison
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "INSERT INTO ws_comparisons "
                    "(trade_id, pair, entry_price, sell_price_poll, sell_price_ws, "
                    "sell_time_poll, sell_time_ws, diff_usd, diff_seconds, "
                    "total_ticks, duration_seconds, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (self._trade_id, self._pair, entry_price,
                     result["sell_price_poll"], result["sell_price_ws"],
                     result.get("sell_time_poll"), result.get("sell_time_ws"),
                     result["diff_usd"], result["diff_seconds"],
                     result["total_ticks"], result["duration_seconds"],
                     datetime.now().isoformat())
                )
        except Exception as e:
            logger.error("WS comparison save error: %s", e)

        return result
