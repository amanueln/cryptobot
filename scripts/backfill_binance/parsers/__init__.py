"""Dispatcher: route a Job to the right per-schema parser."""
from __future__ import annotations

from pathlib import Path

from scripts.backfill_binance.manifest import Job

from . import funding, klines, metrics

_ROUTES = {
    "klines_1h": klines.parse,
    "klines_1s": klines.parse,
    "fundingRate": funding.parse,
    "metrics": metrics.parse,
}


def parse(job: Job, zip_path: Path, data_root: Path) -> int:
    """Route to the right parser by job.schema. Returns row count."""
    fn = _ROUTES.get(job.schema)
    if fn is None:
        raise NotImplementedError(f"parser for {job.schema} not built yet")
    return fn(zip_path, job.parquet_path(data_root), job.symbol)
