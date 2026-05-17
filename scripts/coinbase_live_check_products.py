"""Read-only test for Feature 2 (product validation).

For each pair the momentum bot would trade, calls get_product() against
the real Coinbase API and prints: status, trading flags, min order size,
price precision. Then tests verify_product_tradable() at multiple sizes.

Tradable pairs (status=online, all flags off) plus a deliberately-bad pair
to confirm the rejection path works.
"""
import sys
sys.path.insert(0, "/app/src")
from engine.coinbase_executor import CoinbaseExecutor

DB = "/app/src/data/candles.db"
print("=== Feature 2: product validation ===")
print(f"endpoint: GET /api/v3/brokerage/products/{{product_id}} (SDK: get_product)")
print()

ex = CoinbaseExecutor(db_path=DB)

PAIRS = [
    "BTC-USD",       # benchmark
    "ETH-USD",
    "INJ-USD",       # bot has recently traded
    "VVV-USD",
    "USELESS-USD",
    "TROLL-USD",
    "ZZZINVALID-USD",  # deliberate bad pair — should error gracefully
]

print(f"{'pair':<18} {'status':<8} {'trading':<10} {'qmin':>8} {'price':>12} {'precision':<14}")
print("-" * 75)
for pair in PAIRS:
    info = ex.get_product_info(pair)
    if "error" in info:
        print(f"{pair:<18} ERR: {info['error'][:60]}")
        continue
    status = info.get("status") or "?"
    flags = ("HALT" if info.get("trading_disabled") or info.get("is_disabled")
             else "view" if info.get("view_only")
             else "cancel" if info.get("cancel_only")
             else "ok")
    qmin = info.get("quote_min_size", "?")
    price = info.get("price", "?")
    incr = f"{info.get('base_increment','?')}/{info.get('quote_increment','?')}"
    print(f"{pair:<18} {status:<8} {flags:<10} {qmin:>8} {price:>12} {incr:<14}")

print()
print("=== verify_product_tradable() at three notionals ===")
for pair in ["BTC-USD", "INJ-USD", "ZZZINVALID-USD"]:
    for notional in (1.0, 5.0, 300.0):
        ok, why = ex.verify_product_tradable(pair, notional)
        flag = "ALLOW" if ok else "BLOCK"
        print(f"  {pair:<18} ${notional:>6.2f}  {flag}  {why or ''}")
    print()

print("DONE — read-only, no orders placed.")
