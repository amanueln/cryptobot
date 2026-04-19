"""Parse Binance fundingRate zips into snappy parquet."""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import duckdb


def parse(zip_path: Path, out_parquet: Path, symbol: str) -> int:
    """Extract the fundingRate CSV and write a snappy parquet. Returns row count."""
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    csv_name = zip_path.name[:-4] + ".csv"

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extract(csv_name, tmp)
        csv_path = Path(tmp) / csv_name

        con = duckdb.connect(":memory:")
        con.execute(
            f"""
            COPY (
                SELECT
                    to_timestamp(calc_time / 1000) AS calc_time,
                    CAST(funding_interval_hours AS INTEGER) AS funding_interval_hours,
                    CAST(last_funding_rate AS DOUBLE) AS last_funding_rate,
                    '{symbol}' AS symbol
                FROM read_csv_auto('{csv_path.as_posix()}', header=true)
            ) TO '{out_parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION SNAPPY)
            """
        )
        rows = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{out_parquet.as_posix()}')"
        ).fetchone()[0]
        con.close()
    return int(rows)
