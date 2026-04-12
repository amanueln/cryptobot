"""Momentum Rotation Engine — portfolio-level strategy that picks top coins by acceleration.

Optimized config (backtested on full ZimaOS data, +107%):
- Weekly rebalance: pick top 1 coin by momentum acceleration
- BTC regime filter with 5% hysteresis band (prevents daily whipsaw)
- 20% re-entry threshold: only enter on very strong signals
- RSI < 65 filter: blocks overbought entries
- 15% equity trailing stop: protects profits when portfolio drops from peak
- 4-hour cooldown after exits: brief pause, then re-enter on next signal
- No position-level trailing stops (avoids whipsaw losses)

This engine is independent from the grid engine — it has its own cash pool,
positions, and equity tracking.
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from exchange.models import Candle, Trade

logger = logging.getLogger(__name__)

DEFAULT_PAIRS = [
    'ETH-USD', 'BTC-USD', 'ADA-USD', 'LINK-USD', 'UNI-USD',
    'ALGO-USD', 'DOGE-USD', 'DOT-USD', 'SOL-USD', 'AVAX-USD',
]

# Keep PAIRS as alias for backward compat (sim_runner imports it)
PAIRS = DEFAULT_PAIRS

# Strategy params (optimized via ZimaOS data replay)
TOP_N = 1                 # concentrate on single best coin
REBAL_HOURS = 168         # weekly
SHORT_LB = 336            # 14 days in hours
LONG_LB = 720             # 30 days in hours
REGIME_MA = 500            # BTC SMA period (hourly)
REGIME_HYSTERESIS = 0.05   # 5% band — BTC must be 5% above SMA to go bullish
REENTRY_THRESHOLD = 0.20   # 20% — only enter on very strong signals
FEE_RATE = 0.006           # Coinbase taker fee
RSI_MAX = 65               # block entries when RSI > 65 (overbought)
RSI_PERIOD = 14            # RSI lookback
EQUITY_TRAIL_PCT = 0.15    # exit all if equity drops 15% from peak
EXIT_COOLDOWN = 4          # hours to wait after exit before re-entering
MIN_HOLD_HOURS = 0         # no minimum hold — hysteresis prevents whipsaw
ATR_PERIOD = 24            # 24-hour ATR (used for dashboard info only)
HARD_STOP_PCT = 0.15       # kept for dashboard display only


def _sma(values: list[float], period: int) -> float | None:
    """Simple moving average of last `period` values."""
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _rsi(closes: list[float], period: int = 14) -> float | None:
    """Relative Strength Index."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> float | None:
    """Average True Range over last `period` candles."""
    if len(highs) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return sum(trs) / len(trs)


@dataclass
class MomentumHolding:
    pair: str
    shares: float
    entry_price: float
    entry_time: datetime
    peak_price: float = 0.0     # highest price since entry
    stop_price: float = 0.0     # current trailing stop level


@dataclass
class AccelScore:
    pair: str
    accel: float
    short_mom: float
    long_mom: float


