"""Market tape recorder — captures executed trades (matches) and periodic L2
snapshots on a watchlist of pairs.

Isolation contract (do not violate — see memory/project_data_collection_phase.md):
  * Separate DB: ``data/market_tape.db`` — not ``candles.db``. Prevents SQLite
    write contention with the engine's own writes.
  * Dedicated thread: own ``run_forever`` thread plus a snapshot writer thread.
  * Batched writes: matches flush every N messages OR every M seconds.
  * Fail-silent: the outer entry points wrap everything in ``try/except`` so a
    WS crash can never propagate into the trading loop.
  * Kill switch: ``market_tape.enabled`` in ``bot_config.yaml`` (default true).
"""
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


class MarketTapeRecorder:
    """Isolated WS recorder for executed trades + periodic L2 snapshots."""

    def __init__(
        self,
        pairs: list[str],
        db_path: str | Path = "data/market_tape.db",
        l2_snapshot_interval_sec: float = 5.0,
        l2_snapshot_depth: int = 50,
        matches_batch_size: int = 100,
        matches_flush_interval_sec: float = 5.0,
    ):
        self._pairs = list(pairs)
        self._db_path = Path(db_path)
        self._l2_interval = float(l2_snapshot_interval_sec)
        self._l2_depth = int(l2_snapshot_depth)
        self._matches_batch = int(matches_batch_size)
        self._matches_flush_sec = float(matches_flush_interval_sec)

        self._running = False
        self._ws: websocket.WebSocketApp | None = None
        self._ws_thread: threading.Thread | None = None
        self._snap_thread: threading.Thread | None = None

        # In-memory books keyed by pair → {price: qty}
        self._bids: dict[str, dict[float, float]] = {p: {} for p in self._pairs}
        self._asks: dict[str, dict[float, float]] = {p: {} for p in self._pairs}
        self._snapshot_done: dict[str, bool] = {p: False for p in self._pairs}
        self._book_lock = threading.Lock()

        # Matches buffer (list of dicts, flushed in batches)
        self._matches_buf: list[dict] = []
        self._matches_lock = threading.Lock()
        self._last_flush = time.time()

        # Health / debug counters
        self.stats = {
            "matches_received": 0,
            "matches_written": 0,
            "l2_updates": 0,
            "l2_snapshots_written": 0,
            "errors": 0,
            "last_error": "",
            "last_message_ts": 0.0,
        }

        self._ensure_db()

    # ------------------------------------------------------------------ DB

    def _ensure_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ws_matches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT NOT NULL,
                        ts_epoch REAL NOT NULL,
                        pair TEXT NOT NULL,
                        trade_id TEXT,
                        price REAL NOT NULL,
                        size REAL NOT NULL,
                        side TEXT
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ws_matches_pair_ts "
                    "ON ws_matches(pair, ts_epoch)"
                )
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS l2_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts TEXT NOT NULL,
                        ts_epoch REAL NOT NULL,
                        pair TEXT NOT NULL,
                        mid REAL,
                        spread_bps REAL,
                        bids TEXT,
                        asks TEXT
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_l2_pair_ts "
                    "ON l2_snapshots(pair, ts_epoch)"
                )
        except Exception as e:
            logger.error("[TAPE] _ensure_db failed: %s", e)
            self.stats["errors"] += 1
            self.stats["last_error"] = f"ensure_db: {e}"

    # ------------------------------------------------------------------ API

    def start(self) -> None:
        """Start the WS connection and the snapshot writer. Idempotent."""
        if self._running:
            return
        self._running = True
        try:
            self._connect()
            self._snap_thread = threading.Thread(
                target=self._snapshot_loop, name="tape-snap", daemon=True
            )
            self._snap_thread.start()
            logger.info("[TAPE] started — pairs=%s", self._pairs)
        except Exception as e:
            logger.error("[TAPE] start failed: %s", e)
            self.stats["errors"] += 1
            self.stats["last_error"] = f"start: {e}"
            self._running = False

    def stop(self) -> None:
        self._running = False
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass
        # One last flush of buffered matches.
        try:
            self._flush_matches(force=True)
        except Exception as e:
            logger.error("[TAPE] final flush failed: %s", e)

    # ------------------------------------------------------------------ WS

    def _connect(self) -> None:
        if not self._running:
            return

        def _on_open(ws):
            try:
                ws.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": self._pairs,
                    "channel": "market_trades",
                }))
                ws.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": self._pairs,
                    "channel": "level2",
                }))
                logger.info("[TAPE] subscribed matches+level2 for %d pairs", len(self._pairs))
            except Exception as e:
                logger.error("[TAPE] on_open send failed: %s", e)
                self.stats["errors"] += 1
                self.stats["last_error"] = f"on_open: {e}"

        def _on_message(ws, message):
            try:
                self.stats["last_message_ts"] = time.time()
                data = json.loads(message)
                ch = data.get("channel")
                if ch == "market_trades" or ch == "matches":
                    self._handle_matches(data.get("events", []))
                elif ch == "l2_data":
                    self._handle_l2(data.get("events", []))
            except Exception as e:
                # Fail-silent: never let a WS message kill the thread.
                self.stats["errors"] += 1
                self.stats["last_error"] = f"on_message: {e}"

        def _on_error(ws, error):
            logger.warning("[TAPE] ws error: %s", error)
            self.stats["errors"] += 1
            self.stats["last_error"] = f"ws_error: {error}"

        def _on_close(ws, status_code, msg):
            logger.info("[TAPE] ws closed (code=%s)", status_code)
            if self._running:
                time.sleep(2)
                try:
                    self._connect()
                except Exception as e:
                    logger.error("[TAPE] reconnect failed: %s", e)
                    self.stats["errors"] += 1
                    self.stats["last_error"] = f"reconnect: {e}"

        self._ws = websocket.WebSocketApp(
            WS_URL,
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
            on_close=_on_close,
        )
        self._ws_thread = threading.Thread(
            target=self._ws.run_forever, name="tape-ws", daemon=True
        )
        self._ws_thread.start()

    # ------------------------------------------------------------------ matches

    def _handle_matches(self, events: list[dict]) -> None:
        now_epoch = time.time()
        now_iso = datetime.now().isoformat()
        new_rows: list[dict] = []
        for event in events:
            # Coinbase Advanced Trade sends matches under "trades".
            for t in event.get("trades", []):
                try:
                    pair = t.get("product_id")
                    if pair not in self._bids:
                        # Not on our watchlist — skip.
                        continue
                    new_rows.append({
                        "ts": t.get("time", now_iso),
                        "ts_epoch": now_epoch,
                        "pair": pair,
                        "trade_id": str(t.get("trade_id", "")),
                        "price": float(t.get("price", 0) or 0),
                        "size": float(t.get("size", 0) or 0),
                        "side": t.get("side", ""),
                    })
                except (TypeError, ValueError):
                    continue
        if not new_rows:
            return
        with self._matches_lock:
            self._matches_buf.extend(new_rows)
            self.stats["matches_received"] += len(new_rows)
            due = (len(self._matches_buf) >= self._matches_batch
                   or (time.time() - self._last_flush) >= self._matches_flush_sec)
        if due:
            self._flush_matches()

    def _flush_matches(self, force: bool = False) -> None:
        with self._matches_lock:
            if not self._matches_buf:
                self._last_flush = time.time()
                return
            batch = self._matches_buf
            self._matches_buf = []
            self._last_flush = time.time()
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.executemany(
                    "INSERT INTO ws_matches "
                    "(ts, ts_epoch, pair, trade_id, price, size, side) "
                    "VALUES (:ts, :ts_epoch, :pair, :trade_id, :price, :size, :side)",
                    batch,
                )
            self.stats["matches_written"] += len(batch)
        except Exception as e:
            logger.error("[TAPE] _flush_matches failed (%d rows dropped): %s", len(batch), e)
            self.stats["errors"] += 1
            self.stats["last_error"] = f"flush_matches: {e}"

    # ------------------------------------------------------------------ L2

    def _handle_l2(self, events: list[dict]) -> None:
        with self._book_lock:
            for event in events:
                pair = event.get("product_id")
                if pair not in self._bids:
                    continue
                etype = event.get("type")
                if etype == "snapshot":
                    self._bids[pair] = {}
                    self._asks[pair] = {}
                for u in event.get("updates", []):
                    side = u.get("side")
                    try:
                        price = float(u.get("price_level", 0))
                        qty = float(u.get("new_quantity", 0))
                    except (TypeError, ValueError):
                        continue
                    if side == "bid":
                        book = self._bids[pair]
                    elif side in ("offer", "ask"):
                        book = self._asks[pair]
                    else:
                        continue
                    if qty <= 0:
                        book.pop(price, None)
                    else:
                        book[price] = qty
                    self.stats["l2_updates"] += 1
                if etype == "snapshot":
                    self._snapshot_done[pair] = True

    def _snapshot_loop(self) -> None:
        """Write a full L2 snapshot per pair every ``l2_snapshot_interval_sec``."""
        while self._running:
            try:
                time.sleep(self._l2_interval)
                self._write_l2_snapshots()
                # Also periodically flush matches even if batch threshold not hit.
                if (time.time() - self._last_flush) >= self._matches_flush_sec:
                    self._flush_matches()
            except Exception as e:
                self.stats["errors"] += 1
                self.stats["last_error"] = f"snap_loop: {e}"
                logger.error("[TAPE] snapshot loop: %s", e)

    def _write_l2_snapshots(self) -> None:
        now_epoch = time.time()
        now_iso = datetime.now().isoformat()
        rows: list[dict] = []
        with self._book_lock:
            for pair in self._pairs:
                if not self._snapshot_done.get(pair):
                    continue
                bids = self._bids.get(pair, {})
                asks = self._asks.get(pair, {})
                if not bids or not asks:
                    continue
                top_bids = sorted(bids.items(), key=lambda x: -x[0])[:self._l2_depth]
                top_asks = sorted(asks.items(), key=lambda x: x[0])[:self._l2_depth]
                if not top_bids or not top_asks:
                    continue
                best_bid = top_bids[0][0]
                best_ask = top_asks[0][0]
                mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else None
                spread_bps = (
                    (best_ask - best_bid) / mid * 10000 if mid else None
                )
                rows.append({
                    "ts": now_iso,
                    "ts_epoch": now_epoch,
                    "pair": pair,
                    "mid": mid,
                    "spread_bps": spread_bps,
                    "bids": json.dumps([[p, s] for p, s in top_bids]),
                    "asks": json.dumps([[p, s] for p, s in top_asks]),
                })
        if not rows:
            return
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.executemany(
                    "INSERT INTO l2_snapshots "
                    "(ts, ts_epoch, pair, mid, spread_bps, bids, asks) "
                    "VALUES (:ts, :ts_epoch, :pair, :mid, :spread_bps, :bids, :asks)",
                    rows,
                )
            self.stats["l2_snapshots_written"] += len(rows)
        except Exception as e:
            logger.error("[TAPE] _write_l2_snapshots failed (%d rows dropped): %s", len(rows), e)
            self.stats["errors"] += 1
            self.stats["last_error"] = f"write_l2: {e}"

    # ------------------------------------------------------------------ status

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "pairs": self._pairs,
            "db_path": str(self._db_path),
            **self.stats,
        }
