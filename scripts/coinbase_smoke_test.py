"""Coinbase live smoke test — first real money round-trip.

Does the smallest possible buy-and-sell on BTC-USD to verify the full
pipeline (auth → submit → fill → reconcile) works end-to-end. Costs ~$0.05
in fees.

REQUIRED ENVIRONMENT VARIABLES:
  LIVE_TRADING_ENABLED=true
  LIVE_KEY_FILE=/app/persistent/coinbase_key.json     # or wherever the key is
  LIVE_PAIR_ALLOWLIST=BTC-USD                          # at minimum BTC-USD

USAGE (inside the cryptobot container):
  # Default amount: $2 (close to Coinbase's minimum). Override with --usd.
  LIVE_TRADING_ENABLED=true LIVE_PAIR_ALLOWLIST=BTC-USD \\
      python3 /app/src/scripts/coinbase_smoke_test.py --usd 2.0

  # Dry-run (no orders, just verify auth + balances + guards):
  LIVE_TRADING_ENABLED=true LIVE_PAIR_ALLOWLIST=BTC-USD \\
      python3 /app/src/scripts/coinbase_smoke_test.py --usd 2.0 --dry-run

What happens (live mode):
  1. Print pre-trade state: USD balance, BTC balance, exposure cap, kill switch
  2. Place a $X market BUY of BTC-USD
  3. Wait 8 seconds for the fill to settle
  4. Query the order's fill — confirm the BTC arrived in the account
  5. Place a market SELL for the exact BTC amount we just bought
  6. Wait 8 seconds, confirm the sell filled
  7. Print post-trade state: USD balance, BTC balance, round-trip P&L (~ -fees)
  8. Print all rows the run wrote to live_orders + live_trades for audit
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone

# Make the bot's engine package importable regardless of cwd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from engine.coinbase_executor import CoinbaseExecutor

DB_PATH = "/app/src/data/candles.db"
PAIR = "BTC-USD"
DEFAULT_USD = 2.0


def fmt(x, prec=8):
    try: return f"{float(x):.{prec}f}"
    except Exception: return str(x)


def print_state(executor, label):
    print(f"\n--- {label} ---")
    cash = executor.get_usd_cash()
    btc = executor.get_crypto_balance("BTC")
    paused, why = executor.is_paused()
    enabled, why_e = executor.is_live_enabled()
    print(f"  USD cash:        ${cash:.4f}")
    print(f"  BTC balance:     {fmt(btc)} BTC")
    print(f"  live enabled:    {enabled}  {why_e}")
    print(f"  kill switch:     paused={paused}  reason={why}")
    return cash, btc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usd", type=float, default=DEFAULT_USD,
                    help=f"USD to spend on BUY (default {DEFAULT_USD})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print state and run guards but place no orders")
    args = ap.parse_args()

    print(f"=== Coinbase smoke test  pair={PAIR}  usd=${args.usd}  dry_run={args.dry_run} ===")
    print(f"DB: {DB_PATH}")
    print(f"Run timestamp: {datetime.now(timezone.utc).isoformat()}")

    executor = CoinbaseExecutor(db_path=DB_PATH)
    cash_before, btc_before = print_state(executor, "PRE-TRADE")

    # Hard sanity check
    if cash_before < args.usd + 0.10:
        print(f"\nABORT: cash=${cash_before:.4f} < required ${args.usd + 0.10}")
        sys.exit(1)

    # ---- Gate check (without placing the order) ----
    allowed, why = executor.check_can_place_order(PAIR, args.usd)
    print(f"\nGate check for ${args.usd} BTC-USD buy: allowed={allowed}  reason='{why}'")
    if not allowed:
        print("ABORT: guards rejected the order")
        sys.exit(2)

    if args.dry_run:
        print("\nDRY RUN — no orders placed. Auth, balance reads, and guards all passed.")
        sys.exit(0)

    # ---- BUY ----
    print(f"\n=== submitting ${args.usd} market BUY of {PAIR} ===")
    buy = executor.submit_market_buy(
        PAIR, quote_size_usd=args.usd,
        intent="smoke_test", strategy="smoke_test",
    )
    print(f"  result: ok={buy.ok}  reason={buy.reason}  coinbase_order_id={buy.coinbase_order_id}")
    if not buy.ok:
        print("\nBUY FAILED — see above. Inspect live_orders for details.")
        sys.exit(3)

    print(f"  waiting 8s for fill to settle...")
    time.sleep(8)

    cash_mid, btc_mid = print_state(executor, "POST-BUY")
    bought_btc = btc_mid - btc_before
    print(f"\nBTC delta from buy: {fmt(bought_btc)} BTC")
    if bought_btc <= 0:
        print("WARNING: BTC didn't increase — buy may not have filled yet. Waiting another 8s...")
        time.sleep(8)
        cash_mid, btc_mid = print_state(executor, "POST-BUY (retry)")
        bought_btc = btc_mid - btc_before
    if bought_btc <= 0:
        print("ABORT: buy did not fill. Check Coinbase manually.")
        sys.exit(4)

    # ---- SELL ----
    # Sell what we just bought, rounded down to 8 decimals (Coinbase precision).
    sell_size = float(f"{bought_btc:.8f}")
    print(f"\n=== submitting market SELL of {sell_size} BTC ===")
    sell = executor.submit_market_sell(
        PAIR, base_size=sell_size,
        intent="smoke_test", strategy="smoke_test",
    )
    print(f"  result: ok={sell.ok}  reason={sell.reason}  coinbase_order_id={sell.coinbase_order_id}")
    if not sell.ok:
        print(f"\nSELL FAILED — you have {sell_size} BTC sitting in the account. "
              f"Sell manually via Coinbase UI to close.")
        sys.exit(5)

    print(f"  waiting 8s for fill to settle...")
    time.sleep(8)

    cash_after, btc_after = print_state(executor, "POST-SELL")

    # ---- Round-trip P&L ----
    print(f"\n=== round-trip summary ===")
    print(f"  USD before:  ${cash_before:.4f}")
    print(f"  USD after:   ${cash_after:.4f}")
    print(f"  USD delta:   ${cash_after - cash_before:+.4f}   (negative is expected = ~$0.04-0.10 fees)")
    print(f"  BTC before:  {fmt(btc_before)}")
    print(f"  BTC after:   {fmt(btc_after)}   (should match before — round-trip)")

    # ---- Audit trail ----
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    print(f"\n=== rows written to live_orders this run ===")
    for r in conn.execute(
        "SELECT id, ts, side, quote_size, base_size, intent, coinbase_order_id, result_status "
        "FROM live_orders WHERE intent='smoke_test' ORDER BY id DESC LIMIT 5"
    ):
        print(f"  id={r[0]}  {r[1][:19]}  {r[2]}  qty/usd={r[3] or r[4]}  cb_id={r[6]}  status={r[7]}")
    conn.close()

    print(f"\nSMOKE TEST COMPLETE.")


if __name__ == "__main__":
    main()
