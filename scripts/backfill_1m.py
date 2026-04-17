"""Backfill 1-minute candles for the momentum pairs into candles.db.

Use for micro-entry-timing analysis and finer-grain sims than the current 1h
bars support. Writes through the existing CandleStore so rows land in the same
``candles`` table; granularity column keeps them separate from the 1h data.

Usage:
    py scripts/backfill_1m.py                # last 7 days, all momentum pairs
    py scripts/backfill_1m.py --days 30
    py scripts/backfill_1m.py --pairs BTC-USD,ETH-USD --days 3
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

# Allow running from repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from data.candle_store import CandleStore
from exchange.coinbase_client import CoinbaseClient


DEFAULT_PAIRS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
    "AVAX-USD", "LINK-USD", "ADA-USD", "MATIC-USD", "DOT-USD",
]


def _load_pairs_from_config() -> list[str]:
    try:
        with open("config/bot_config.yaml") as f:
            cfg = yaml.safe_load(f) or {}
        tape = cfg.get("market_tape", {}) or {}
        pairs = tape.get("pairs") or []
        if pairs:
            return list(pairs)
    except Exception:
        pass
    return list(DEFAULT_PAIRS)


def backfill(pairs: list[str], days: int, db_path: str) -> None:
    client = CoinbaseClient()
    store = CandleStore(db_path=db_path)
    end = datetime.now()
    start = end - timedelta(days=days)

    total_written = 0
    for pair in pairs:
        print(f"[BACKFILL] {pair}: fetching {days}d of 1m candles …", flush=True)
        try:
            candles = client.get_candles(pair, "ONE_MINUTE", start, end)
        except Exception as e:
            print(f"[BACKFILL] {pair}: FAILED — {e}", flush=True)
            continue
        if not candles:
            print(f"[BACKFILL] {pair}: no candles returned", flush=True)
            continue
        store.save_candles(pair, "ONE_MINUTE", candles)
        total_written += len(candles)
        print(f"[BACKFILL] {pair}: wrote {len(candles)} rows "
              f"({candles[0].timestamp} → {candles[-1].timestamp})",
              flush=True)

    print(f"[BACKFILL] done — {total_written} total rows across {len(pairs)} pairs")


def main():
    p = argparse.ArgumentParser(description="Backfill 1m candles for momentum pairs")
    p.add_argument("--days", type=int, default=7, help="lookback window in days (default 7)")
    p.add_argument("--pairs", type=str, default="",
                   help="comma-separated pair list; defaults to market_tape.pairs from config")
    p.add_argument("--db", type=str, default="data/candles.db",
                   help="path to candles.db (default data/candles.db)")
    args = p.parse_args()

    if args.pairs.strip():
        pairs = [x.strip() for x in args.pairs.split(",") if x.strip()]
    else:
        pairs = _load_pairs_from_config()

    backfill(pairs, args.days, args.db)


if __name__ == "__main__":
    main()
