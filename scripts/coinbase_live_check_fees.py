"""Read-only test for Feature 3 (fee tier visibility).

Pulls the user's real fee tier from Coinbase via the transaction summary
endpoint and prints current maker/taker rates, 30-day volume, and how
much more volume needed for the next tier.

Inconsistency-flagged: docs mention aop_from/aop_to (assets-on-platform)
in the schema; the live response also still returns usd_from/usd_to.
Code uses usd_* (volume band) for the next-tier calc since that's what
matches the user's intent ("how much more should I trade to drop a tier").
"""
import sys
sys.path.insert(0, "/app/src")
from engine.coinbase_executor import CoinbaseExecutor

DB = "/app/src/data/candles.db"

print("=== Feature 3: fee tier ===")
print(f"endpoint: GET /api/v3/brokerage/transaction_summary?product_type=SPOT")
print(f"(SDK: get_transaction_summary, SINGULAR)")
print()

ex = CoinbaseExecutor(db_path=DB)
info = ex.get_fee_tier_info(product_type="SPOT")

if "error" in info:
    print(f"FAILED: {info['error']}")
    sys.exit(1)

print(f"Pricing tier:           {info['pricing_tier']}")
print(f"Maker fee rate:         {info['maker_fee_rate']*100:.2f}% ({info['maker_fee_rate']})")
print(f"Taker fee rate:         {info['taker_fee_rate']*100:.2f}% ({info['taker_fee_rate']})")
print(f"30-day USD volume:      ${info['total_volume_30d']:,.2f}")
print(f"Current tier band:      ${info['usd_from']:,.0f} - ${info['usd_to']:,.0f}")
print(f"To reach next tier:     ${info['to_next_tier_usd']:,.2f} more in 30d volume")
print()

# What this means in $ on a real trade
print(f"=== Cost implications on a $300 round-trip ===")
maker_cost = 300 * info['maker_fee_rate'] * 2
taker_cost = 300 * info['taker_fee_rate'] * 2
print(f"Market (taker on both sides):       ${taker_cost:.4f}")
print(f"Limit + post_only (maker on both):  ${maker_cost:.4f}")
print(f"Savings if you use limit orders:    ${taker_cost - maker_cost:.4f} per round-trip")
print(f"                                    ({(1 - maker_cost/taker_cost)*100:.0f}% reduction)")
print()
print("DONE — read-only, no orders placed.")
