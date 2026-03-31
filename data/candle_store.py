import sqlite3
from datetime import datetime

from exchange.models import Candle


class CandleStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    pair TEXT NOT NULL,
                    granularity TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    UNIQUE(pair, granularity, timestamp)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def save_candles(self, pair: str, granularity: str, candles: list[Candle]) -> None:
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO candles
                   (pair, granularity, timestamp, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (pair, granularity, c.timestamp.isoformat(),
                     c.open, c.high, c.low, c.close, c.volume)
                    for c in candles
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def get_candles(
        self, pair: str, granularity: str, start: datetime, end: datetime
    ) -> list[Candle]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            rows = conn.execute(
                """SELECT pair, granularity, timestamp, open, high, low, close, volume
                   FROM candles
                   WHERE pair = ? AND granularity = ?
                     AND timestamp >= ? AND timestamp <= ?
                   ORDER BY timestamp ASC""",
                (pair, granularity, start.isoformat(), end.isoformat()),
            ).fetchall()
        finally:
            conn.close()

        return [
            Candle(
                pair=row[0],
                granularity=row[1],
                timestamp=datetime.fromisoformat(row[2]),
                open=row[3],
                high=row[4],
                low=row[5],
                close=row[6],
                volume=row[7],
            )
            for row in rows
        ]
