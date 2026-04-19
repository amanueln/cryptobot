"""CLI orchestrator for the Binance historical archive backfill.

Wires the three stages together:

    manifest -> download (parallel) -> parse+write parquet -> delete zip

Downloads run in a thread pool (``--workers``, default 8 which saturates the
Binance CDN at ~415 Mbps). Parse runs in the main thread from the completion
callback, so CPU and I/O pipeline naturally: while one zip is being parsed,
others keep downloading.

Resume-safe: ``manifest.filter_pending`` drops jobs whose parquet already
exists, so a crashed run just picks up where it stopped.

Usage:
    python -m scripts.backfill_binance.run --tier 1
    python -m scripts.backfill_binance.run --tier 2 --workers 8 \\
        --data-dir /DATA/AppData/cryptobot/data/binance
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from scripts.backfill_binance import parsers
from scripts.backfill_binance.downloader import download_many
from scripts.backfill_binance.manifest import (
    DEFAULT_DATA_ROOT,
    Job,
    Tier,
    build_manifest,
    filter_pending,
    summarize,
)

logger = logging.getLogger("backfill")


def _make_on_complete(data_root: Path, keep_zips: bool) -> "callable":
    """Build the callback that parses each downloaded zip into its parquet."""
    stats = {"done": 0, "rows": 0, "missing": 0, "failed": 0}

    def on_complete(job: Job, zip_path: Path | None) -> None:
        if zip_path is None:
            stats["missing"] += 1
            return
        try:
            rows = parsers.parse(job, zip_path, data_root)
            stats["done"] += 1
            stats["rows"] += rows
            logger.info(
                "parsed schema=%s symbol=%s %d-%02d rows=%d",
                job.schema, job.symbol, job.year, job.month, rows,
            )
        except Exception:
            stats["failed"] += 1
            logger.exception(
                "parse-fail schema=%s symbol=%s %d-%02d",
                job.schema, job.symbol, job.year, job.month,
            )
            raise
        finally:
            if not keep_zips and zip_path.exists():
                zip_path.unlink(missing_ok=True)

    on_complete.stats = stats  # type: ignore[attr-defined]
    return on_complete


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Binance backfill pipeline.")
    parser.add_argument("--tier", type=int, choices=[1, 2], default=1)
    parser.add_argument("--months", type=int, default=24)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="output parquet root (override for Zima: /DATA/AppData/cryptobot/data/binance)",
    )
    parser.add_argument(
        "--temp-dir",
        type=Path,
        default=None,
        help="scratch dir for downloaded zips (default: <data-dir>/_zips)",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="comma-separated subset for testing (default: all mapped Binance symbols)",
    )
    parser.add_argument(
        "--keep-zips",
        action="store_true",
        help="don't delete downloaded zips after parsing (useful for re-runs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the manifest summary and exit without downloading",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    tier = Tier.ONE if args.tier == 1 else Tier.TWO
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None

    data_root: Path = args.data_dir
    temp_dir: Path = args.temp_dir or (data_root / "_zips")
    data_root.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    all_jobs = build_manifest(
        tier=tier, months=args.months, symbols=symbols, data_root=data_root
    )
    pending = filter_pending(all_jobs, data_root)

    logger.info("manifest %s", summarize(all_jobs))
    logger.info("pending  %s", summarize(pending))
    logger.info("data_root=%s temp_dir=%s workers=%d", data_root, temp_dir, args.workers)

    if args.dry_run:
        return 0
    if not pending:
        logger.info("nothing to do — all jobs already have parquet output")
        return 0

    on_complete = _make_on_complete(data_root, keep_zips=args.keep_zips)

    t0 = time.monotonic()
    download_many(
        pending,
        temp_dir=temp_dir,
        max_workers=args.workers,
        on_complete=on_complete,
    )
    elapsed = time.monotonic() - t0

    stats = on_complete.stats  # type: ignore[attr-defined]
    logger.info(
        "run complete: done=%d rows=%d missing=%d failed=%d elapsed=%.1fs",
        stats["done"], stats["rows"], stats["missing"], stats["failed"], elapsed,
    )
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
