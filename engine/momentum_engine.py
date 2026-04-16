from __future__ import annotations

"""Momentum Rotation Engine — portfolio-level strategy that picks top coins by acceleration.

Optimized config (3-round backtest: +51.8% avg, profitable in all 3 market conditions):

ENTRY:
- Weekly rebalance: pick top 1 coin by momentum acceleration (>10% threshold)
- BTC regime filter with 5% hysteresis band (prevents daily whipsaw)
- ADX > 25 entry filter: only enter when trend is confirmed strong
- RSI > 50 entry filter: confirm uptrend direction
- RSI < 65 filter: blocks overbought entries
- Same-coin 24h lockout: prevents whipsaw re-entry after selling

EXIT (layered — first trigger wins):
- Delayed+Stale trailing stop: 3-layer adaptive trail tested on 159 scanner alerts
  Layer 1: Wide 5% trail activates at +2% peak (breathing room)
  Layer 2: Tightens to 2.5% after 30 min above +5% (confirmed move)
  Layer 3: Tightens to 2.0% if no new high for 30 min (fading move)
- 2.5x ATR smart stop: per-coin floor set at entry based on coin's own volatility
- Accel < 5% hourly exit: sell when momentum fades (take profit before giveback)
- 72h max hold: force exit stale positions that aren't moving
- 15% equity trailing stop: emergency backstop (should rarely fire now)

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

# Strategy params (optimized via 3-round backtesting across stale/bear/sideways markets)
TOP_N = 1                 # concentrate on single best coin
REBAL_HOURS = 168         # weekly
SHORT_LB = 336            # 14 days in hours
LONG_LB = 720             # 30 days in hours
REGIME_MA = 500            # BTC SMA period (hourly)
REGIME_HYSTERESIS = 0.05   # 5% band — BTC must be 5% above SMA to go bullish
REENTRY_THRESHOLD = 0.10   # 10% — enter on strong signals (20% was too restrictive for normal markets)
FEE_RATE = 0.006           # Coinbase taker fee
RSI_MAX = 65               # block entries when RSI > 65 (overbought)
RSI_PERIOD = 14            # RSI lookback
EQUITY_TRAIL_PCT = 0.15    # emergency backstop — portfolio-level (should rarely fire now)
EXIT_COOLDOWN = 1          # hours to wait after exit before re-entering (was 4h, sim shows 1h optimal)
MIN_HOLD_HOURS = 0         # no minimum hold — hysteresis prevents whipsaw
ATR_PERIOD = 24            # ATR lookback for smart stop calculation

# New exit rules (Round 3 winner: +51.8% avg across 3 market conditions, 3/3 profitable)
ATR_STOP_MULT = 2.5        # stop at entry - 2.5 * ATR (adapts to each coin's volatility)
ATR_STOP_LOOKBACK = 24     # hours of ATR to measure coin's volatility
ACCEL_EXIT_THRESH = 0.05   # exit when momentum acceleration fades below 5%
ACCEL_EXIT_MIN_HOLD = 4    # don't check accel exit until held for 4 hours
MAX_HOLD_HOURS = 72        # force exit after 3 days — prevents slow bleed

# Delayed+Stale trailing stop — validated on 159 scanner alerts + 9 momentum trades
# Captures 70-90% of big moves while capping dud losses at initial stop
TRAIL_WIDE_PCT = 5.0       # Layer 1: wide trail when peak >= activation (breathing room)
TRAIL_ACTIVATE_PCT = 2.0   # peak PnL% needed to activate wide trail
TRAIL_TIGHT_PCT = 2.5      # Layer 2: tighter trail after delay period above threshold
TRAIL_TIGHTEN_PCT = 5.0    # peak PnL% needed before tight trail can activate
TRAIL_DELAY_TICKS = 30     # ticks (minutes) above tighten threshold before tight trail activates
TRAIL_STALE_PCT = 2.0      # Layer 3: tightest trail when peak goes stale (no new high)
TRAIL_STALE_TICKS = 30     # ticks (minutes) with no new high = stale peak

# New entry filters (Round 1 winner: only strategy profitable in choppy markets)
ADX_FILTER_THRESH = 25     # only enter when ADX > 25 (confirmed trend strength)
RSI_TREND_THRESH = 50      # only enter when RSI > 50 (uptrend confirmed)
LOCKOUT_HOURS = 24         # after selling a coin, don't re-buy it for 24h
LOSS_LOCKOUT_HOURS = 72    # after losing on a coin, don't re-buy for 72h
MIN_PRICE = 0.01           # skip sub-penny coins — price data too noisy for momentum signals


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


def _adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    """Average Directional Index — measures trend strength (0-100)."""
    if len(closes) < period * 3:
        return None
    h = highs[-(period * 3):]
    l = lows[-(period * 3):]
    c = closes[-(period * 3):]
    plus_dm, minus_dm, tr_list = [], [], []
    for i in range(1, len(h)):
        hi_diff = h[i] - h[i - 1]
        lo_diff = l[i - 1] - l[i]
        plus_dm.append(hi_diff if hi_diff > lo_diff and hi_diff > 0 else 0)
        minus_dm.append(lo_diff if lo_diff > hi_diff and lo_diff > 0 else 0)
        tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        tr_list.append(tr)
    if len(tr_list) < period:
        return None
    atr = sum(tr_list[:period]) / period
    plus_di_sum = sum(plus_dm[:period])
    minus_di_sum = sum(minus_dm[:period])
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        plus_di_sum = (plus_di_sum * (period - 1) + plus_dm[i]) / period
        minus_di_sum = (minus_di_sum * (period - 1) + minus_dm[i]) / period
    if atr == 0:
        return None
    plus_di = 100 * plus_di_sum / atr
    minus_di = 100 * minus_di_sum / atr
    di_sum = plus_di + minus_di
    if di_sum == 0:
        return None
    return 100 * abs(plus_di - minus_di) / di_sum


@dataclass
class MomentumHolding:
    pair: str
    shares: float
    entry_price: float
    entry_time: datetime
    peak_price: float = 0.0          # highest price since entry
    atr_stop_price: float = 0.0      # ATR stop set at entry — floor, never moves
    trail_stop_price: float = 0.0    # tightening trail — ratchets up
    ticks_above_tighten: int = 0     # how many ticks peak has been above TRAIL_TIGHTEN_PCT
    ticks_since_new_peak: int = 0    # how many ticks since last new high (stale peak detection)


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
        self._last_sold_pair: str | None = None   # same-coin lockout
        self._last_sold_time: datetime | None = None
        self._loss_lockouts: dict[str, datetime] = {}  # pair -> lockout expiry after a loss
        self._entry_rejections: list[str] = []  # why coins were rejected this tick

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

        # Update peak price for held positions (also checks candle high)
        if pair in self.holdings:
            h = self.holdings[pair]
            if candle.high > h.peak_price:
                h.peak_price = candle.high
                h.ticks_since_new_peak = 0

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

        # === EXIT LOGIC ===
        trades = []
        if self.holdings:
            equity = self.get_equity()
            if equity > self._peak_equity:
                self._peak_equity = equity

            # Emergency backstop: equity trailing stop (should rarely fire with new exits)
            if self._peak_equity > self.starting_balance and equity < self._peak_equity * (1 - EQUITY_TRAIL_PCT):
                exit_trades = self._exit_all(candle.timestamp,
                    f"Equity trailing stop ({EQUITY_TRAIL_PCT*100:.0f}% from peak ${self._peak_equity:,.0f})")
                trades.extend(exit_trades)
                self._was_cash = True
                self._peak_equity = equity
                self._exit_cooldown = EXIT_COOLDOWN
                self._hours_in_position = 0
                self.status = "cash"
                self.status_detail = "Equity stop — protecting profits"
                logger.info("Equity trailing stop triggered at $%.2f (peak was $%.2f)",
                            equity, self._peak_equity)
                return trades

            # Per-position exit checks
            for pair_key in list(self.holdings.keys()):
                h = self.holdings[pair_key]
                price = self._closes[pair_key][-1] if self._closes[pair_key] else 0
                if price <= 0:
                    continue
                should_exit = False
                reason = ""

                # 0. Update trailing stop (runs on every tick + hourly candle)
                self._update_trail_stop(h, price)

                # 1. Check effective stop (max of ATR floor and trailing stop)
                effective_stop = max(h.atr_stop_price, h.trail_stop_price)
                if effective_stop > 0 and price <= effective_stop:
                    should_exit = True
                    if h.trail_stop_price > h.atr_stop_price and h.trail_stop_price > 0:
                        pnl_pct = (price - h.entry_price) / h.entry_price * 100 if h.entry_price > 0 else 0
                        reason = f"Trail stop hit: ${price:,.4f} <= ${h.trail_stop_price:,.4f} (locked +{pnl_pct:.1f}%)"
                    else:
                        stop_dist = (h.entry_price - h.atr_stop_price) / h.entry_price * 100 if h.entry_price > 0 else 0
                        reason = f"ATR stop hit: ${price:,.4f} <= ${h.atr_stop_price:,.4f} ({stop_dist:.1f}% from entry)"

                # 2. Accel faded exit (momentum died — take profit before it gives back)
                if not should_exit and self._hours_in_position >= ACCEL_EXIT_MIN_HOLD:
                    accel = self._get_accel(pair_key)
                    if accel is not None and accel < ACCEL_EXIT_THRESH:
                        should_exit = True
                        reason = f"Accel faded: {accel:.1%} < {ACCEL_EXIT_THRESH:.0%} threshold"

                # 3. Max hold duration (kill stale positions)
                if not should_exit and self._hours_in_position >= MAX_HOLD_HOURS:
                    should_exit = True
                    reason = f"Max hold {MAX_HOLD_HOURS}h reached"

                if should_exit:
                    t = self._sell(pair_key, candle.timestamp, reason)
                    if t:
                        trades.append(t)

            if trades:
                self._was_cash = True
                self._exit_cooldown = EXIT_COOLDOWN
                self._hours_in_position = 0
                self.status = "cash"
                self.status_detail = trades[0].reason if trades else "Exited position"
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

        # === Immediate entry from cash (if cooldown expired and no positions) ===
        self._entry_rejections = []  # track why coins are rejected
        if self._was_cash and not self.holdings and self._exit_cooldown <= 0 and self.cash > self.starting_balance * 0.5:
            if not self.regime_bullish:
                self._entry_rejections.append("BTC regime is bearish — no entries allowed")
            if self.regime_bullish:
                scores = self._compute_scores()
                self.accel_scores = scores
                qualifying = [s for s in scores if s.accel > REENTRY_THRESHOLD]
                below_thresh = [s for s in scores if s.accel <= REENTRY_THRESHOLD]
                for s in below_thresh:
                    self._entry_rejections.append(f"{s.pair}: accel {s.accel:.1%} < {REENTRY_THRESHOLD:.0%} threshold")

                # Same-coin lockout: don't re-buy what we just sold for 24h
                if self._last_sold_pair and self._last_sold_time:
                    if candle.timestamp < self._last_sold_time + timedelta(hours=LOCKOUT_HOURS):
                        locked = [s for s in qualifying if s.pair == self._last_sold_pair]
                        for s in locked:
                            self._entry_rejections.append(f"{s.pair}: same-coin lockout ({LOCKOUT_HOURS}h)")
                        qualifying = [s for s in qualifying if s.pair != self._last_sold_pair]

                # Entry filters: ADX > 25 and RSI > 50
                qualifying = self._filter_entries(qualifying)

                if qualifying:
                    logger.info("Immediate entry: %d coins passed all filters (accel+ADX+RSI)",
                                len(qualifying))
                    self._was_cash = False
                    winners = qualifying[:TOP_N]
                    investable = self.cash * 0.99
                    per = investable / len(winners)
                    for s in winners:
                        if per > 1:
                            t = self._buy(s.pair, per, candle.timestamp,
                                          f"Immediate entry: {s.accel:+.1%} accel (ADX+RSI confirmed)")
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

                # Apply reentry threshold and filters if coming from cash
                if self._was_cash and REENTRY_THRESHOLD > 0:
                    scores = [s for s in scores if s.accel > REENTRY_THRESHOLD]
                    # Same-coin lockout
                    if self._last_sold_pair and self._last_sold_time:
                        if candle.timestamp < self._last_sold_time + timedelta(hours=LOCKOUT_HOURS):
                            scores = [s for s in scores if s.pair != self._last_sold_pair]
                    scores = self._filter_entries(scores)

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
                    investable = self.cash * 0.99
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
        now = self._last_candle_ts or datetime.now()
        for pair in self.pairs:
            closes = self._closes[pair]
            if len(closes) < LONG_LB + 1:
                continue
            # Skip sub-penny coins — price data too noisy for reliable momentum
            if closes[-1] < MIN_PRICE:
                self._entry_rejections.append(f"{pair}: price ${closes[-1]:.4f} < ${MIN_PRICE} (sub-penny)")
                continue
            # Skip coins in loss lockout (lost money recently, don't re-enter)
            if pair in self._loss_lockouts:
                if now < self._loss_lockouts[pair]:
                    self._entry_rejections.append(f"{pair}: loss lockout (lost money recently)")
                    continue
                else:
                    del self._loss_lockouts[pair]
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

    def _filter_entries(self, qualifying: list[AccelScore]) -> list[AccelScore]:
        """Apply ADX > 25 and RSI > 50 entry filters."""
        if not qualifying:
            return []
        filtered = []
        for s in qualifying:
            pair = s.pair
            closes = self._closes.get(pair, [])
            highs = self._highs.get(pair, [])
            lows = self._lows.get(pair, [])

            # ADX filter: only enter when trend is strong
            adx = _adx(highs, lows, closes)
            if adx is not None and adx < ADX_FILTER_THRESH:
                logger.debug("Entry filter: %s rejected — ADX %.1f < %d", pair, adx, ADX_FILTER_THRESH)
                self._entry_rejections.append(f"{pair}: ADX {adx:.1f} < {ADX_FILTER_THRESH} (weak trend)")
                continue

            # RSI > 50 filter: confirm uptrend
            if len(closes) >= RSI_PERIOD + 1:
                rsi = _rsi(closes, RSI_PERIOD)
                if rsi is not None and rsi < RSI_TREND_THRESH:
                    logger.debug("Entry filter: %s rejected — RSI %.1f < %d", pair, rsi, RSI_TREND_THRESH)
                    self._entry_rejections.append(f"{pair}: RSI {rsi:.1f} < {RSI_TREND_THRESH} (not in uptrend)")
                    continue

            filtered.append(s)
        return filtered

    def _get_accel(self, pair: str) -> float | None:
        """Get current momentum acceleration for a held pair."""
        closes = self._closes.get(pair, [])
        if len(closes) < LONG_LB + 1:
            return None
        short_mom = (closes[-1] / closes[-SHORT_LB]) - 1
        long_mom = (closes[-1] / closes[-LONG_LB]) - 1
        return short_mom - long_mom

    def _update_trail_stop(self, holding: MomentumHolding, price: float | None = None) -> None:
        """Update the delayed+stale trailing stop for a position.

        Called on every ticker tick (~60s) and on hourly candle close.
        Three layers that progressively tighten as the move matures:

        Layer 1 (wide): 5% trail from peak when peak PnL >= 2% — gives breathing room
        Layer 2 (tight): 2.5% trail after price has been above +5% for 30 ticks — confirmed move
        Layer 3 (stale): 2.0% trail if no new high for 30 ticks — move is fading, protect profit
        """
        if holding.peak_price <= 0 or holding.entry_price <= 0:
            return

        cur_price = price if price is not None else holding.peak_price

        # Update peak tracking
        if cur_price > holding.peak_price:
            holding.peak_price = cur_price
            holding.ticks_since_new_peak = 0
        else:
            holding.ticks_since_new_peak += 1

        peak_pct = (holding.peak_price - holding.entry_price) / holding.entry_price * 100

        # Track time above tighten threshold
        if peak_pct >= TRAIL_TIGHTEN_PCT:
            holding.ticks_above_tighten += 1

        new_stop = holding.trail_stop_price

        # Layer 1: Wide trail when peak >= activation (breathing room for early move)
        if peak_pct >= TRAIL_ACTIVATE_PCT:
            new_stop = max(new_stop, holding.peak_price * (1 - TRAIL_WIDE_PCT / 100))

        # Layer 2: Tight trail after confirmed above threshold for delay period
        if peak_pct >= TRAIL_TIGHTEN_PCT and holding.ticks_above_tighten >= TRAIL_DELAY_TICKS:
            new_stop = max(new_stop, holding.peak_price * (1 - TRAIL_TIGHT_PCT / 100))

        # Layer 3: Stale peak — no new high for stale period, move is fading
        if peak_pct >= TRAIL_TIGHTEN_PCT and holding.ticks_since_new_peak >= TRAIL_STALE_TICKS:
            new_stop = max(new_stop, holding.peak_price * (1 - TRAIL_STALE_PCT / 100))

        # Never go below ATR stop floor
        if holding.atr_stop_price > 0:
            new_stop = max(new_stop, holding.atr_stop_price)

        # Ratchet: only move up
        if new_stop > holding.trail_stop_price:
            old_stop = holding.trail_stop_price
            holding.trail_stop_price = new_stop
            # Determine which layer set this stop
            layer = "wide"
            if peak_pct >= TRAIL_TIGHTEN_PCT and holding.ticks_since_new_peak >= TRAIL_STALE_TICKS:
                layer = "stale"
            elif peak_pct >= TRAIL_TIGHTEN_PCT and holding.ticks_above_tighten >= TRAIL_DELAY_TICKS:
                layer = "tight"
            logger.debug("Trail stop updated for %s: $%.4f -> $%.4f (%s layer, peak $%.4f +%.1f%%, "
                         "above_thr=%d stale=%d)",
                         holding.pair, old_stop, new_stop, layer, holding.peak_price, peak_pct,
                         holding.ticks_above_tighten, holding.ticks_since_new_peak)

    def check_stop_ticker(self, pair: str, price: float) -> Trade | None:
        """Check stops using live ticker prices (~every 60s).

        Updates the delayed+stale trailing stop on every tick so that
        stale peak detection and delay counters advance in real time,
        not just on hourly candle boundaries.
        """
        if pair not in self.holdings:
            return None
        h = self.holdings[pair]

        # Update closes for equity calculation
        if self._closes.get(pair):
            self._closes[pair][-1] = price

        # Update trailing stop with current price (advances stale/delay counters)
        self._update_trail_stop(h, price)

        now = datetime.now()

        # 1. Check effective stop (max of ATR floor and trailing stop)
        effective_stop = max(h.atr_stop_price, h.trail_stop_price)
        if effective_stop > 0 and price <= effective_stop:
            if h.trail_stop_price > h.atr_stop_price and h.trail_stop_price > 0:
                pnl_pct = (price - h.entry_price) / h.entry_price * 100 if h.entry_price > 0 else 0
                reason = f"Trail stop hit: ${price:,.4f} <= ${h.trail_stop_price:,.4f} (locked +{pnl_pct:.1f}%)"
            else:
                stop_dist = (h.entry_price - h.atr_stop_price) / h.entry_price * 100 if h.entry_price > 0 else 0
                reason = f"ATR stop hit: ${price:,.4f} <= ${h.atr_stop_price:,.4f} ({stop_dist:.1f}% from entry)"
            t = self._sell(pair, now, reason)
            if t:
                self._was_cash = True
                self._exit_cooldown = EXIT_COOLDOWN
                self._hours_in_position = 0
                self.status = "cash"
                self.status_detail = reason
                logger.info("Stop triggered for %s at $%.4f (effective stop $%.4f)", pair, price, effective_stop)
                return t

        # 2. Check equity trailing stop (emergency backstop)
        equity = self.get_equity()
        if equity > self._peak_equity:
            self._peak_equity = equity

        if self._peak_equity > self.starting_balance and equity < self._peak_equity * (1 - EQUITY_TRAIL_PCT):
            reason = f"Equity stop ({EQUITY_TRAIL_PCT*100:.0f}% from peak ${self._peak_equity:,.0f})"
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
        """Buy a coin with given USD amount. Sets ATR-calibrated stop at entry."""
        if amount_usd > self.cash or amount_usd < 1:
            return None

        price = self._closes[pair][-1]
        fee = amount_usd * self.fee_rate
        crypto_amount = (amount_usd - fee) / price
        self.cash -= amount_usd

        # Calculate ATR-calibrated stop: adapts to each coin's volatility
        atr = _atr(self._highs.get(pair, []), self._lows.get(pair, []),
                    self._closes.get(pair, []), ATR_STOP_LOOKBACK)
        if atr and price > 0:
            atr_pct = atr / price
            stop_price = price * (1 - atr_pct * ATR_STOP_MULT)
            stop_dist_pct = atr_pct * ATR_STOP_MULT * 100
            logger.info("ATR stop for %s: entry $%.4f, stop $%.4f (%.1f%% away, ATR=%.1f%%)",
                        pair, price, stop_price, stop_dist_pct, atr_pct * 100)
        else:
            # Fallback: 8% hard stop if ATR not available
            stop_price = price * 0.92
            logger.warning("ATR not available for %s, using 8%% fallback stop at $%.4f", pair, stop_price)

        self.holdings[pair] = MomentumHolding(
            pair=pair, shares=crypto_amount, entry_price=price, entry_time=timestamp,
            peak_price=price, atr_stop_price=stop_price, trail_stop_price=0.0,
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
        """Sell all holdings of a coin. Tracks pair for lockout."""
        holding = self.holdings.get(pair)
        if not holding:
            return None

        price = self._closes[pair][-1]
        gross_usd = holding.shares * price
        fee = gross_usd * self.fee_rate
        net_usd = gross_usd - fee

        # Track for same-coin lockout
        self._last_sold_pair = pair
        self._last_sold_time = timestamp

        # If this was a loss, apply extended lockout so we don't re-buy the same loser
        buy_cost = holding.shares * holding.entry_price
        if net_usd < buy_cost:
            self._loss_lockouts[pair] = timestamp + timedelta(hours=LOSS_LOCKOUT_HOURS)
            logger.info("Loss lockout: %s blocked for %dh (bought %.2f, sold %.2f)",
                        pair, LOSS_LOCKOUT_HOURS, buy_cost, net_usd)

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

            # Effective stop: max of ATR floor and trailing stop
            effective_stop = max(h.atr_stop_price, h.trail_stop_price)
            stop_price = effective_stop
            stop_distance_pct = ((current_price - effective_stop) / current_price * 100) if current_price > 0 and effective_stop > 0 else 0

            # Time remaining before max hold exit
            hold_hours = self._hours_in_position
            max_hold_remaining = max(0, MAX_HOLD_HOURS - hold_hours)

            # Determine active trail layer for dashboard
            peak_pnl = (h.peak_price - h.entry_price) / h.entry_price * 100 if h.entry_price > 0 else 0
            if peak_pnl >= TRAIL_TIGHTEN_PCT and h.ticks_since_new_peak >= TRAIL_STALE_TICKS:
                trail_layer = "stale"
            elif peak_pnl >= TRAIL_TIGHTEN_PCT and h.ticks_above_tighten >= TRAIL_DELAY_TICKS:
                trail_layer = "tight"
            elif peak_pnl >= TRAIL_ACTIVATE_PCT:
                trail_layer = "wide"
            else:
                trail_layer = "inactive"

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
                "stop_price": stop_price,
                "atr_stop_price": h.atr_stop_price,
                "trail_stop_price": h.trail_stop_price,
                "stop_distance_pct": stop_distance_pct,
                "max_hold_remaining_hours": max_hold_remaining,
                "trail_layer": trail_layer,
                "ticks_above_tighten": h.ticks_above_tighten,
                "ticks_since_new_peak": h.ticks_since_new_peak,
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
            "max_hold_hours": MAX_HOLD_HOURS,
            "accel_exit_thresh": ACCEL_EXIT_THRESH,
            "entry_rejections": self._entry_rejections[-10:],  # last 10 reasons
            "lockout_pair": self._last_sold_pair,
            "lockout_until": self._last_sold_time.isoformat() if self._last_sold_time else None,
            "loss_lockouts": {p: t.isoformat() for p, t in self._loss_lockouts.items()},
            "min_price_filter": MIN_PRICE,
        }