class MomentumEngine:
    """Self-contained momentum rotation engine with its own cash and positions."""

    def __init__(self, allocation_usd: float, fee_rate: float = FEE_RATE,
                 pairs: list[str] | None = None):
        self.starting_balance = allocation_usd
        self.cash = allocation_usd
        self.fee_rate = fee_rate
        self.holdings: dict[str, MomentumHolding] = {}
        self.pairs: list[str] = list(pairs) if pairs else list(DEFAULT_PAIRS)

        # Candle history per pair (need LONG_LB + REGIME_MA worth of closes)
        self._closes: dict[str, list[float]] = {p: [] for p in self.pairs}
        self._highs: dict[str, list[float]] = {p: [] for p in self.pairs}
        self._lows: dict[str, list[float]] = {p: [] for p in self.pairs}
        self._timestamps: dict[str, list[datetime]] = {p: [] for p in self.pairs}

        # BTC closes for regime MA
        self._btc_closes: list[float] = []

        # State
        self._was_cash = True
        self._hours_since_rebal = 0
        self._hours_since_regime_check = 0
        self._last_candle_ts: datetime | None = None
        self._candles_fed = 0
        self._warmup_done = False
        self._regime_state = "unknown"  # "bullish", "bearish", "unknown"
        self._exit_cooldown = 0         # hours remaining before re-entry allowed
        self._hours_in_position = 0     # tracks min hold period

        # Trade history (for logging)
        self.trades: list[Trade] = []
        self.trade_count = 0

        # Equity tracking
        self._last_equity = allocation_usd
        self._peak_equity = allocation_usd  # for equity trailing stop

        # Status info for dashboard
        self.status = "warming_up"
        self.status_detail = "Building price history..."
        self.regime_bullish = False
        self.btc_price = 0.0
        self.btc_ma = 0.0
        self.next_rebal_hours = REBAL_HOURS
        self.accel_scores: list[AccelScore] = []

    def update_pairs(self, new_pairs: list[str]):
        """Update the tracked pair universe (called after scanner rescan).

        Preserves candle history for pairs that stay in the list.
        Adds empty history for new pairs. Drops data for removed pairs
        (unless we're currently holding them — those get kept until sold).
        """
        # Always keep BTC for regime
        if 'BTC-USD' not in new_pairs:
            new_pairs = ['BTC-USD'] + new_pairs

        # Keep pairs we currently hold (even if scanner dropped them)
        held = set(self.holdings.keys())
        kept = set(new_pairs) | held | {'BTC-USD'}

        # Add new pairs
        for p in kept:
            if p not in self._closes:
                self._closes[p] = []
                self._highs[p] = []
                self._lows[p] = []
                self._timestamps[p] = []

        # Remove pairs we no longer track (and don't hold)
        for p in list(self._closes.keys()):
            if p not in kept:
                del self._closes[p]
                del self._highs[p]
                del self._lows[p]
                del self._timestamps[p]

        self.pairs = list(kept)
        logger.info("Momentum engine: updated to %d pairs", len(self.pairs))

    def feed_candle(self, pair: str, candle: Candle, warmup: bool = False) -> list[Trade]:
        """Feed a single candle for a single pair. Returns any trades executed."""
        if pair not in self._closes:
            return []

        # Deduplicate
        ts_list = self._timestamps[pair]
        if ts_list and candle.timestamp <= ts_list[-1]:
            return []

        self._closes[pair].append(candle.close)
        self._highs[pair].append(candle.high)
        self._lows[pair].append(candle.low)
        self._timestamps[pair].append(candle.timestamp)
        self._candles_fed += 1

        # Keep history bounded (need max of LONG_LB + some buffer)
        max_hist = max(LONG_LB, REGIME_MA) + 100
        if len(self._closes[pair]) > max_hist:
            self._closes[pair] = self._closes[pair][-max_hist:]
            self._highs[pair] = self._highs[pair][-max_hist:]
            self._lows[pair] = self._lows[pair][-max_hist:]
            self._timestamps[pair] = self._timestamps[pair][-max_hist:]

        # Update peak price for held positions (for dashboard display)
        if pair in self.holdings:
            h = self.holdings[pair]
            if candle.close > h.peak_price:
                h.peak_price = candle.close
            # No position-level trailing stops — equity trailing stop handles risk
            h.stop_price = 0

        # Track BTC separately for regime — with hysteresis band
        if pair == 'BTC-USD':
            self._btc_closes = self._closes['BTC-USD']
            self.btc_price = candle.close
            btc_ma = _sma(self._btc_closes, REGIME_MA)
            if btc_ma is not None:
                self.btc_ma = btc_ma
                # Hysteresis: need 5% above SMA to go bullish, 5% below to go bearish
                if self._regime_state in ("bearish", "unknown"):
                    if self.btc_price >= btc_ma * (1 + REGIME_HYSTERESIS):
                        self._regime_state = "bullish"
                        self.regime_bullish = True
                elif self._regime_state == "bullish":
                    if self.btc_price <= btc_ma * (1 - REGIME_HYSTERESIS):
                        self._regime_state = "bearish"
                        self.regime_bullish = False

        if warmup:
            return []

        # Check if BTC has enough data (required for regime)
        if len(self._btc_closes) < REGIME_MA:
            self.status = "warming_up"
            self.status_detail = f"BTC MA needs {REGIME_MA} candles, have {len(self._btc_closes)}"
            return []

        # Count pairs with enough data (don't let one short pair block everything)
        ready_pairs = [p for p in self.pairs if len(self._closes[p]) >= LONG_LB + 1]
        if len(ready_pairs) < 3:
            self.status = "warming_up"
            self.status_detail = f"Need 3+ pairs with {LONG_LB + 1} candles, have {len(ready_pairs)}"
            return []

        self._warmup_done = True

        # Only process logic on BTC candle (all pairs should be hourly aligned)
        if pair != 'BTC-USD':
            return []

        # === Equity trailing stop (portfolio-level, not per-position) ===
        trades = []
        if self.holdings:
            equity = self.get_equity()
            if equity > self._peak_equity:
                self._peak_equity = equity
            # Only trigger if we've been profitable (peak > starting balance)
            if self._peak_equity > self.starting_balance and equity < self._peak_equity * (1 - EQUITY_TRAIL_PCT):
                exit_trades = self._exit_all(candle.timestamp,
                    f"Equity trailing stop ({EQUITY_TRAIL_PCT*100:.0f}% from peak ${self._peak_equity:,.0f})")
                trades.extend(exit_trades)
                self._was_cash = True
                self._peak_equity = equity  # reset peak
                self._exit_cooldown = EXIT_COOLDOWN
                self._hours_in_position = 0
                self.status = "cash"
                self.status_detail = "Equity stop — protecting profits"
                logger.info("Equity trailing stop triggered at $%.2f (peak was $%.2f)",
                            equity, self._peak_equity)
                return trades

        self._last_candle_ts = candle.timestamp
        self._hours_since_rebal += 1
        self._hours_since_regime_check += 1

        # Decrement cooldown timer
        if self._exit_cooldown > 0:
            self._exit_cooldown -= 1

        # Track time in position
        if self.holdings:
            self._hours_in_position += 1

        trades = []

        # === Daily regime check (every 24 hours) ===
        if self._hours_since_regime_check >= 24:
            self._hours_since_regime_check = 0
            if not self.regime_bullish and self.holdings:
                # Only exit if we've held long enough (min hold period)
                if self._hours_in_position >= MIN_HOLD_HOURS:
                    exit_trades = self._exit_all(candle.timestamp, "Regime bearish — daily check")
                    trades.extend(exit_trades)
                    self._was_cash = True
                    self._exit_cooldown = EXIT_COOLDOWN
                    self._hours_in_position = 0
                    self.status = "cash"
                    self.status_detail = "BTC regime bearish — holding cash"

        # === Immediate entry from cash (if cooldown expired) ===
        if self._was_cash and not self.holdings and self._exit_cooldown <= 0:
            if self.regime_bullish:
                scores = self._compute_scores()
                self.accel_scores = scores
                qualifying = [s for s in scores if s.accel > REENTRY_THRESHOLD]
                if qualifying:
                    logger.info("Immediate entry: %d coins above %.0f%% threshold",
                                len(qualifying), REENTRY_THRESHOLD * 100)
                    self._was_cash = False
                    winners = qualifying[:TOP_N]
                    investable = self.cash * 0.95
                    per = investable / len(winners)
                    for s in winners:
                        if per > 1:
                            t = self._buy(s.pair, per, candle.timestamp,
                                          f"Immediate entry: {s.accel:+.1%} acceleration")
                            if t:
                                trades.append(t)
                    # Reset peak equity on new entry
                    self._peak_equity = self.get_equity()
                    self._hours_in_position = 0
                    held = [h.pair.replace('-USD', '') for h in self.holdings.values()]
                    self.status = "holding"
                    self.status_detail = f"Holding {', '.join(held)}"
                    self._hours_since_rebal = 0
                    return trades

        # === Weekly rebalance (rotation between positions) ===
        if self._hours_since_rebal >= REBAL_HOURS:
            self._hours_since_rebal = 0
            self.next_rebal_hours = REBAL_HOURS

            # If bearish regime, go to cash (only if held long enough)
            if not self.regime_bullish:
                if self.holdings and self._hours_in_position >= MIN_HOLD_HOURS:
                    exit_trades = self._exit_all(candle.timestamp, "Regime bearish at rebalance")
                    trades.extend(exit_trades)
                    self._was_cash = True
                    self._exit_cooldown = EXIT_COOLDOWN
                    self._hours_in_position = 0
                if not self.holdings:
                    self.status = "cash"
                    self.status_detail = "BTC regime bearish — waiting for trend"
            elif self._exit_cooldown <= 0:
                # Compute acceleration scores
                scores = self._compute_scores()
                self.accel_scores = scores

                # Apply reentry threshold if coming from cash
                if self._was_cash and REENTRY_THRESHOLD > 0:
                    scores = [s for s in scores if s.accel > REENTRY_THRESHOLD]

                if not scores:
                    # No qualifying coins — go to cash (only if held long enough)
                    if self.holdings and self._hours_in_position >= MIN_HOLD_HOURS:
                        exit_trades = self._exit_all(candle.timestamp, "No qualifying acceleration scores")
                        trades.extend(exit_trades)
                    if not self.holdings:
                        self._was_cash = True
                        self.status = "cash"
                        self.status_detail = f"No coins above {REENTRY_THRESHOLD:.0%} re-entry threshold"
                else:
                    self._was_cash = False
                    winners = set(s.pair for s in scores[:TOP_N])

                    # Sell holdings not in winners (only if held long enough)
                    if self._hours_in_position >= MIN_HOLD_HOURS:
                        for pair_key in list(self.holdings.keys()):
                            if pair_key not in winners:
                                t = self._sell(pair_key, candle.timestamp, "Rotated out — no longer top acceleration")
                                if t:
                                    trades.append(t)

                    # Buy new winners
                    investable = self.cash * 0.95
                    n_buy = len(winners) - len(self.holdings)
                    if n_buy > 0 and investable > 10:
                        per = investable / n_buy
                        for s in scores[:TOP_N]:
                            if s.pair not in self.holdings and per > 1:
                                t = self._buy(s.pair, per, candle.timestamp,
                                              f"Top acceleration: {s.accel:+.1%}")
                                if t:
                                    trades.append(t)
                                    self._hours_in_position = 0
                                    # Reset peak equity on new entry
                                    self._peak_equity = self.get_equity()

                    held = [h.pair.replace('-USD', '') for h in self.holdings.values()]
                    self.status = "holding"
                    self.status_detail = f"Holding {', '.join(held)}"
        else:
            self.next_rebal_hours = REBAL_HOURS - self._hours_since_rebal

        return trades

    def _compute_scores(self) -> list[AccelScore]:
        """Compute momentum acceleration scores for all pairs."""
        scores = []
        for pair in self.pairs:
            closes = self._closes[pair]
            if len(closes) < LONG_LB + 1:
                continue
            short_mom = closes[-1] / closes[-SHORT_LB] - 1
            long_mom = closes[-1] / closes[-LONG_LB] - 1
            accel = short_mom - (long_mom * SHORT_LB / LONG_LB)
            if long_mom <= 0:
                continue
            if accel <= 0:
                continue
            # RSI filter: skip overbought coins
            rsi = _rsi(closes, RSI_PERIOD)
            if rsi is not None and rsi > RSI_MAX:
                continue
            scores.append(AccelScore(pair=pair, accel=accel, short_mom=short_mom, long_mom=long_mom))
        scores.sort(key=lambda s: s.accel, reverse=True)
        return scores

    def check_stop_ticker(self, pair: str, price: float) -> Trade | None:
        """Check equity trailing stop using live ticker prices.

        Updates peak prices and checks portfolio-level equity stop.
        Returns a Trade if stopped out, else None.
        """
        if pair not in self.holdings:
            return None
        h = self.holdings[pair]

        # Update peak price for tracking
        if price > h.peak_price:
            h.peak_price = price

        # Update closes for equity calculation
        if self._closes.get(pair):
            self._closes[pair][-1] = price

        # Check equity trailing stop
        equity = self.get_equity()
        if equity > self._peak_equity:
            self._peak_equity = equity

        if self._peak_equity > self.starting_balance and equity < self._peak_equity * (1 - EQUITY_TRAIL_PCT):
            now = datetime.now()
            reason = f"Equity stop ({EQUITY_TRAIL_PCT*100:.0f}% from peak ${self._peak_equity:,.0f})"
            # Sell all holdings
            trades = self._exit_all(now, reason)
            self._was_cash = True
            self._peak_equity = equity
            self._exit_cooldown = EXIT_COOLDOWN
            self._hours_in_position = 0
            self.status = "cash"
            self.status_detail = "Equity stop — protecting profits"
            logger.info("Equity trailing stop at $%.2f (peak $%.2f)", equity, self._peak_equity)
            return trades[0] if trades else None
        return None

    def _buy(self, pair: str, amount_usd: float, timestamp: datetime, reason: str) -> Trade | None:
        """Buy a coin with given USD amount."""
        if amount_usd > self.cash or amount_usd < 1:
            return None

        price = self._closes[pair][-1]
        fee = amount_usd * self.fee_rate
        crypto_amount = (amount_usd - fee) / price
        self.cash -= amount_usd

        # No position-level stops — equity trailing stop protects the portfolio
        self.holdings[pair] = MomentumHolding(
            pair=pair, shares=crypto_amount, entry_price=price, entry_time=timestamp,
            peak_price=price, stop_price=0,
        )

        trade = Trade(
            timestamp=timestamp, pair=pair, side="buy", price=price,
            amount=crypto_amount, cost_usd=amount_usd, fee=fee,
            strategy="momentum_rotation", reason=reason,
        )
        self.trades.append(trade)
        self.trade_count += 1
        return trade

    def _sell(self, pair: str, timestamp: datetime, reason: str) -> Trade | None:
        """Sell all holdings of a coin."""
        holding = self.holdings.get(pair)
        if not holding:
            return None

        price = self._closes[pair][-1]
        gross_usd = holding.shares * price
        fee = gross_usd * self.fee_rate
        net_usd = gross_usd - fee
        self.cash += net_usd

        del self.holdings[pair]

        trade = Trade(
            timestamp=timestamp, pair=pair, side="sell", price=price,
            amount=holding.shares, cost_usd=net_usd, fee=fee,
            strategy="momentum_rotation", reason=reason,
        )
        self.trades.append(trade)
        self.trade_count += 1
        return trade

    def _exit_all(self, timestamp: datetime, reason: str) -> list[Trade]:
        """Sell all holdings and go to cash."""
        trades = []
        for pair in list(self.holdings.keys()):
            t = self._sell(pair, timestamp, reason)
            if t:
                trades.append(t)
        return trades

    def get_equity(self) -> float:
        """Current total equity = cash + holdings value."""
        equity = self.cash
        for pair, holding in self.holdings.items():
            if self._closes[pair]:
                equity += holding.shares * self._closes[pair][-1]
        self._last_equity = equity
        return equity

    def get_positions_value(self) -> float:
        """Current value of all held positions."""
        value = 0.0
        for pair, holding in self.holdings.items():
            if self._closes[pair]:
                value += holding.shares * self._closes[pair][-1]
        return value

    def get_pnl(self) -> float:
        return self.get_equity() - self.starting_balance

    def get_holdings_info(self) -> list[dict]:
        """Return holdings with current values for dashboard."""
        info = []
        for pair, h in self.holdings.items():
            current_price = self._closes[pair][-1] if self._closes[pair] else 0
            value = h.shares * current_price
            pnl = value - (h.shares * h.entry_price)
            pnl_pct = (current_price / h.entry_price - 1) * 100 if h.entry_price > 0 else 0

            # Find accel score
            accel = 0.0
            for s in self.accel_scores:
                if s.pair == pair:
                    accel = s.accel
                    break

            # Distance to stop
            stop_distance_pct = ((current_price - h.stop_price) / current_price * 100) if current_price > 0 and h.stop_price > 0 else 0

            info.append({
                "pair": pair,
                "shares": h.shares,
                "entry_price": h.entry_price,
                "current_price": current_price,
                "value": value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "accel": accel,
                "entry_time": h.entry_time.isoformat(),
                "peak_price": h.peak_price,
                "stop_price": h.stop_price,
                "stop_distance_pct": stop_distance_pct,
            })
        return info

    def get_status_dict(self) -> dict:
        """Full status for API/dashboard."""
        equity = self.get_equity()
        return {
            "engine": "momentum_rotation",
            "status": self.status,
            "status_detail": self.status_detail,
            "equity": equity,
            "cash": self.cash,
            "positions_value": self.get_positions_value(),
            "pnl": equity - self.starting_balance,
            "pnl_pct": ((equity / self.starting_balance) - 1) * 100 if self.starting_balance > 0 else 0,
            "starting_balance": self.starting_balance,
            "trade_count": self.trade_count,
            "holdings": self.get_holdings_info(),
            "regime_bullish": self.regime_bullish,
            "btc_price": self.btc_price,
            "btc_ma": self.btc_ma,
            "next_rebal_hours": self.next_rebal_hours,
            "accel_scores": [
                {"pair": s.pair, "accel": s.accel, "short_mom": s.short_mom, "long_mom": s.long_mom}
                for s in self.accel_scores
            ],
            "was_cash": self._was_cash,
            "warmup_done": self._warmup_done,
            "candles_fed": self._candles_fed,
            "pairs_tracked": len(self.pairs),
            "regime_state": self._regime_state,
            "regime_hysteresis": REGIME_HYSTERESIS,
            "exit_cooldown_remaining": self._exit_cooldown,
            "hours_in_position": self._hours_in_position,
        }
