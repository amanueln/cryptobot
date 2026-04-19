"""Binance public archive backfill pipeline.

Pulls 2 years of historical market data from data.binance.vision (the
non-geoblocked public mirror) for the 18 tracked pairs that exist on Binance.

Writes Hive-partitioned Parquet (snappy) under ``data/binance/`` so DuckDB
can query the whole archive with a single wildcard.

Entry point: ``python -m scripts.backfill_binance.run --tier 1``
"""
