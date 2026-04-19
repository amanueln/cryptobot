"""Enumerate every backfill job: one (schema, symbol, month) tuple per monthly
Binance archive zip we need to pull.

The ``Job`` dataclass is the single interface between the manifest and the
downloader/parsers/writer — they never talk to each other directly.

Resume-safe: ``already_done()`` checks for a non-empty output parquet so
re-running the pipeline skips finished months.

Usage:
    from scripts.backfill_binance.manifest import build_manifest, Tier
    jobs = build_manifest(tier=Tier.ONE, months=24)
"""
from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Iterable, Literal

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAPPING_PATH = REPO_ROOT / "scripts" / "binance_coin_mapping.json"

# Root for all Binance parquet output. Writes go under this root, partitioned
# Hive-style (schema=…/symbol=…/year=…/month=…[/day=…]).
#
# The CLI overrides this for Zima runs via ``--data-dir /DATA/AppData/cryptobot/data``.
DEFAULT_DATA_ROOT = REPO_ROOT / "data" / "binance"

S3_BASE = "https://data.binance.vision/data/spot/monthly"
# Perp-only schemas — some monthly (fundingRate), some daily-only (metrics, bookDepth).
S3_FUTURES_BASE_MONTHLY = "https://data.binance.vision/data/futures/um/monthly"
S3_FUTURES_BASE_DAILY = "https://data.binance.vision/data/futures/um/daily"


class Tier(Enum):
    ONE = 1   # klines-1h + fundingRate + metrics  (~1.2 GB, 10 min run)
    TWO = 2   # + bookDepth + klines-1s + aggTrades (~40 GB, adds ~12 min run)


Cadence = Literal["monthly", "daily"]


@dataclass(frozen=True)
class Schema:
    """One Binance archive data type — where it lives on S3, how it partitions."""

    name: str                # 'klines_1h', 'fundingRate', etc.
    cadence: Cadence         # 'monthly' or 'daily' — metrics/bookDepth are daily-only
    s3_base: str             # S3 prefix (spot or futures, monthly or daily)
    s3_segment: str          # path segment, e.g. 'klines/{symbol}/1h' or 'metrics/{symbol}'
    filename_tpl: str        # monthly: 'BTCUSDT-1h-{year}-{month:02d}.zip'
                             # daily:   'BTCUSDT-metrics-{year}-{month:02d}-{day:02d}.zip'
    tier: Tier


SCHEMAS: dict[str, Schema] = {
    "klines_1h": Schema(
        name="klines_1h",
        cadence="monthly",
        s3_base=S3_BASE,
        s3_segment="klines/{symbol}/1h",
        filename_tpl="{symbol}-1h-{year}-{month:02d}.zip",
        tier=Tier.ONE,
    ),
    "fundingRate": Schema(
        name="fundingRate",
        cadence="monthly",
        s3_base=S3_FUTURES_BASE_MONTHLY,
        s3_segment="fundingRate/{symbol}",
        filename_tpl="{symbol}-fundingRate-{year}-{month:02d}.zip",
        tier=Tier.ONE,
    ),
    "metrics": Schema(
        name="metrics",
        cadence="daily",
        s3_base=S3_FUTURES_BASE_DAILY,
        s3_segment="metrics/{symbol}",
        filename_tpl="{symbol}-metrics-{year}-{month:02d}-{day:02d}.zip",
        tier=Tier.ONE,
    ),
    "bookDepth": Schema(
        name="bookDepth",
        cadence="daily",
        s3_base=S3_FUTURES_BASE_DAILY,
        s3_segment="bookDepth/{symbol}",
        filename_tpl="{symbol}-bookDepth-{year}-{month:02d}-{day:02d}.zip",
        tier=Tier.TWO,
    ),
    "klines_1s": Schema(
        name="klines_1s",
        cadence="monthly",
        s3_base=S3_BASE,
        s3_segment="klines/{symbol}/1s",
        filename_tpl="{symbol}-1s-{year}-{month:02d}.zip",
        tier=Tier.TWO,
    ),
    "aggTrades": Schema(
        name="aggTrades",
        cadence="monthly",
        s3_base=S3_BASE,
        s3_segment="aggTrades/{symbol}",
        filename_tpl="{symbol}-aggTrades-{year}-{month:02d}.zip",
        tier=Tier.TWO,
    ),
}


