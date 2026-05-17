"""Read-only test for Batch A endpoint 1 (preview_order).

For each scenario, calls preview_market_buy() against the REAL Coinbase
API. Coinbase tells us what would happen WITHOUT submitting — projected
fill price, fee, slippage, and any errors that would block submission.

Scenarios:
  1. BTC-USD $2.00       — should preview cleanly (we did this for real already)
  2. BTC-USD $0.50       — likely below min_funds, preview should err
  3. BTC-USD $99999      — insufficient funds (account has $293.68)
  4. ZZZINVALID-USD $5   — invalid product
  5. USELESS-USD $5.00   — tradable, low-priced — let's see the precision

NO orders placed.
"""
import sys
sys.path.insert(0, "/app/src")
from engine.coinbase_executor import CoinbaseExecutor

DB = "/app/src/data/candles.db"
print("=== Batch A.1: preview_order (dry-run safety net) ===")
print("endpoint: POST /api/v3/brokerage/orders/preview")
print("(SDK: preview_market_order_buy)")
print()

ex = CoinbaseExecutor(db_path=DB)

CASES = [
    ("BTC-USD", 2.00,    "normal small"),
    ("BTC-USD", 0.50,    "below min funds?"),
    ("BTC-USD", 99999.0, "insufficient funds (account ~$293)"),
    ("ZZZINVALID-USD", 5.0, "invalid product"),
    ("USELESS-USD", 5.0, "tradable low-priced"),
]

for pair, usd, desc in CASES:
    print(f"\n--- {pair} ${usd:.2f}  ({desc}) ---")
    p = ex.preview_market_buy(pair, usd)
    flag = "ALLOW" if p["ok"] else "BLOCK"
    print(f"  result:            {flag}")
    if p["errs"]:
        print(f"  errs:              {p['errs']}")
    if p["warnings"]:
        print(f"  warnings:          {p['warnings']}")
    if p.get("projected_fill_price"):
        print(f"  proj. fill price:  {p['projected_fill_price']}")
    if p.get("projected_base_size"):
        print(f"  proj. base size:   {p['projected_base_size']}")
    if p.get("projected_fee_usd"):
        print(f"  proj. fee USD:     ${p['projected_fee_usd']}")
    if p.get("slippage"):
        print(f"  slippage:          {p['slippage']}")
    if p.get("best_bid"):
        print(f"  best bid / ask:    {p['best_bid']} / {p['best_ask']}")

print()
print("DONE — no orders placed, all preview-only.")
