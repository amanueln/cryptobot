"""Read-only test for Feature 1 (live cash check).

What it does:
  1. Calls executor.get_usd_cash() against the REAL Coinbase API
  2. Calls executor.verify_sufficient_cash() for several sizes
  3. Prints the actual live balance and what the bot thinks it has

NO orders placed. Safe to run anytime. Requires:
  LIVE_KEY_FILE pointing at the CDP key json (defaults to
  /app/persistent/coinbase_key.json in the container).
"""
import os
import sqlite3
import sys

sys.path.insert(0, "/app/src")
from engine.coinbase_executor import CoinbaseExecutor

DB = "/app/src/data/candles.db"

print("=== Feature 1: live cash check ===")
print(f"endpoint: GET /api/v3/brokerage/accounts (SDK: get_accounts)")
print()

ex = CoinbaseExecutor(db_path=DB)

# 1. Raw live balance
live = ex.get_usd_cash()
print(f"Coinbase USD available balance (live read):  ${live:.4f}")

# 2. What does the bot's persisted state say?
try:
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        row = conn.execute(
            "SELECT ts, cash_usd, total_equity_usd FROM live_equity "
            "ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    if row:
        print(f"Bot's last-snapshot cash (live_equity):      ${row[1]:.4f}")
        print(f"Snapshot at:                                  {row[0][:19]} UTC")
        drift = abs(live - row[1])
        if drift > 0.5:
            print(f"WARN: drift ${drift:.2f} between live and bot's tracking")
        else:
            print(f"Drift between live and bot's tracking:       ${drift:.4f} (within tolerance)")
    else:
        print(f"Bot's last-snapshot cash (live_equity):       (no rows)")
except Exception as e:
    print(f"could not read live_equity: {e}")

# 3. Test verify_sufficient_cash at three sizes
print()
print("verify_sufficient_cash() at three notionals:")
for notional in (2.0, 100.0, 300.0, 99999.0):
    ok, balance, why = ex.verify_sufficient_cash(notional)
    flag = "ALLOW" if ok else "BLOCK"
    print(f"  ${notional:>9.2f}  {flag}  balance=${balance:.2f}  reason='{why or ''}'")

print()
print("DONE — read-only, no orders placed.")