@dataclass(frozen=True)
class Job:
    """One download+parse+write unit of work.

    ``day`` is set for daily-cadence schemas (metrics, bookDepth) and None for
    monthly ones — daily schemas get one Job per calendar day.
    """

    schema: str          # key into SCHEMAS
    symbol: str          # e.g. 'SOLUSDT'
    year: int
    month: int           # 1–12
    day: int | None = None  # 1–31 for daily-cadence schemas; None otherwise

    @property
    def schema_def(self) -> Schema:
        return SCHEMAS[self.schema]

    def _fmt_kwargs(self) -> dict:
        kw = {"symbol": self.symbol, "year": self.year, "month": self.month}
        if self.day is not None:
            kw["day"] = self.day
        return kw

    @property
    def zip_url(self) -> str:
        s = self.schema_def
        seg = s.s3_segment.format(symbol=self.symbol)
        fn = s.filename_tpl.format(**self._fmt_kwargs())
        return f"{s.s3_base}/{seg}/{fn}"

    @property
    def zip_filename(self) -> str:
        return self.schema_def.filename_tpl.format(**self._fmt_kwargs())

    def parquet_path(self, data_root: Path) -> Path:
        """Output parquet for this job — Hive-partitioned (adds day=DD for daily)."""
        parts = [
            f"schema={self.schema}",
            f"symbol={self.symbol}",
            f"year={self.year}",
            f"month={self.month:02d}",
        ]
        if self.day is not None:
            parts.append(f"day={self.day:02d}")
        return data_root.joinpath(*parts) / "data.parquet"

    def already_done(self, data_root: Path, min_bytes: int = 512) -> bool:
        """Skip if output already exists with at least ``min_bytes``.

        512 B floor guards against truncated writes from interrupted runs —
        a real parquet with even one row is >1 KB.
        """
        p = self.parquet_path(data_root)
        return p.exists() and p.stat().st_size >= min_bytes

    def __repr__(self) -> str:
        suffix = f"-{self.day:02d}" if self.day is not None else ""
        return f"Job({self.schema} {self.symbol} {self.year}-{self.month:02d}{suffix})"


def load_binance_symbols() -> list[str]:
    """Read the Coinbase→Binance mapping, return just the matched Binance symbols.

    Relies on ``scripts/binance_coin_mapping.json`` produced by
    ``binance_coin_mapping.py``. Unmapped pairs (value is null) are dropped.
    """
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    return sorted(
        entry["binance_symbol"]
        for entry in mapping.values()
        if entry is not None
    )


def month_range(n_months: int, today: date | None = None) -> list[tuple[int, int]]:
    """Return the N most recent *complete* months as (year, month) pairs.

    Always excludes the current month (incomplete data). Ordered oldest → newest
    so the downloader can schedule oldest first (warms caches, fails fast on
    any deep-history symbol gaps).
    """
    today = today or date.today()
    first_of_current = today.replace(day=1)
    # Walk back N complete months from the month BEFORE current
    months: list[tuple[int, int]] = []
    cursor = first_of_current - timedelta(days=1)  # last day of prev month
    for _ in range(n_months):
        months.append((cursor.year, cursor.month))
        cursor = cursor.replace(day=1) - timedelta(days=1)
    return sorted(months)


def build_manifest(
    tier: Tier,
    months: int = 24,
    symbols: Iterable[str] | None = None,
    data_root: Path | None = None,
) -> list[Job]:
    """Build the full job list for the requested tier.

    Args:
        tier: Tier.ONE (klines_1h + funding + metrics) or Tier.TWO (adds depth,
            1s klines, aggTrades). Tier.TWO *includes* Tier.ONE.
        months: how many complete calendar months to pull (default 24 = 2yr).
        symbols: explicit override; default reads the mapping file.
        data_root: output parquet root; default ``data/binance/``.

    Returns:
        List of Job, ordered oldest month first (same schema grouped together).
    """
    symbols = list(symbols) if symbols is not None else load_binance_symbols()
    data_root = data_root or DEFAULT_DATA_ROOT
    month_pairs = month_range(months)

    in_scope_schemas = [
        s for s in SCHEMAS.values()
        if s.tier == Tier.ONE or (tier == Tier.TWO and s.tier == Tier.TWO)
    ]

    today = date.today()
    jobs: list[Job] = []
    for schema in in_scope_schemas:
        for symbol in symbols:
            for year, month in month_pairs:
                if schema.cadence == "monthly":
                    jobs.append(Job(schema.name, symbol, year, month))
                else:
                    # Daily schemas: one Job per calendar day in that month.
                    # Skip today and future days (archive only publishes completed UTC days).
                    _, last_day = calendar.monthrange(year, month)
                    for day in range(1, last_day + 1):
                        if date(year, month, day) >= today:
                            break
                        jobs.append(Job(schema.name, symbol, year, month, day))
    return jobs


def filter_pending(jobs: list[Job], data_root: Path) -> list[Job]:
    """Drop jobs whose output parquet already exists (resume-safe re-runs)."""
    return [j for j in jobs if not j.already_done(data_root)]


def summarize(jobs: list[Job]) -> str:
    """One-line breakdown by schema, for run-start logging."""
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j.schema] = counts.get(j.schema, 0) + 1
    parts = [f"{k}={v}" for k, v in sorted(counts.items())]
    return f"total={len(jobs)} ({', '.join(parts)})"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inspect the Binance backfill manifest.")
    parser.add_argument("--tier", type=int, choices=[1, 2], default=1)
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--show", type=int, default=5, help="sample job lines to print")
    args = parser.parse_args()

    tier = Tier.ONE if args.tier == 1 else Tier.TWO
    jobs = build_manifest(tier=tier, months=args.months)

    print(f"Tier {args.tier}, months={args.months}, symbols={len(load_binance_symbols())}")
    print(summarize(jobs))
    print(f"\nOutput root (default): {DEFAULT_DATA_ROOT}")
    print(f"\nFirst {args.show} jobs:")
    for j in jobs[: args.show]:
        print(f"  {j}")
        print(f"    url: {j.zip_url}")
        print(f"    out: {j.parquet_path(DEFAULT_DATA_ROOT).relative_to(REPO_ROOT)}")
    print(f"\nLast {args.show} jobs:")
    for j in jobs[-args.show:]:
        print(f"  {j}")
