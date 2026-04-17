"""Test: Would WebSocket catch early scanner signals faster than 10-min REST polling?

Connects to Coinbase WebSocket for top volume coins, runs signal checks
in real-time, and compares timing to simulated 10-minute REST polling.

Run for 1 hour to collect meaningful data.
"""
import json
import time
import threading
import requests
import websocket
from datetime import datetime, timezone, timedelta
from collections import defaultdict

WS_URL = "wss://advanced-trade-ws.coinbase.com"
CANDLE_URL = "https://api.coinbase.com/api/v3/brokerage/market/products"

# Scanner thresholds (same as early_scanner.py)
VOL_SPIKE_MULT = 2.5
PRICE_RISE_1H = 0.01
MOM_3H_THRESH = 0.03
STRONG_MOVE_3H = 0.05
MIN_SCORE = 2

# How long to run (seconds)
TEST_DURATION = 3600  # 1 hour

# Track state
coin_history = {}       # pair -> {closes: [], highs: [], volumes: [], vol_24h_avg: float}
ws_alerts = []          # alerts caught by WebSocket
poll_alerts = []        # alerts caught by simulated 10-min poll
ws_prices = defaultdict(list)  # pair -> [(time, price)]
last_poll_check = 0


def get_top_coins(n=15):
    """Get top N coins by 24h volume from Coinbase."""
    try:
        r = requests.get(CANDLE_URL, timeout=15)
        products = r.json().get('products', [])
    except Exception as e:
        print(f"Failed to fetch products: {e}")
        return []

    STABLES = {'USDT-USD', 'USDC-USD', 'DAI-USD', 'PYUSD-USD', 'GUSD-USD',
               'BUSD-USD', 'USDP-USD', 'TUSD-USD', 'CBETH-USD', 'PAXG-USD',
               'WBTC-USD', 'STETH-USD'}

    eligible = []
    for p in products:
        if p.get('quote_currency_id') != 'USD' or p.get('status') != 'online':
            continue
        pair = p['product_id']
        if pair in STABLES:
            continue
        try:
            price = float(p.get('price', 0))
            vol = float(p.get('volume_24h', 0)) * price
        except (ValueError, TypeError):
            continue
        if price < 0.01 or vol < 300_000:
            continue
        eligible.append({'pair': pair, 'price': price, 'vol_24h': vol})

    eligible.sort(key=lambda x: x['vol_24h'], reverse=True)
    return eligible[:n]


