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
        # In-memory L2 order book (price -> size) and per-level first-seen epoch.
        self._bids: dict[float, float] = {}
        self._asks: dict[float, float] = {}
        self._bid_first_seen: dict[float, float] = {}
        self._ask_first_seen: dict[float, float] = {}
        self._book_snapshot_done = False
        self._book_lock = threading.Lock()
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
        with self._book_lock:
            self._bids.clear(); self._asks.clear()
            self._bid_first_seen.clear(); self._ask_first_seen.clear()
            self._book_snapshot_done = False
        self._running = True

        def _on_open(ws):
            logger.info("WS recorder connected — subscribing to ticker+level2 for %s", pair)
            ws.send(json.dumps({
                "type": "subscribe",
                "product_ids": [pair],
                "channel": "ticker",
            }))
            ws.send(json.dumps({
                "type": "subscribe",
                "product_ids": [pair],
                "channel": "level2",
            }))

        def _on_message(ws, message):
            data = json.loads(message)
            ch = data.get("channel")
            if ch == "ticker":
                for event in data.get("events", []):
                    for ticker in event.get("tickers", []):
                        tick = {
                            "trade_id": self._trade_id,
                            "pair": ticker.get("product_id", pair),
                            "price": float(ticker.get("price", 0)),
                            "volume_24h": float(ticker.get("volume_24_h", 0)),
                            "timestamp": datetime.utcnow().isoformat(),
                            "ts_epoch": time.time(),
                        }
                        self._ticks.append(tick)
                        # Batch write every 50 ticks
                        if len(self._ticks) % 50 == 0:
                            self._flush_ticks()
            elif ch == "l2_data":
                self._apply_l2_events(data.get("events", []))

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

    def _apply_l2_events(self, events: list[dict]):
        """Apply level2 snapshot/update events to the in-memory book."""
        now = time.time()
        with self._book_lock:
            for event in events:
                etype = event.get("type")
                if etype == "snapshot":
                    self._bids.clear(); self._asks.clear()
                    self._bid_first_seen.clear(); self._ask_first_seen.clear()
                for u in event.get("updates", []):
                    side = u.get("side")
                    try:
                        price = float(u.get("price_level", 0))
                        qty = float(u.get("new_quantity", 0))
                    except (TypeError, ValueError):
                        continue
                    if side == "bid":
                        book = self._bids
                        seen = self._bid_first_seen
                    elif side in ("offer", "ask"):
                        book = self._asks
                        seen = self._ask_first_seen
                    else:
                        continue
                    if qty <= 0:
                        book.pop(price, None)
                        seen.pop(price, None)
                    else:
                        # Preserve first-seen timestamp across qty updates at the same price.
                        if price not in book:
                            seen[price] = now
                        book[price] = qty
                if etype == "snapshot":
                    self._book_snapshot_done = True

    def get_book_snapshot(self, depth: int = 20) -> dict:
        """Return a UI-friendly snapshot: top N bids/asks, mid, spread, first-seen ages.

        Returns dict with: pair, mid, best_bid, best_ask, spread_bps, bids, asks,
        snapshot_done. Each level in bids/asks is {price, size, usd, first_seen_ms_age}.
        """
        now = time.time()
        with self._book_lock:
            if not self._book_snapshot_done or not self._bids or not self._asks:
                return {
                    "pair": self._pair,
                    "mid": None,
                    "best_bid": None,
                    "best_ask": None,
                    "spread_bps": None,
                    "bids": [],
                    "asks": [],
                    "snapshot_done": self._book_snapshot_done,
                }
            sorted_bids = sorted(self._bids.items(), key=lambda x: -x[0])[:depth]
            sorted_asks = sorted(self._asks.items(), key=lambda x: x[0])[:depth]
            best_bid = sorted_bids[0][0]
            best_ask = sorted_asks[0][0]
            mid = (best_bid + best_ask) / 2
            spread_bps = (best_ask - best_bid) / mid * 10000 if mid else None
            def _lvl(side_seen, price, size):
                fs = side_seen.get(price)
                age_ms = int((now - fs) * 1000) if fs else 0
                return {"price": price, "size": size, "usd": price * size, "age_ms": age_ms}
            return {
                "pair": self._pair,
                "mid": mid,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread_bps": spread_bps,
                "bids": [_lvl(self._bid_first_seen, p, s) for p, s in sorted_bids],
                "asks": [_lvl(self._ask_first_seen, p, s) for p, s in sorted_asks],
                "snapshot_done": True,
            }

    def find_qualifying_wall(
        self,
        peak: float,
        position_equity_usd: float,
        min_size_vs_position: float,
        min_persistence_ms: int,
        max_dist_from_peak_pct: float,
    ) -> dict | None:
        """Find the largest bid wall within max_dist_from_peak_pct below peak that
        meets the size and persistence guardrails. Returns dict or None.

        Output: {price, size, usd, age_ms, dist_from_peak_pct}
        """
        now = time.time()
        with self._book_lock:
            if not self._book_snapshot_done or not self._bids:
                return None
            min_price = peak - (peak * max_dist_from_peak_pct / 100.0)
            min_usd = position_equity_usd * min_size_vs_position
            best = None
            for price, size in self._bids.items():
                if price < min_price or price > peak:
                    continue
                usd = price * size
                if usd < min_usd:
                    continue
                fs = self._bid_first_seen.get(price)
                if fs is None:
                    continue
                age_ms = int((now - fs) * 1000)
                if age_ms < min_persistence_ms:
                    continue
                if best is None or usd > best["usd"]:
                    best = {
                        "price": price,
                        "size": size,
                        "usd": usd,
                        "age_ms": age_ms,
                        "dist_from_peak_pct": (peak - price) / peak * 100.0 if peak else 0.0,
                    }
            return best

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
        with self._book_lock:
            self._bids.clear(); self._asks.clear()
            self._bid_first_seen.clear(); self._ask_first_seen.clear()
            self._book_snapshot_done = False
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
                     datetime.utcnow().isoformat())
                )
        except Exception as e:
            logger.error("WS comparison save error: %s", e)

        return result
