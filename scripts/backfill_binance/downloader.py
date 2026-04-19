"""Stream Binance monthly archive zips from ``data.binance.vision`` to local disk.

Library module: ``download_zip`` fetches one ``Job``; ``download_many`` fans out
across a thread pool and invokes a completion callback per job so the
orchestrator can pipeline parse+write while other downloads are in flight.

404s are treated as expected absences (symbol not yet listed that month) and
surface as ``None``, not exceptions.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import requests

from scripts.backfill_binance.manifest import Job

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "cryptobot-backfill/1.0"}
_CHUNK = 64 * 1024


def download_zip(
    job: Job,
    temp_dir: Path,
    timeout: int = 120,
    max_retries: int = 3,
) -> Path | None:
    """Download one job's zip to ``temp_dir``; return path, or None on 404."""
    dest = temp_dir / job.zip_filename
    if dest.exists() and dest.stat().st_size > 0:
        logger.info(
            "skip-existing schema=%s symbol=%s %d-%02d bytes=%d",
            job.schema, job.symbol, job.year, job.month, dest.stat().st_size,
        )
        return dest

    temp_dir.mkdir(parents=True, exist_ok=True)
    url = job.zip_url
    backoff = 1.0
    last_err: Exception | None = None

    for attempt in range(1, max_retries + 1):
        started = time.monotonic()
        try:
            with requests.get(url, stream=True, timeout=timeout, headers=_HEADERS) as r:
                if r.status_code == 404:
                    logger.info(
                        "not-found schema=%s symbol=%s %d-%02d (pre-listing gap)",
                        job.schema, job.symbol, job.year, job.month,
                    )
                    return None
                r.raise_for_status()

                expected = r.headers.get("Content-Length")
                expected_bytes = int(expected) if expected is not None else None

                tmp = dest.with_suffix(dest.suffix + ".part")
                written = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=_CHUNK):
                        if chunk:
                            f.write(chunk)
                            written += len(chunk)

                # urllib silently truncates >~100 MB on Windows; requests does
                # not, but a short read still signals a flaky connection — retry.
                if expected_bytes is not None and written < expected_bytes:
                    tmp.unlink(missing_ok=True)
                    raise IOError(
                        f"short read: got {written} of {expected_bytes} bytes"
                    )

                tmp.replace(dest)
                elapsed = time.monotonic() - started
                mbps = (written / 1_000_000) / elapsed if elapsed > 0 else 0.0
                logger.info(
                    "done schema=%s symbol=%s %d-%02d bytes=%d secs=%.2f mbps=%.2f",
                    job.schema, job.symbol, job.year, job.month,
                    written, elapsed, mbps,
                )
                return dest

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and 400 <= status < 500:
                raise
            last_err = e
        except (requests.ConnectionError, requests.Timeout, IOError) as e:
            last_err = e

        if attempt < max_retries:
            logger.warning(
                "retry schema=%s symbol=%s %d-%02d attempt=%d err=%s",
                job.schema, job.symbol, job.year, job.month, attempt, last_err,
            )
            time.sleep(backoff)
            backoff *= 2

    assert last_err is not None
    raise last_err


def download_many(
    jobs: list[Job],
    temp_dir: Path,
    max_workers: int = 8,
    on_complete: Callable[[Job, Path | None], None] | None = None,
) -> None:
    """Parallel downloader; calls ``on_complete(job, path_or_none)`` per finish."""
    temp_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(download_zip, j, temp_dir): j for j in jobs}
        for fut in as_completed(futures):
            job = futures[fut]
            try:
                result = fut.result()
            except Exception:
                logger.exception(
                    "fail schema=%s symbol=%s %d-%02d",
                    job.schema, job.symbol, job.year, job.month,
                )
                raise
            if on_complete is not None:
                on_complete(job, result)
