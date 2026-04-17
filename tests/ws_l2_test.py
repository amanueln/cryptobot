"""Quick live test of the Coinbase level2 order-book feed.

Connects to wss://advanced-trade-ws.coinbase.com, subscribes to level2 for
a given pair, maintains an in-memory book, and prints depth metrics every
5 seconds for 60 seconds. No DB writes, no integration — just proves the
feed works and the depth numbers look sensible before we wire it into the
recorder.

Usage:
  py tests/ws_l2_test.py BTC-USD
  py tests/ws_l2_test.py FARTCOIN-USD
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime

import websocket

WS_URL = "wss://advanced-trade-ws.coinbase.com"


class BookTester:
    def __init__(self, pair: str):
        self.pair = pair
        self.bids: dict[float, float] = {}  # price -> size
        self.asks: dict[float, float] = {}
        self.snapshot_done = False
        self.update_count = 0
        self.last_print = time.time()
        self.running = True

    def apply_update(self, side: str, price: float, qty: float):
        book = self.bids if side == "bid" else self.asks
        if qty <= 0:
            book.pop(price, None)
        else:
            book[price] = qty

    def best_bid(self) -> float | None:
        return max(self.bids.keys()) if self.bids else None

    def best_ask(self) -> float | None:
        return min(self.asks.keys()) if self.asks else None

    def mid(self) -> float | None:
        bb, ba = self.best_bid(), self.best_ask()
        if bb is None or ba is None:
            return None
        return (bb + ba) / 2

    def depth_within(self, side: str, pct_low: float, pct_high: float) -> tuple[float, float]:
        """Return (total_qty, total_usd) of orders on `side` whose distance from mid
        is between pct_low and pct_high percent."""
        mid = self.mid()
        if mid is None:
            return 0.0, 0.0
        book = self.bids if side == "bid" else self.asks
        qty = 0.0
        usd = 0.0
        for price, size in book.items():
            if side == "bid":
                dist = (mid - price) / mid * 100
            else:
                dist = (price - mid) / mid * 100
            if pct_low <= dist < pct_high:
                qty += size
                usd += size * price
        return qty, usd

    def largest_wall(self, side: str, max_dist_pct: float = 5.0) -> tuple[float, float, float] | None:
        """Return (price, size, dist_pct) of largest single level within max_dist_pct."""
        mid = self.mid()
        if mid is None:
            return None
        book = self.bids if side == "bid" else self.asks
        best = None
        for price, size in book.items():
            if side == "bid":
                dist = (mid - price) / mid * 100
            else:
                dist = (price - mid) / mid * 100
            if dist < 0 or dist > max_dist_pct:
                continue
            if best is None or size > best[1]:
                best = (price, size, dist)
        return best

    def print_stats(self):
        mid = self.mid()
        if mid is None:
            print("[book not ready]")
            return
        spread = self.best_ask() - self.best_bid()
        spread_bps = spread / mid * 10000
        bid_0_1_qty, bid_0_1_usd = self.depth_within("bid", 0, 1)
        bid_1_2_qty, bid_1_2_usd = self.depth_within("bid", 1, 2)
        ask_0_1_qty, ask_0_1_usd = self.depth_within("ask", 0, 1)
        wall = self.largest_wall("bid")
        total_bid_levels = len(self.bids)
        total_ask_levels = len(self.asks)
        imbalance = bid_0_1_usd / (bid_0_1_usd + ask_0_1_usd) * 100 if (bid_0_1_usd + ask_0_1_usd) > 0 else 50
        print(f"[{datetime.now().strftime('%H:%M:%S')}] mid=${mid:.6f} spread={spread_bps:.1f}bps "
              f"updates={self.update_count} levels(b/a)={total_bid_levels}/{total_ask_levels}")
        print(f"   bid 0-1%: ${bid_0_1_usd:>9,.0f}  ask 0-1%: ${ask_0_1_usd:>9,.0f}  "
              f"imbalance: {imbalance:.1f}% (>50 = buy-side heavy)")
        print(f"   bid 1-2%: ${bid_1_2_usd:>9,.0f}")
        if wall:
            wp, wsize, wdist = wall
            wusd = wsize * wp
            print(f"   top bid wall: ${wusd:,.0f} at ${wp:.6f} ({wdist:.2f}% below mid)")


def run(pair: str, seconds: int = 60):
    tester = BookTester(pair)

    def on_open(ws):
        print(f"connected, subscribing to level2 for {pair}")
        ws.send(json.dumps({
            "type": "subscribe",
            "product_ids": [pair],
            "channel": "level2",
        }))

    def on_message(ws, message):
        data = json.loads(message)
        ch = data.get("channel")
        if ch == "subscriptions":
            print(f"subscriptions ack: {data.get('events')}")
            return
        if ch != "l2_data":
            return
        for event in data.get("events", []):
            etype = event.get("type")
            for u in event.get("updates", []):
                side = u.get("side")
                try:
                    price = float(u.get("price_level", 0))
                    qty = float(u.get("new_quantity", 0))
                except ValueError:
                    continue
                tester.apply_update(side, price, qty)
            if etype == "snapshot":
                tester.snapshot_done = True
                print(f"snapshot applied: {len(tester.bids)} bids, {len(tester.asks)} asks")
            elif etype == "update":
                tester.update_count += 1

    def on_error(ws, err):
        print(f"ws error: {err}")

    def on_close(ws, code, msg):
        print(f"ws closed: {code} {msg}")
        tester.running = False

    ws = websocket.WebSocketApp(
        WS_URL, on_open=on_open, on_message=on_message,
        on_error=on_error, on_close=on_close,
    )
    t = threading.Thread(target=ws.run_forever, daemon=True)
    t.start()

    start = time.time()
    while time.time() - start < seconds and tester.running:
        time.sleep(5)
        if tester.snapshot_done:
            tester.print_stats()

    ws.close()
    print("\n=== final ===")
    tester.print_stats()


if __name__ == "__main__":
    pair = sys.argv[1] if len(sys.argv) > 1 else "BTC-USD"
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    run(pair, seconds)
