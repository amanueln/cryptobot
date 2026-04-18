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
import time
from datetime import datetime, timedelta

# Allow running from repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import yaml

from data.candle_store import CandleStore
from exchange.coinbase_client import CoinbaseClient

# Coinbase 1m candles cap at 300 per request — same as client's pagination.
CHUNK_MINUTES = 300
MAX_RETRIES = 6  # exponential backoff: 1, 2, 4, 8, 16, 32 seconds


def _load_pairs_from_config() -> list[str]:
    with open("config/bot_config.yaml") as f:
        cfg = yaml.safe_load(f) or {}
    pairs = ((cfg.get("market_tape") or {}).get("pairs")) or []
    if not pairs:
        raise RuntimeError(
            "config/bot_config.yaml has no market_tape.pairs — refusing to "
            "backfill a silent default. Fix the config or pass --pairs."
        )
    return list(pairs)


def _fetch_chunk_with_retry(client: CoinbaseClient, pair: str,
                            chunk_start: datetime, chunk_end: datetime) -> list:
    """Fetch a single 300-candle chunk with exponential backoff on 429s."""
    for attempt in range(MAX_RETRIES):
        try:
            return client.get_candles(pair, "ONE_MINUTE", chunk_start, chunk_end)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                delay = 2 ** attempt
                time.sleep(delay)
                continue
            raise
    # Final attempt raises instead of swallowing.
    return client.get_candles(pair, "ONE_MINUTE", chunk_start, chunk_end)


def backfill(pairs: list[str], days: int, db_path: str) -> None:
    client = CoinbaseClient()
    store = CandleStore(db_path=db_path)
    end = datetime.now()
    start = end - timedelta(days=days)

    total_written = 0
    total_start = time.time()
    for pair_idx, pair in enumerate(pairs, start=1):
        pair_t0 = time.time()
        print(f"[BACKFILL] ({pair_idx}/{len(pairs)}) {pair}: "
              f"fetching {days}d of 1m candles …", flush=True)

        chunk_start = start
        chunk_duration = timedelta(minutes=CHUNK_MINUTES)
        pair_candles: list = []
        chunk_count = 0
        chunks_total = max(1, (days * 24 * 60) // CHUNK_MINUTES + 1)

        while chunk_start < end:
            chunk_end = min(chunk_start + chunk_duration, end)
            try:
                chunk = _fetch_chunk_with_retry(client, pair, chunk_start, chunk_end)
            except Exception as e:
                print(f"[BACKFILL] {pair}: chunk {chunk_count+1} FAILED — {e}",
                      flush=True)
                chunk_start = chunk_end
                continue
            if chunk:
                pair_candles.extend(chunk)
            chunk_count += 1
            chunk_start = chunk_end
            if chunk_count % 50 == 0:
                elapsed = time.time() - pair_t0
                print(f"[BACKFILL] {pair}: {chunk_count}/{chunks_total} chunks, "
                      f"{len(pair_candles)} candles so far ({elapsed:.0f}s)",
                      flush=True)

        if not pair_candles:
            print(f"[BACKFILL] {pair}: no candles returned", flush=True)
            continue
        store.save_candles(pair, "ONE_MINUTE", pair_candles)
        total_written += len(pair_candles)
        pair_dt = time.time() - pair_t0
        elapsed = time.time() - total_start
        print(f"[BACKFILL] {pair}: wrote {len(pair_candles)} rows in {pair_dt:.0f}s "
              f"({pair_candles[0].timestamp} → {pair_candles[-1].timestamp}) "
              f"[total {elapsed/60:.1f} min]",
              flush=True)

    total_dt = time.time() - total_start
    print(f"[BACKFILL] done — {total_written} total rows across {len(pairs)} pairs "
          f"in {total_dt/60:.1f} min")


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
