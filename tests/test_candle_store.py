import os
import tempfile
from datetime import datetime

from exchange.models import Candle


def make_candle(ts: datetime, close: float = 85000.0) -> Candle:
    return Candle(
        pair="BTC-USD",
        granularity="ONE_HOUR",
        timestamp=ts,
        open=close - 100,
        high=close + 200,
        low=close - 300,
        close=close,
        volume=50.0,
    )


def test_save_and_get_candles():
    from data.candle_store import CandleStore

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = CandleStore(db_path)

        candles = [
            make_candle(datetime(2026, 1, 1, i, 0), 85000.0 + i * 100)
            for i in range(5)
        ]
        store.save_candles("BTC-USD", "ONE_HOUR", candles)

        result = store.get_candles(
            "BTC-USD", "ONE_HOUR",
            datetime(2026, 1, 1, 0, 0),
            datetime(2026, 1, 1, 4, 0),
        )
        assert len(result) == 5
        assert result[0].close == 85000.0
        assert result[4].close == 85400.0


def test_get_candles_empty():
    from data.candle_store import CandleStore

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = CandleStore(db_path)

        result = store.get_candles(
            "BTC-USD", "ONE_HOUR",
            datetime(2026, 1, 1, 0, 0),
            datetime(2026, 1, 1, 4, 0),
        )
        assert result == []


def test_save_candles_upsert():
    from data.candle_store import CandleStore

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = CandleStore(db_path)

        ts = datetime(2026, 1, 1, 0, 0)
        store.save_candles("BTC-USD", "ONE_HOUR", [make_candle(ts, 85000.0)])
        store.save_candles("BTC-USD", "ONE_HOUR", [make_candle(ts, 86000.0)])

        result = store.get_candles("BTC-USD", "ONE_HOUR", ts, ts)
        assert len(result) == 1
        assert result[0].close == 86000.0


def test_get_candles_returns_sorted():
    from data.candle_store import CandleStore

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = CandleStore(db_path)

        candles = [
            make_candle(datetime(2026, 1, 1, 3, 0)),
            make_candle(datetime(2026, 1, 1, 1, 0)),
            make_candle(datetime(2026, 1, 1, 2, 0)),
        ]
        store.save_candles("BTC-USD", "ONE_HOUR", candles)

        result = store.get_candles(
            "BTC-USD", "ONE_HOUR",
            datetime(2026, 1, 1, 0, 0),
            datetime(2026, 1, 1, 4, 0),
        )
        timestamps = [c.timestamp for c in result]
        assert timestamps == sorted(timestamps)
