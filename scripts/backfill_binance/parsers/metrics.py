"""Parse Binance metrics (5-min OI + long/short ratios) zips into snappy parquet."""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import duckdb


def parse(zip_path: Path, out_parquet: Path, symbol: str) -> int:
    """Extract the metrics CSV and write a snappy parquet. Returns row count."""
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    csv_name = zip_path.name[:-4] + ".csv"

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extract(csv_name, tmp)
        csv_path = Path(tmp) / csv_name

        con = duckdb.connect(":memory:")
        # symbol column from CSV is dropped in favor of the arg (keeps schema
        # consistent with other parsers even if the CSV disagrees).
        con.execute(
            f"""
            COPY (
                SELECT
                    CAST(create_time AS TIMESTAMP) AS create_time,
                    CAST(sum_open_interest AS DOUBLE) AS sum_open_interest,
                    CAST(sum_open_interest_value AS DOUBLE) AS sum_open_interest_value,
                    CAST(count_toptrader_long_short_ratio AS DOUBLE)
                        AS count_toptrader_long_short_ratio,
                    CAST(sum_toptrader_long_short_ratio AS DOUBLE)
                        AS sum_toptrader_long_short_ratio,
                    CAST(count_long_short_ratio AS DOUBLE) AS count_long_short_ratio,
                    CAST(sum_taker_long_short_vol_ratio AS DOUBLE)
                        AS sum_taker_long_short_vol_ratio,
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
