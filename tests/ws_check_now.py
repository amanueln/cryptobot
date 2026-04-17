"""Quick check — grab current prices for all READY coins via WebSocket."""
import json
import time
import threading
import websocket

WS_URL = "wss://advanced-trade-ws.coinbase.com"
PAIRS = ["CTSI-USD", "FARTCOIN-USD", "AXL-USD", "MOODENG-USD", "AAVE-USD", "ZEC-USD"]

latest = {}

def on_open(ws):
    ws.send(json.dumps({
        "type": "subscribe",
        "product_ids": PAIRS,
        "channel": "ticker",
    }))

def on_message(ws, message):
    data = json.loads(message)
    if data.get("channel") == "ticker":
        for event in data.get("events", []):
            for ticker in event.get("tickers", []):
                pair = ticker.get("product_id", "")
                price = float(ticker.get("price", 0))
                if pair not in latest:
                    latest[pair] = {"prices": [], "high": 0, "low": 999999}
                latest[pair]["prices"].append(price)
                latest[pair]["high"] = max(latest[pair]["high"], price)
                latest[pair]["low"] = min(latest[pair]["low"], price)

if __name__ == "__main__":
    print("Connecting to WebSocket — watching 6 coins for 30 seconds...\n")
    ws = websocket.WebSocketApp(WS_URL, on_open=on_open, on_message=on_message)
    timer = threading.Timer(30.0, lambda: ws.close())
    timer.daemon = True
    timer.start()
    ws.run_forever()

    print(f"\n{'Pair':<15} {'Ticks':>6} {'First':>12} {'Last':>12} {'Low':>12} {'High':>12} {'Range%':>8}")
    print("-" * 80)
    for pair in PAIRS:
        if pair in latest:
            d = latest[pair]
            p = d["prices"]
            rng = (d["high"] - d["low"]) / p[0] * 100 if p[0] > 0 else 0
            print(f"{pair:<15} {len(p):>6} ${p[0]:>10.4f} ${p[-1]:>10.4f} ${d['low']:>10.4f} ${d['high']:>10.4f} {rng:>7.3f}%")
        else:
            print(f"{pair:<15}   -- no data --")
