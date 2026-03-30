import os
import tempfile
from datetime import datetime

from exchange.models import Trade
from data.trade_logger import TradeLogger


def _make_logger():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return TradeLogger(path), path


def _make_trade(side="buy", price=3000.0, amount=0.1, pair="ETH-USD") -> Trade:
    return Trade(
        timestamp=datetime(2026, 1, 1, 12, 0),
        pair=pair,
        side=side,
        price=price,
        amount=amount,
        cost_usd=price * amount,
        fee=price * amount * 0.006,
        strategy="grid",
        reason="test",
    )


def test_log_and_retrieve_trade():
    logger, path = _make_logger()
    try:
        trade = _make_trade()
        logger.log_trade(trade)

        trades = logger.get_trades(limit=10)
        assert len(trades) == 1
        assert trades[0].pair == "ETH-USD"
        assert trades[0].side == "buy"
        assert trades[0].price == 3000.0
    finally:
        os.unlink(path)


def test_log_multiple_trades():
    logger, path = _make_logger()
    try:
        logger.log_trade(_make_trade(side="buy", price=3000))
        logger.log_trade(_make_trade(side="sell", price=3100))
        logger.log_trade(_make_trade(side="buy", price=3050))

        trades = logger.get_trades(limit=10)
        assert len(trades) == 3
        # Returned in reverse order (most recent first)
        assert trades[0].price == 3050
    finally:
        os.unlink(path)


def test_get_trades_respects_limit():
    logger, path = _make_logger()
    try:
        for i in range(10):
            logger.log_trade(_make_trade(price=3000 + i))

        trades = logger.get_trades(limit=3)
        assert len(trades) == 3
    finally:
        os.unlink(path)


def test_log_equity_snapshot():
    logger, path = _make_logger()
    try:
        logger.log_equity(
            timestamp=datetime(2026, 1, 1, 12, 0),
            equity=3050.0,
            balance_usd=2800.0,
            positions_value=250.0,
        )

        pnl = logger.get_session_pnl(starting_balance=3000.0)
        assert pnl["equity"] == 3050.0
        assert pnl["pnl"] == 50.0
        assert abs(pnl["pnl_pct"] - 1.6667) < 0.01
    finally:
        os.unlink(path)


def test_session_pnl_no_data():
    logger, path = _make_logger()
    try:
        pnl = logger.get_session_pnl(starting_balance=3000.0)
        assert pnl["equity"] == 3000.0
        assert pnl["pnl"] == 0.0
    finally:
        os.unlink(path)


def test_tables_created():
    """Verify that the logger creates both tables on init."""
    import sqlite3

    logger, path = _make_logger()
    try:
        conn = sqlite3.connect(path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "sim_trades" in table_names
        assert "equity_snapshots" in table_names
        conn.close()
    finally:
        os.unlink(path)
