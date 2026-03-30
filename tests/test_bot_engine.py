import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from exchange.models import Candle, Signal
from engine.bot_engine import BotEngine


DOGE_CONFIG = {
    "pair": "DOGE-USD",
    "granularity": "ONE_HOUR",
    "lower_price": 0.15,
    "upper_price": 0.25,
    "num_grids": 10,
    "total_investment_usd": 1000,
    "stop_loss_pct": 0.15,
    "take_profit_pct": 0.10,
}


def _make_candle(close: float, hour: int = 0, pair: str = "DOGE-USD") -> Candle:
    return Candle(
        pair=pair,
        granularity="ONE_HOUR",
        timestamp=datetime(2026, 1, 1) + timedelta(hours=hour),
        open=close * 0.99,
        high=close * 1.01,
        low=close * 0.98,
        close=close,
        volume=1000.0,
    )


def _make_engine(db_path: str | None = None) -> tuple[BotEngine, str]:
    if db_path is None:
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

    engine = BotEngine(
        strategy_name="grid",
        strategy_config=DOGE_CONFIG,
        starting_balance=3000.0,
        db_path=db_path,
        poll_seconds=1,
        warmup_days=0,
    )
    return engine, db_path


def test_engine_init():
    engine, path = _make_engine()
    try:
        assert engine.pair == "DOGE-USD"
        assert engine.starting_balance == 3000.0
        assert engine.running is False
        assert engine.simulator.balance_usd == 3000.0
    finally:
        os.unlink(path)


def test_engine_processes_new_candle():
    engine, path = _make_engine()
    try:
        # Simulate feeding a candle directly
        candle = _make_candle(0.20, hour=0)
        engine._last_candle_ts = None

        with patch.object(engine.client, "get_latest_candles", return_value=[candle]):
            engine._poll_and_process()

        assert engine._last_candle_ts == candle.timestamp
        assert engine._candles_fed == 1
    finally:
        os.unlink(path)


def test_engine_skips_duplicate_candle():
    engine, path = _make_engine()
    try:
        candle = _make_candle(0.20, hour=0)
        engine._last_candle_ts = candle.timestamp  # Already seen

        with patch.object(engine.client, "get_latest_candles", return_value=[candle]):
            engine._poll_and_process()

        assert engine._candles_fed == 0  # Should not process again
    finally:
        os.unlink(path)


def test_engine_handles_api_failure():
    engine, path = _make_engine()
    try:
        with patch.object(engine.client, "get_latest_candles", return_value=[]):
            engine._poll_and_process()

        assert engine._candles_fed == 0  # No crash, no candles processed
    finally:
        os.unlink(path)


def test_engine_executes_signals():
    engine, path = _make_engine()
    try:
        # Warm up grid strategy with enough candles to establish levels
        for i in range(5):
            candle = _make_candle(0.20, hour=i)
            engine.strategy.on_candle(candle)
            engine._last_candle_ts = candle.timestamp

        # Now feed a candle that should trigger grid activity
        candle = _make_candle(0.18, hour=5)
        with patch.object(engine.client, "get_latest_candles", return_value=[candle]):
            engine._poll_and_process()

        # Engine should have logged equity snapshots
        pnl = engine.trade_logger.get_session_pnl(3000.0)
        assert "equity" in pnl
    finally:
        os.unlink(path)


def test_engine_logs_equity():
    engine, path = _make_engine()
    try:
        candle = _make_candle(0.20, hour=0)
        with patch.object(engine.client, "get_latest_candles", return_value=[candle]):
            engine._poll_and_process()

        pnl = engine.trade_logger.get_session_pnl(3000.0)
        assert pnl["equity"] > 0
    finally:
        os.unlink(path)


def test_engine_warmup_uses_cached_candles():
    """Warmup should feed historical candles to strategy."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    engine = BotEngine(
        strategy_name="grid",
        strategy_config=DOGE_CONFIG,
        starting_balance=3000.0,
        db_path=path,
        poll_seconds=1,
        warmup_days=7,
    )
    try:
        # Pre-populate candle store with recent candles (within warmup window)
        from data.candle_store import CandleStore
        store = CandleStore(path)
        now = datetime.now()
        candles = []
        for i in range(50):
            c = Candle(
                pair="DOGE-USD",
                granularity="ONE_HOUR",
                timestamp=now - timedelta(days=6) + timedelta(hours=i),
                open=0.198,
                high=0.202,
                low=0.196,
                close=0.20,
                volume=1000.0,
            )
            candles.append(c)
        store.save_candles("DOGE-USD", "ONE_HOUR", candles)

        # Warmup fetches from cache (mock API to return nothing)
        with patch.object(engine.client, "get_candles", return_value=[]):
            count = engine.warmup()

        assert count > 0
        assert engine._candles_fed > 0
    finally:
        os.unlink(path)


def test_engine_stop():
    engine, path = _make_engine()
    try:
        engine.running = True
        engine.stop()
        assert engine.running is False
    finally:
        os.unlink(path)


def test_engine_multiple_candles_in_one_poll():
    engine, path = _make_engine()
    try:
        candles = [_make_candle(0.20, hour=i) for i in range(3)]

        with patch.object(engine.client, "get_latest_candles", return_value=candles):
            engine._poll_and_process()

        assert engine._candles_fed == 3
        assert engine._last_candle_ts == candles[-1].timestamp
    finally:
        os.unlink(path)
