"""Compare WebSocket ticks vs REST poll over 60 seconds."""
import json
import time
import threading
import requests
import websocket

WS_URL = "wss://advanced-trade-ws.coinbase.com"
REST_URL = "https://api.coinbase.com/api/v3/brokerage/market/products"
PAIR = "FARTCOIN-USD"

ws_ticks = []
poll_ticks = []


def run_ws():
    def on_open(ws):
        ws.send(json.dumps({
            "type": "subscribe",
            "product_ids": [PAIR],
            "channel": "ticker",
        }))

    def on_message(ws, message):
        data = json.loads(message)
        if data.get("channel") == "ticker":
            for event in data.get("events", []):
                for ticker in event.get("tickers", []):
                    ws_ticks.append({
                        "price": float(ticker.get("price", 0)),
                        "time": time.time(),
                    })

    ws_app = websocket.WebSocketApp(WS_URL, on_open=on_open, on_message=on_message)
    timer = threading.Timer(60.0, lambda: ws_app.close())
    timer.daemon = True
    timer.start()
    ws_app.run_forever()


def run_polls():
    """Poll REST API every 60 seconds (simulating current behavior)."""
    start = time.time()
    while time.time() - start < 60:
        try:
            resp = requests.get(f"{REST_URL}/{PAIR}", timeout=5)
            price = float(resp.json().get("price", 0))
            poll_ticks.append({"price": price, "time": time.time()})
        except Exception as e:
            print(f"  Poll error: {e}")
        time.sleep(60)  # only one poll in 60s, like current behavior


if __name__ == "__main__":
    print(f"Running 60-second comparison for {PAIR}...")
    print(f"WebSocket: continuous ticks | REST: one poll at start\n")

    # Start both in parallel
    ws_thread = threading.Thread(target=run_ws)
    poll_thread = threading.Thread(target=run_polls)

    ws_thread.start()
    poll_thread.start()

    ws_thread.join(timeout=70)
    poll_thread.join(timeout=70)

    # Results
    print(f"\n{'='*60}")
    print(f"RESULTS ({PAIR})")
    print(f"{'='*60}")

    print(f"\nREST poll: {len(poll_ticks)} price check(s)")
    if poll_ticks:
        print(f"  Price: ${poll_ticks[0]['price']:.6f}")

    print(f"\nWebSocket: {len(ws_ticks)} ticks in 60 seconds")
    if ws_ticks:
        prices = [t["price"] for t in ws_ticks]
        print(f"  First:  ${prices[0]:.6f}")
        print(f"  Last:   ${prices[-1]:.6f}")
        print(f"  High:   ${max(prices):.6f}")
        print(f"  Low:    ${min(prices):.6f}")
        print(f"  Range:  ${max(prices) - min(prices):.6f} ({(max(prices) - min(prices)) / prices[0] * 100:.3f}%)")

        # Show unique prices
        unique = sorted(set(prices))
        print(f"  Unique prices: {len(unique)}")
        for p in unique:
            count = prices.count(p)
            print(f"    ${p:.6f} ({count}x)")

        # What the poll missed
        if poll_ticks:
            poll_price = poll_ticks[0]["price"]
            missed_low = min(prices)
            missed_high = max(prices)
            if missed_low < poll_price:
                print(f"\n  Poll MISSED a dip to ${missed_low:.6f} (${poll_price - missed_low:.6f} lower)")
            if missed_high > poll_price:
                print(f"  Poll MISSED a spike to ${missed_high:.6f} (${missed_high - poll_price:.6f} higher)")
