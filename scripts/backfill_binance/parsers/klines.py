"""Parse Binance klines zips (1h or 1s — same CSV shape) into snappy parquet."""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import duckdb

# klines CSVs have no header; these are the 12 columns in fixed order.
_KLINE_COLUMNS: list[str] = [
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

_KLINE_TYPES: dict[str, str] = {
    "open_time": "BIGINT",
    "open": "DOUBLE",
    "high": "DOUBLE",
    "low": "DOUBLE",
    "close": "DOUBLE",
    "volume": "DOUBLE",
    "close_time": "BIGINT",
    "quote_volume": "DOUBLE",
    "trades": "BIGINT",
    "taker_buy_base_vol": "DOUBLE",
    "taker_buy_quote_vol": "DOUBLE",
    "ignore": "VARCHAR",
}


def parse(zip_path: Path, out_parquet: Path, symbol: str) -> int:
    """Extract the klines CSV and write a snappy parquet. Returns row count."""
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    csv_name = zip_path.name[:-4] + ".csv"

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extract(csv_name, tmp)
        csv_path = Path(tmp) / csv_name

        con = duckdb.connect(":memory:")
        names_sql = ", ".join(f"'{c}'" for c in _KLINE_COLUMNS)
        types_sql = ", ".join(f"'{c}': '{t}'" for c, t in _KLINE_TYPES.items())
        # Binance switched klines epochs from milliseconds to microseconds
        # at 2025-01. A 24-month backfill straddles both formats; branch inline
        # on magnitude (>= 1e14 is microseconds, anything smaller is ms).
        con.execute(
            f"""
            COPY (
                SELECT
                    to_timestamp(
                        CASE WHEN open_time >= 100000000000000 THEN open_time / 1000000
                             ELSE open_time / 1000 END
                    ) AS open_time,
                    to_timestamp(
                        CASE WHEN close_time >= 100000000000000 THEN close_time / 1000000
                             ELSE close_time / 1000 END
                    ) AS close_time,
                    open, high, low, close, volume,
                    quote_volume, trades,
                    taker_buy_base_vol, taker_buy_quote_vol,
                    '{symbol}' AS symbol
                FROM read_csv_auto(
                    '{csv_path.as_posix()}',
                    header=false,
                    names=[{names_sql}],
                    types={{{types_sql}}}
                )
            ) TO '{out_parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION SNAPPY)
            """
        )
        rows = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{out_parquet.as_posix()}')"
        ).fetchone()[0]
        con.close()
    return int(rows)