def fetch_candle_history(pair, hours=76):
    """Fetch hourly candles for baseline."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    url = f"{CANDLE_URL}/{pair}/candles"
    params = {
        "start": str(int(start.timestamp())),
        "end": str(int(now.timestamp())),
        "granularity": "ONE_HOUR",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        raw = resp.json().get("candles", [])
        candles = []
        for c in reversed(raw):
            candles.append({
                'close': float(c['close']),
                'high': float(c['high']),
                'volume': float(c['volume']),
            })
        return candles
    except Exception as e:
        print(f"  Failed to fetch candles for {pair}: {e}")
        return []


def check_signals(pair, closes, highs, volumes, cur_price):
    """Run scanner signal checks. Returns (score, signals) or (0, [])."""
    if not closes or cur_price <= 0:
        return 0, []

    low_72h = min(closes)
    high_72h = max(closes)
    range_pct = ((cur_price - low_72h) / (high_72h - low_72h) * 100) if high_72h > low_72h else 50

    score = 0
    signals = []

    # Volume spike with price rising
    if len(volumes) >= 25 and range_pct <= 50:
        vol_avg = sum(volumes[-25:-1]) / 24
        cur_vol = volumes[-1]
        price_1h_ago = closes[-2] if len(closes) >= 2 else cur_price
        change_1h = (cur_price - price_1h_ago) / price_1h_ago if price_1h_ago > 0 else 0
        if vol_avg > 0 and cur_vol >= VOL_SPIKE_MULT * vol_avg and change_1h >= PRICE_RISE_1H:
            score += 2
            signals.append(f"vol_spike ({cur_vol / vol_avg:.1f}x, +{change_1h * 100:.1f}%)")

    # 72h breakout
    if len(closes) >= 4 and len(highs) >= 72 and range_pct <= 85:
        high_72h_prev = max(highs[:-1])
        price_3h_ago = closes[-4]
        mom_3h = (cur_price - price_3h_ago) / price_3h_ago if price_3h_ago > 0 else 0
        if cur_price > high_72h_prev and mom_3h >= MOM_3H_THRESH:
            score += 2
            signals.append(f"breakout (new high ${cur_price:.4f}, +{mom_3h * 100:.1f}%)")

    # Momentum reversal
    if len(closes) >= 7:
        price_6h_ago = closes[-7]
        price_3h_ago = closes[-4]
        prev_3h = (price_3h_ago - price_6h_ago) / price_6h_ago if price_6h_ago > 0 else 0
        cur_3h = (cur_price - price_3h_ago) / price_3h_ago if price_3h_ago > 0 else 0
        if prev_3h <= 0.005 and cur_3h >= MOM_3H_THRESH:
            score += 1
            signals.append(f"reversal ({prev_3h * 100:+.1f}% -> +{cur_3h * 100:.1f}%)")

    # Strong 3h move
    if len(closes) >= 4 and range_pct <= 50:
        price_3h_ago = closes[-4]
        change_3h = (cur_price - price_3h_ago) / price_3h_ago if price_3h_ago > 0 else 0
        if change_3h >= STRONG_MOVE_3H:
            score += 1
            signals.append(f"strong_move (+{change_3h * 100:.1f}%)")

    # Bottom bounce
    if len(closes) >= 3 and range_pct <= 25:
        prev_change = (closes[-2] - closes[-3]) / closes[-3] if closes[-3] > 0 else 0
        cur_change = (cur_price - closes[-2]) / closes[-2] if closes[-2] > 0 else 0
        if prev_change <= 0.005 and cur_change >= 0.005:
            score += 2
            signals.append(f"bottom_bounce (range {range_pct:.0f}%)")

    # Squeeze
    if len(closes) >= 24:
        range_24h = max(closes[-24:]) - min(closes[-24:])
        range_6h = max(closes[-6:]) - min(closes[-6:])
        if range_24h > 0 and range_6h / range_24h < 0.25 and range_pct <= 40:
            score += 1
            signals.append(f"squeeze ({range_6h / range_24h * 100:.0f}%)")

    return score, signals


def run_test():
    print("=" * 70)
    print("WEBSOCKET vs REST POLL — EARLY SCANNER TEST")
    print(f"Duration: {TEST_DURATION // 60} minutes")
    print("=" * 70)

    # Step 1: Get top coins
    print("\nFetching top volume coins...")
    coins = get_top_coins(15)
    if not coins:
        print("No coins found!")
        return

    pairs = [c['pair'] for c in coins]
    print(f"Watching {len(pairs)} coins:")
    for c in coins:
        print(f"  {c['pair']:<15} ${c['price']:<12.4f} vol ${c['vol_24h']:>12,.0f}")

    # Step 2: Fetch candle history for each
    print("\nFetching candle history...")
    for c in coins:
        pair = c['pair']
        candles = fetch_candle_history(pair)
        if candles:
            coin_history[pair] = {
                'closes': [x['close'] for x in candles],
                'highs': [x['high'] for x in candles],
                'volumes': [x['volume'] for x in candles],
            }
            print(f"  {pair}: {len(candles)} candles loaded")
        time.sleep(0.3)  # rate limit

    # Step 3: Track alerts we've already seen (prevent duplicates)
    ws_seen = set()    # pair -> set of signal combos
    poll_seen = set()

    # Step 4: Connect WebSocket
    print(f"\nConnecting WebSocket — running for {TEST_DURATION // 60} minutes...")
    print("Checking signals on every tick (WS) vs every 10 min (simulated poll)\n")

    start_time = time.time()
    tick_count = 0
    ws_check_count = 0
    poll_check_count = 0

    def on_open(ws_app):
        ws_app.send(json.dumps({
            "type": "subscribe",
            "product_ids": pairs,
            "channel": "ticker",
        }))

    def on_message(ws_app, message):
        nonlocal tick_count, ws_check_count, poll_check_count
        data = json.loads(message)
        if data.get("channel") != "ticker":
            return

        for event in data.get("events", []):
            for ticker in event.get("tickers", []):
                pair = ticker.get("product_id", "")
                price = float(ticker.get("price", 0))
                if pair not in coin_history:
                    continue

                tick_count += 1
                now = time.time()
                ws_prices[pair].append((now, price))

                # Update the last close with current price for signal check
                h = coin_history[pair]
                test_closes = h['closes'][:-1] + [price]

                # WS check: every tick
                ws_check_count += 1
                score, signals = check_signals(pair, test_closes, h['highs'], h['volumes'], price)
                if score >= MIN_SCORE:
                    sig_key = f"{pair}|{'|'.join(sorted(signals))}"
                    if sig_key not in ws_seen:
                        ws_seen.add(sig_key)
                        alert = {
                            'pair': pair, 'price': price, 'score': score,
                            'signals': signals, 'time': now,
                            'time_str': datetime.now().strftime('%H:%M:%S'),
                        }
                        ws_alerts.append(alert)
                        elapsed = now - start_time
                        print(f"  [WS    {elapsed:6.0f}s] {pair:<15} score={score} ${price:.4f} — {', '.join(signals)}")

    def poll_loop():
        """Simulate 10-minute REST polling."""
        nonlocal poll_check_count
        while time.time() - start_time < TEST_DURATION:
            time.sleep(600)  # 10 minutes
            if time.time() - start_time >= TEST_DURATION:
                break

            for pair in pairs:
                if pair not in coin_history:
                    continue
                # Get current price from our WS data (simulating REST poll)
                if ws_prices[pair]:
                    price = ws_prices[pair][-1][1]
                else:
                    continue

                h = coin_history[pair]
                test_closes = h['closes'][:-1] + [price]
                poll_check_count += 1
                score, signals = check_signals(pair, test_closes, h['highs'], h['volumes'], price)
                if score >= MIN_SCORE:
                    sig_key = f"{pair}|{'|'.join(sorted(signals))}"
                    if sig_key not in poll_seen:
                        poll_seen.add(sig_key)
                        alert = {
                            'pair': pair, 'price': price, 'score': score,
                            'signals': signals, 'time': time.time(),
                            'time_str': datetime.now().strftime('%H:%M:%S'),
                        }
                        poll_alerts.append(alert)
                        elapsed = time.time() - start_time
                        print(f"  [POLL  {elapsed:6.0f}s] {pair:<15} score={score} ${price:.4f} — {', '.join(signals)}")

    # Start poll simulation in background
    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()

    # Run WebSocket
    ws_app = websocket.WebSocketApp(WS_URL, on_open=on_open, on_message=on_message)
    timer = threading.Timer(float(TEST_DURATION), lambda: ws_app.close())
    timer.daemon = True
    timer.start()
    ws_app.run_forever()

    # Wait for poll thread
    poll_thread.join(timeout=5)

    # Results
    print(f"\n{'=' * 70}")
    print("RESULTS")
    print(f"{'=' * 70}")
    duration = time.time() - start_time
    print(f"\nDuration: {duration / 60:.1f} minutes")
    print(f"Total ticks received: {tick_count:,}")
    print(f"WS signal checks: {ws_check_count:,}")
    print(f"Poll signal checks: {poll_check_count}")
    print(f"\nWS alerts: {len(ws_alerts)}")
    print(f"Poll alerts: {len(poll_alerts)}")

    if ws_alerts:
        print(f"\n--- WebSocket Alerts ---")
        for a in ws_alerts:
            elapsed = a['time'] - start_time
            print(f"  [{a['time_str']}] +{elapsed:5.0f}s  {a['pair']:<15} score={a['score']} ${a['price']:.4f}")
            print(f"           signals: {', '.join(a['signals'])}")

    if poll_alerts:
        print(f"\n--- Poll Alerts ---")
        for a in poll_alerts:
            elapsed = a['time'] - start_time
            print(f"  [{a['time_str']}] +{elapsed:5.0f}s  {a['pair']:<15} score={a['score']} ${a['price']:.4f}")
            print(f"           signals: {', '.join(a['signals'])}")

    # Compare: for each WS alert, did poll catch it? How much later?
    if ws_alerts:
        print(f"\n--- Timing Comparison ---")
        for wa in ws_alerts:
            # Find matching poll alert
            match = None
            for pa in poll_alerts:
                if pa['pair'] == wa['pair']:
                    match = pa
                    break
            if match:
                delay = match['time'] - wa['time']
                price_diff = match['price'] - wa['price']
                pct_diff = price_diff / wa['price'] * 100
                print(f"  {wa['pair']:<15} WS: {wa['time_str']}  Poll: {match['time_str']}  "
                      f"Delay: {delay:.0f}s ({delay / 60:.1f}min)  "
                      f"Price moved: {pct_diff:+.2f}%")
            else:
                print(f"  {wa['pair']:<15} WS: {wa['time_str']}  Poll: MISSED entirely")

    if not ws_alerts and not poll_alerts:
        print("\nNo alerts fired during the test period.")
        print("This is normal — signals require specific conditions (volume spikes, breakouts, etc.)")
        print("The market may have been quiet during this window.")

        # Show price movement summary
        print(f"\n--- Price Movement Summary ---")
        for pair in pairs:
            if ws_prices[pair]:
                prices = [p[1] for p in ws_prices[pair]]
                pct = (prices[-1] - prices[0]) / prices[0] * 100
                rng = (max(prices) - min(prices)) / prices[0] * 100
                print(f"  {pair:<15} {len(prices):>5} ticks  "
                      f"${prices[0]:.4f} -> ${prices[-1]:.4f}  "
                      f"change: {pct:+.2f}%  range: {rng:.2f}%")


if __name__ == "__main__":
    run_test()
