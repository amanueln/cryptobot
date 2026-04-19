"""End-to-end smoke test for the Binance backfill pipeline.

Proves out:
  1. data.binance.vision S3 archive is reachable from US without VPN
  2. Monthly zip download + unzip works
  3. DuckDB can ingest the raw CSV
  4. Parquet output works with 3 compression levels (none / snappy / zstd)
  5. Query speed on parquet is sane
  6. Row count matches expected hours-in-month

Target: SOLUSDT 1h klines, one month (tries 2026-03 first, falls back).
"""
from __future__ import annotations

import io
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import duckdb

SYMBOL = "SOLUSDT"
INTERVAL = "1h"
# Try most recent full month; fall back one at a time if 404
MONTHS_TO_TRY = ["2026-03", "2026-02", "2026-01", "2025-12"]

BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "binance_smoke"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Binance klines CSV columns (no header row in the CSV)
COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_base_vol",
    "taker_buy_quote_vol",
    "ignore",
]


def try_fetch(month: str) -> bytes | None:
    url = f"{BASE_URL}/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{month}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "cryptobot-smoke/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        print(f"  {url} -> HTTP {e.code}")
        return None


def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main() -> int:
    print(f"=== Binance backfill smoke test: {SYMBOL} {INTERVAL} ===\n")

    # 1. Download
    zip_bytes = None
    month_used = None
    for month in MONTHS_TO_TRY:
        print(f"Trying {month}...")
        zip_bytes = try_fetch(month)
        if zip_bytes is not None:
            month_used = month
            print(f"  got it: {fmt_bytes(len(zip_bytes))}\n")
            break
    if zip_bytes is None:
        print("ERROR: no month available — archive unreachable or symbol missing")
        return 1

    zip_size = len(zip_bytes)

    # 2. Unzip
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_name = zf.namelist()[0]
        csv_bytes = zf.read(csv_name)
    csv_size = len(csv_bytes)
    csv_path = OUT_DIR / csv_name
    csv_path.write_bytes(csv_bytes)
    print(f"Unzipped CSV: {csv_name} ({fmt_bytes(csv_size)})\n")

    # 3. Ingest with DuckDB — read_csv directly
    con = duckdb.connect(":memory:")
    col_defs = ", ".join(f"{c} DOUBLE" if c != "open_time" and c != "close_time" and c != "trades" and c != "ignore" else f"{c} BIGINT" for c in COLUMNS)
    # Simpler: let DuckDB auto-detect types
    t0 = time.perf_counter()
    con.execute(f"""
        CREATE TABLE klines AS
        SELECT * FROM read_csv(
            '{csv_path.as_posix()}',
            columns = {{{", ".join(f"'{c}': 'DOUBLE'" if c not in ('open_time', 'close_time', 'trades') else f"'{c}': 'BIGINT'" for c in COLUMNS)}}},
            header = false
        )
    """)
    ingest_s = time.perf_counter() - t0
    rows = con.execute("SELECT COUNT(*) FROM klines").fetchone()[0]
    print(f"Ingested {rows} rows into DuckDB in {ingest_s*1000:.0f} ms")

    # Expected: one month of 1h bars = ~24 * 28-31 = 672-744 rows
    expected_min, expected_max = 24 * 28, 24 * 31
    ok = expected_min <= rows <= expected_max
    print(f"  row count sanity: {rows} in [{expected_min}, {expected_max}] -> {'OK' if ok else 'FAIL'}\n")

    # 4. Write parquet — three compression variants
    variants = [
        ("uncompressed", "UNCOMPRESSED"),
        ("snappy",       "SNAPPY"),
        ("zstd",         "ZSTD"),
    ]
    sizes = {}
    for label, codec in variants:
        out = OUT_DIR / f"{SYMBOL}-{INTERVAL}-{month_used}.{label}.parquet"
        t0 = time.perf_counter()
        con.execute(f"COPY klines TO '{out.as_posix()}' (FORMAT PARQUET, COMPRESSION {codec})")
        write_s = time.perf_counter() - t0
        sz = out.stat().st_size
        sizes[label] = sz
        print(f"  {label:13s} {fmt_bytes(sz):>10s}  (write: {write_s*1000:.0f} ms)")

    # 5. Spot-check aggregate against each parquet (query speed)
    print("\nSpot-check aggregate (SUM(volume), AVG(close)) per parquet:")
    for label, _ in variants:
        path = OUT_DIR / f"{SYMBOL}-{INTERVAL}-{month_used}.{label}.parquet"
        t0 = time.perf_counter()
        agg = con.execute(
            f"SELECT SUM(volume) AS vol, AVG(close) AS avg_close, MIN(low) AS lo, MAX(high) AS hi "
            f"FROM read_parquet('{path.as_posix()}')"
        ).fetchone()
        q_ms = (time.perf_counter() - t0) * 1000
        print(f"  {label:13s} vol={agg[0]:,.0f}  avg_close={agg[1]:.2f}  lo={agg[2]:.2f}  hi={agg[3]:.2f}  ({q_ms:.1f} ms)")

    # 6. Compression ratios
    print(f"\n=== Size summary ({SYMBOL} {INTERVAL} {month_used}) ===")
    print(f"  zip (on S3):   {fmt_bytes(zip_size):>10s}")
    print(f"  CSV (raw):     {fmt_bytes(csv_size):>10s}")
    for label, _ in variants:
        ratio = sizes[label] / csv_size
        print(f"  parquet/{label:13s} {fmt_bytes(sizes[label]):>10s}  ({ratio*100:.1f}% of raw CSV)")

    best = min(sizes, key=sizes.get)
    print(f"\nBest compression: {best} ({fmt_bytes(sizes[best])}, {sizes[best]/csv_size*100:.1f}% of CSV)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
