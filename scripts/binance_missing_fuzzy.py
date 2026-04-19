"""Fuzzy-check missing coins: look for partial matches (e.g. 1000X, XPERP) on
Binance spot AND USD-M futures. Writes findings to stdout only."""
import json
import urllib.request

MISSING = ["FARTCOIN", "AERO", "MOODENG", "MON", "IRYS", "VVV", "WET", "IP"]

SPOT_URL = "https://data-api.binance.vision/api/v3/exchangeInfo"
FUTURES_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "cryptobot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fuzzy_match(needle: str, symbols: list[dict]) -> list[str]:
    hits = []
    for s in symbols:
        sym = s.get("symbol", "")
        base = s.get("baseAsset", "")
        if needle in base or needle in sym:
            hits.append(f"{sym} (base={base}, status={s.get('status', '?')})")
    return hits


def main() -> None:
    spot = fetch(SPOT_URL).get("symbols", [])
    print(f"Fetched spot: {len(spot)} symbols")
    try:
        fut = fetch(FUTURES_URL).get("symbols", [])
        print(f"Fetched futures: {len(fut)} symbols\n")
    except Exception as exc:
        print(f"Futures fetch failed (likely geoblocked): {exc}\n")
        fut = []

    for needle in MISSING:
        print(f"--- {needle} ---")
        spot_hits = fuzzy_match(needle, spot)
        fut_hits = fuzzy_match(needle, fut)
        if spot_hits:
            print(f"  SPOT:    {spot_hits}")
        if fut_hits:
            print(f"  FUTURES: {fut_hits}")
        if not spot_hits and not fut_hits:
            print("  (no matches anywhere)")
        print()


if __name__ == "__main__":
    main()
