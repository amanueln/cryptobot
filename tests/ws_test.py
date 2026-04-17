"""Quick WebSocket test — connect to Coinbase public ticker and print prices."""
import json
import time
import websocket

WS_URL = "wss://advanced-trade-ws.coinbase.com"
PAIR = "FARTCOIN-USD"

def on_open(ws):
    print(f"Connected — subscribing to {PAIR} ticker...")
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
                print(f"  {ticker.get('product_id')}  ${float(ticker.get('price', 0)):.6f}  "
                      f"vol={ticker.get('volume_24_h', '?')}  "
                      f"low={ticker.get('low_24_h', '?')}  high={ticker.get('high_24_h', '?')}")
    elif data.get("channel") == "subscriptions":
        print(f"Subscribed: {data}")
    else:
        print(f"Other: {data.get('channel', data.get('type', '?'))}")

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Connection closed")

if __name__ == "__main__":
    print(f"Connecting to {WS_URL}...")
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    # Run for 30 seconds then stop
    import threading
    timer = threading.Timer(30.0, lambda: ws.close())
    timer.daemon = True
    timer.start()
    ws.run_forever()
    print("Done — 30 second test complete")
