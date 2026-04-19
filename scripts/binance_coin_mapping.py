"""Coin-mapping probe: map Coinbase-style pairs (X-USD) to Binance symbols.

Hits data-api.binance.vision (public, non-geoblocked) /api/v3/exchangeInfo and
tries to resolve each tracked pair against Binance's spot + futures listings.

Preference order:
  1. {BASE}USDT on spot  (deepest history, widest coverage)
  2. {BASE}USDC on spot
  3. {BASE}USD  on spot
  4. "not-listed"

Output: printed table + scripts/binance_coin_mapping.json
"""
import json
import sys
import urllib.request
from pathlib import Path

TRACKED = [
    # Passed gates (15)
    "FARTCOIN-USD", "SAPIEN-USD", "AERO-USD", "MOODENG-USD", "SUI-USD",
    "XRP-USD", "METIS-USD", "TRB-USD", "ONDO-USD", "ICP-USD",
    "SOL-USD", "XLM-USD", "AAVE-USD", "ENA-USD", "AXL-USD",
    # Recently traded but not in 36h gate log (6)
    "MON-USD", "IRYS-USD", "VVV-USD", "WET-USD", "ZEC-USD", "ALGO-USD",
    # High-accel but blocked (5)
    "BIO-USD", "PNUT-USD", "CTSI-USD", "IP-USD", "NEAR-USD",
]

EXCHANGE_INFO_URL = "https://data-api.binance.vision/api/v3/exchangeInfo"


def fetch_exchange_info() -> dict:
    req = urllib.request.Request(
        EXCHANGE_INFO_URL,
        headers={"User-Agent": "cryptobot-backfill-probe/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"exchangeInfo returned {resp.status}")
        return json.load(resp)


def build_symbol_index(info: dict) -> dict[str, set[str]]:
    """Return {base_asset: {quote_asset, ...}} for all TRADING symbols."""
    idx: dict[str, set[str]] = {}
    for s in info.get("symbols", []):
        if s.get("status") != "TRADING":
            continue
        base = s["baseAsset"].upper()
        quote = s["quoteAsset"].upper()
        idx.setdefault(base, set()).add(quote)
    return idx


def resolve(base: str, idx: dict[str, set[str]]) -> tuple[str, str] | None:
    """Return (binance_symbol, quote_asset) or None."""
    quotes = idx.get(base, set())
    for preferred in ("USDT", "USDC", "USD"):
        if preferred in quotes:
            return f"{base}{preferred}", preferred
    return None


def main() -> int:
    print(f"Probing {EXCHANGE_INFO_URL}...")
    info = fetch_exchange_info()
    idx = build_symbol_index(info)
    print(f"Binance has {len(idx)} unique base assets in TRADING status.\n")

    mapping = {}
    missing = []
    print(f"{'Coinbase pair':<18} {'Base':<10} {'Binance symbol':<20} {'Quote'}")
    print("-" * 60)
    for pair in TRACKED:
        base = pair.replace("-USD", "").upper()
        result = resolve(base, idx)
        if result is None:
            mapping[pair] = None
            missing.append(pair)
            print(f"{pair:<18} {base:<10} {'--- NOT LISTED ---':<20} -")
        else:
            symbol, quote = result
            mapping[pair] = {"binance_symbol": symbol, "quote": quote}
            print(f"{pair:<18} {base:<10} {symbol:<20} {quote}")

    print("-" * 60)
    total = len(TRACKED)
    matched = total - len(missing)
    print(f"\nMatched: {matched}/{total}  Missing: {len(missing)}")
    if missing:
        print(f"Missing pairs: {', '.join(missing)}")

    out = Path(__file__).parent / "binance_coin_mapping.json"
    out.write_text(json.dumps(mapping, indent=2))
    print(f"\nWrote {out}")
    return 0 if matched > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
