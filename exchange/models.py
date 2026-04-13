from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Candle:
    pair: str
    granularity: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    action: str  # "buy" or "sell"
    pair: str
    price: float  # current market price when signal generated
    order_type: str  # "market" or "limit"
    amount_usd: float | None = None
    amount_crypto: float | None = None
    limit_price: float | None = None
    reason: str = ""
    regime: str = ""
    adx: float = 0.0
    rsi: float = 0.0
    atr_multiplier: float = 1.0


@dataclass
class Trade:
    timestamp: datetime
    pair: str
    side: str  # "buy" or "sell"
    price: float  # fill price
    amount: float  # crypto amount
    cost_usd: float  # total USD including fees
    fee: float  # fee in USD
    strategy: str
    reason: str = ""
    regime: str = ""
    adx: float = 0.0
    rsi: float = 0.0
    atr_multiplier: float = 1.0


@dataclass
class Position:
    pair: str
    amount: float
    avg_entry_price: float
    cost_basis: float


@dataclass
class BacktestResult:
    total_trades: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    equity_curve: list[float] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
