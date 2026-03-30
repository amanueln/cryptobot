import sqlite3
from datetime import datetime

from exchange.models import Trade


class TradeLogger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pair TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    cost_usd REAL NOT NULL,
                    fee REAL NOT NULL,
                    strategy TEXT NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS equity_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    equity REAL NOT NULL,
                    balance_usd REAL NOT NULL,
                    positions_value REAL NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def log_trade(self, trade: Trade) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO sim_trades
                   (timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade.timestamp.isoformat(),
                    trade.pair,
                    trade.side,
                    trade.price,
                    trade.amount,
                    trade.cost_usd,
                    trade.fee,
                    trade.strategy,
                    trade.reason,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def log_equity(
        self, timestamp: datetime, equity: float, balance_usd: float, positions_value: float
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO equity_snapshots
                   (timestamp, equity, balance_usd, positions_value)
                   VALUES (?, ?, ?, ?)""",
                (timestamp.isoformat(), equity, balance_usd, positions_value),
            )
            conn.commit()
        finally:
            conn.close()

    def get_trades(self, limit: int = 100) -> list[Trade]:
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT timestamp, pair, side, price, amount, cost_usd, fee, strategy, reason
                   FROM sim_trades ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        finally:
            conn.close()

        return [
            Trade(
                timestamp=datetime.fromisoformat(row[0]),
                pair=row[1],
                side=row[2],
                price=row[3],
                amount=row[4],
                cost_usd=row[5],
                fee=row[6],
                strategy=row[7],
                reason=row[8] or "",
            )
            for row in rows
        ]

    def get_session_pnl(self, starting_balance: float) -> dict:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT equity, balance_usd, positions_value FROM equity_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return {"equity": starting_balance, "pnl": 0.0, "pnl_pct": 0.0}

        equity = row[0]
        pnl = equity - starting_balance
        pnl_pct = (pnl / starting_balance) * 100 if starting_balance > 0 else 0.0
        return {"equity": equity, "pnl": pnl, "pnl_pct": pnl_pct}
