"""Measure real download bandwidth to data.binance.vision — the only source
that matters for the backfill. Tests single-stream and parallel throughput."""
from __future__ import annotations

import io
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://data.binance.vision/data/spot/monthly"
# Mix of big schemas (aggTrades, 1s klines) — these are the heavy ones
TARGETS = [
    f"{BASE}/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-03.zip",
    f"{BASE}/aggTrades/ETHUSDT/ETHUSDT-aggTrades-2026-03.zip",
    f"{BASE}/aggTrades/SOLUSDT/SOLUSDT-aggTrades-2026-03.zip",
    f"{BASE}/klines/BTCUSDT/1s/BTCUSDT-1s-2026-03.zip",
]


def fetch_sink(url: str) -> tuple[str, int, float]:
    """Download + discard; return (url, bytes, seconds)."""
    req = urllib.request.Request(url, headers={"User-Agent": "cryptobot-bw-probe/1.0"})
    t0 = time.perf_counter()
    total = 0
    with urllib.request.urlopen(req, timeout=120) as resp:
        while chunk := resp.read(64 * 1024):
            total += len(chunk)
    elapsed = time.perf_counter() - t0
    return url, total, elapsed


def head_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": "cryptobot-bw-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return int(resp.headers.get("Content-Length", 0))
    except Exception as e:
        print(f"  HEAD failed {url}: {e}")
        return 0


def mbps(bytes_: int, seconds: float) -> float:
    return (bytes_ * 8) / (seconds * 1_000_000)  # megabits/sec


def mbyps(bytes_: int, seconds: float) -> float:
    return bytes_ / (seconds * 1_000_000)  # megabytes/sec


def main() -> int:
    print("=== Binance archive bandwidth probe ===\n")

    # 0. Size check
    print("File sizes (HEAD):")
    sizes = {}
    for url in TARGETS:
        sz = head_size(url)
        sizes[url] = sz
        name = url.rsplit("/", 1)[-1]
        print(f"  {name:40s}  {sz / 1_000_000:6.1f} MB")
    total_mb = sum(sizes.values()) / 1_000_000
    print(f"  total: {total_mb:.1f} MB\n")

    # 1. Single-stream (sequential) — largest file
    largest_url = max(sizes, key=sizes.get)
    print(f"Single-stream test on largest file:")
    print(f"  {largest_url.rsplit('/', 1)[-1]} ({sizes[largest_url]/1_000_000:.1f} MB)")
    _, got, elapsed = fetch_sink(largest_url)
    print(f"  downloaded {got/1_000_000:.1f} MB in {elapsed:.1f}s")
    print(f"  -> {mbyps(got, elapsed):.1f} MB/s  ({mbps(got, elapsed):.0f} Mbps)\n")

    # 2. Parallel — all files concurrently
    print(f"Parallel test ({len(TARGETS)} files at once):")
    t0 = time.perf_counter()
    total_bytes = 0
    with ThreadPoolExecutor(max_workers=len(TARGETS)) as ex:
        futures = [ex.submit(fetch_sink, u) for u in TARGETS]
        for f in as_completed(futures):
            url, got, elapsed = f.result()
            total_bytes += got
            name = url.rsplit("/", 1)[-1]
            print(f"  {name:40s}  {got/1_000_000:6.1f} MB in {elapsed:4.1f}s  ({mbyps(got, elapsed):5.1f} MB/s)")
    wall = time.perf_counter() - t0
    print(f"\n  aggregate: {total_bytes/1_000_000:.1f} MB in {wall:.1f}s wall clock")
    print(f"  -> {mbyps(total_bytes, wall):.1f} MB/s  ({mbps(total_bytes, wall):.0f} Mbps)")

    # 3. Extrapolate to full Tier 1+2 (~40 GB estimate)
    print("\n=== Projections for Tier 1+2 (~40 GB total) ===")
    agg_rate = mbyps(total_bytes, wall)  # MB/s
    full_tier_mb = 40_000
    print(f"  at {agg_rate:.1f} MB/s parallel -> {full_tier_mb/agg_rate/60:.1f} min download time")
    print(f"  (plus ~10-15 min parse on DuckDB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
