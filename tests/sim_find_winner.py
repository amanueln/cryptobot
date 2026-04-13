"""Find a winning momentum strategy by testing many variants.

Tests across multiple dimensions:
  - Stop type: tight trailing, wide trailing, no trailing (hold to rebalance), hard-only
  - Entry: acceleration, breakout from consolidation, buy-dip-in-uptrend
  - Lookback: short (3d/7d), medium (7d/14d), long (14d/30d)
  - Rebalance: daily, weekly, biweekly
  - Filters: RSI, overbought, volatility
"""

import sqlite3
import sys
import os
from datetime import datetime, timedelta
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine.momentum_engine import (
    MomentumEngine, AccelScore, _sma, _atr,
    FEE_RATE, REGIME_MA
)
from exchange.models import Candle

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "candles.db")

PAIRS = [
    'ETH-USD', 'BTC-USD', 'ADA-USD', 'LINK-USD', 'UNI-USD',
    'ALGO-USD', 'DOGE-USD', 'DOT-USD', 'SOL-USD', 'AVAX-USD',
    'NEAR-USD', 'SUI-USD', 'PEPE-USD', 'BONK-USD', 'SHIB-USD',
    'HBAR-USD', 'XRP-USD', 'LTC-USD', 'BCH-USD', 'RENDER-USD',
]


def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50.0  # neutral default
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


class FlexEngine(MomentumEngine):
    """Flexible momentum engine with configurable parameters."""

    def __init__(self, allocation, pairs, config):
        super().__init__(allocation, pairs=pairs)
        self.cfg = config
        self._watchlist: dict[str, float] = {}  # for pullback entry
        self._consolidation_range: dict[str, tuple] = {}  # pair -> (low, high)

    def feed_candle(self, pair, candle, warmup=False):
        """Override to use configurable parameters."""
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

        # Trim history
        max_hist = max(self.cfg["long_lb"], REGIME_MA) + 200
        if len(self._closes[pair]) > max_hist:
            self._closes[pair] = self._closes[pair][-max_hist:]
            self._highs[pair] = self._highs[pair][-max_hist:]
            self._lows[pair] = self._lows[pair][-max_hist:]
            self._timestamps[pair] = self._timestamps[pair][-max_hist:]

        # Update peak/stop for holdings
        if pair in self.holdings:
            h = self.holdings[pair]
            if candle.close > h.peak_price:
                h.peak_price = candle.close
            # Update trailing stop
            if self.cfg["stop_type"] == "trailing":
                atr = _atr(self._highs[pair], self._lows[pair], self._closes[pair], 24)
                if atr and h.peak_price > 0:
                    h.atr_stop_price = max(
                        h.peak_price - self.cfg["atr_mult"] * atr,
                        h.entry_price * (1 - self.cfg["hard_stop_pct"]),
                    )
            elif self.cfg["stop_type"] == "hard_only":
                h.atr_stop_price = h.entry_price * (1 - self.cfg["hard_stop_pct"])
            else:  # "none"
                h.atr_stop_price = 0

        # BTC regime
        if pair == 'BTC-USD':
            self._btc_closes = self._closes['BTC-USD']
            self.btc_price = candle.close
            regime_period = self.cfg.get("regime_ma", REGIME_MA)
            btc_ma = _sma(self._btc_closes, regime_period)
            if btc_ma is not None:
                self.btc_ma = btc_ma
                self.regime_bullish = self.btc_price >= btc_ma

        if warmup:
            return []

        # Check warmup requirements
        regime_period = self.cfg.get("regime_ma", REGIME_MA)
        if len(self._btc_closes) < regime_period:
            return []

        ready_pairs = [p for p in self.pairs if len(self._closes[p]) >= self.cfg["long_lb"] + 1]
        if len(ready_pairs) < 3:
            return []

        self._warmup_done = True

        # Stop-loss check
        trades = []
        if pair in self.holdings and self.cfg["stop_type"] != "none":
            h = self.holdings[pair]
            if h.atr_stop_price > 0 and candle.close <= h.atr_stop_price:
                pnl_pct = (candle.close / h.entry_price - 1) * 100
                t = self._sell(pair, candle.timestamp, f"Stop hit ({pnl_pct:+.1f}%)")
                if t:
                    trades.append(t)
                if not self.holdings:
                    self._was_cash = True
                return trades

        if pair != 'BTC-USD':
            return []

        self._last_candle_ts = candle.timestamp
        self._hours_since_rebal += 1
        self._hours_since_regime_check += 1

        # Daily regime check
        if self._hours_since_regime_check >= 24:
            self._hours_since_regime_check = 0
            if not self.regime_bullish and self.holdings:
                trades.extend(self._exit_all(candle.timestamp, "Regime exit"))
                self._was_cash = True
                return trades

        # Immediate entry from cash
        if self._was_cash and not self.holdings:
            scores = self._compute_flex_scores()
            qualifying = [s for s in scores if s.accel > self.cfg["reentry_threshold"]]
            if qualifying:
                entry_trades = self._try_entry(qualifying, candle.timestamp)
                if entry_trades:
                    trades.extend(entry_trades)
                    self._was_cash = False
                    self._hours_since_rebal = 0
                    return trades

        # Rebalance
        rebal_hours = self.cfg["rebal_hours"]
        if self._hours_since_rebal >= rebal_hours:
            self._hours_since_rebal = 0
            if not self.regime_bullish:
                if self.holdings:
                    trades.extend(self._exit_all(candle.timestamp, "Regime bearish at rebal"))
                    self._was_cash = True
            else:
                scores = self._compute_flex_scores()
                if self._was_cash:
                    scores = [s for s in scores if s.accel > self.cfg["reentry_threshold"]]
                if not scores:
                    if self.holdings:
                        trades.extend(self._exit_all(candle.timestamp, "No qualifying scores"))
                    self._was_cash = True
                else:
                    self._was_cash = False
                    top_n = self.cfg["top_n"]
                    winners = set(s.pair for s in scores[:top_n])
                    for pk in list(self.holdings.keys()):
                        if pk not in winners:
                            t = self._sell(pk, candle.timestamp, "Rotated out")
                            if t:
                                trades.append(t)
                    investable = self.cash * 0.95
                    n_buy = len(winners) - len(self.holdings)
                    if n_buy > 0 and investable > 10:
                        per = investable / n_buy
                        for s in scores[:top_n]:
                            if s.pair not in self.holdings and per > 1:
                                t = self._buy(s.pair, per, candle.timestamp,
                                              f"Top accel: {s.accel:+.1%}")
                                if t:
                                    trades.append(t)

        return trades

    def _compute_flex_scores(self):
        """Compute scores based on configured entry type."""
        entry_type = self.cfg["entry_type"]

        if entry_type == "acceleration":
            return self._scores_acceleration()
        elif entry_type == "breakout":
            return self._scores_breakout()
        elif entry_type == "buy_dip":
            return self._scores_buy_dip()
        elif entry_type == "ma_crossover":
            return self._scores_ma_crossover()
        return []

    def _scores_acceleration(self):
        """Original: momentum acceleration."""
        short_lb = self.cfg["short_lb"]
        long_lb = self.cfg["long_lb"]
        scores = []
        for pair in self.pairs:
            closes = self._closes[pair]
            if len(closes) < long_lb + 1:
                continue
            short_mom = closes[-1] / closes[-short_lb] - 1
            long_mom = closes[-1] / closes[-long_lb] - 1
            accel = short_mom - (long_mom * short_lb / long_lb)
            if long_mom <= 0 or accel <= 0:
                continue
            if not self._passes_filters(pair, closes):
                continue
            scores.append(AccelScore(pair=pair, accel=accel, short_mom=short_mom, long_mom=long_mom))
        scores.sort(key=lambda s: s.accel, reverse=True)
        return scores

    def _scores_breakout(self):
        """Breakout: price breaks above 20-day high after consolidation."""
        scores = []
        lookback = self.cfg.get("breakout_lookback", 480)  # 20 days in hours
        consol_period = self.cfg.get("consol_period", 168)  # 7 days
        for pair in self.pairs:
            closes = self._closes[pair]
            highs = self._highs[pair]
            if len(closes) < lookback + 1:
                continue
            # 20-day high
            period_high = max(highs[-lookback:])
            current = closes[-1]
            # Is price breaking above the range?
            if current < period_high * 0.98:
                continue
            # Was it consolidating? (range < 10% over last 7 days)
            recent_high = max(highs[-consol_period:])
            recent_low = min(self._lows[pair][-consol_period:])
            if recent_low <= 0:
                continue
            range_pct = (recent_high - recent_low) / recent_low
            if range_pct > 0.15:  # not consolidating, too volatile
                continue
            if not self._passes_filters(pair, closes):
                continue
            # Score by how clean the breakout is (close to high with tight range)
            accel = (current / recent_low - 1) - range_pct  # net breakout strength
            if accel <= 0:
                continue
            short_mom = current / closes[-self.cfg["short_lb"]] - 1
            long_mom = current / closes[-self.cfg["long_lb"]] - 1
            scores.append(AccelScore(pair=pair, accel=accel, short_mom=short_mom, long_mom=long_mom))
        scores.sort(key=lambda s: s.accel, reverse=True)
        return scores

    def _scores_buy_dip(self):
        """Buy-the-dip: find coins in uptrend that pulled back."""
        scores = []
        for pair in self.pairs:
            closes = self._closes[pair]
            if len(closes) < self.cfg["long_lb"] + 1:
                continue
            # Must be in uptrend: 50-period SMA rising, price above 200-period SMA
            sma50 = _sma(closes, min(50, len(closes)))
            sma200 = _sma(closes, min(200, len(closes)))
            if sma50 is None or sma200 is None:
                continue
            if closes[-1] < sma200:  # below long-term trend
                continue
            if sma50 < sma200:  # no uptrend
                continue
            # Must have pulled back: price below 50-SMA (dip)
            if closes[-1] > sma50:
                continue
            # How far is the dip? (bigger dip = better entry)
            dip_pct = (sma50 - closes[-1]) / sma50
            if dip_pct < 0.02:  # needs at least 2% dip
                continue
            if dip_pct > 0.15:  # too deep, trend might be broken
                continue
            # RSI should be oversold-ish
            rsi = calc_rsi(closes, 14)
            if rsi > 45:  # not really a dip
                continue
            if not self._passes_filters(pair, closes):
                continue
            accel = dip_pct  # deeper dip = higher score
            short_mom = closes[-1] / closes[-self.cfg["short_lb"]] - 1
            long_mom = closes[-1] / closes[-self.cfg["long_lb"]] - 1
            scores.append(AccelScore(pair=pair, accel=accel, short_mom=short_mom, long_mom=long_mom))
        scores.sort(key=lambda s: s.accel, reverse=True)
        return scores

    def _scores_ma_crossover(self):
        """MA crossover: buy when fast EMA crosses above slow EMA."""
        fast_p = self.cfg.get("ema_fast", 48)   # 2-day
        slow_p = self.cfg.get("ema_slow", 168)  # 7-day
        scores = []
        for pair in self.pairs:
            closes = self._closes[pair]
            if len(closes) < slow_p + 10:
                continue
            # Compute EMAs
            fast_ema = self._ema(closes, fast_p)
            slow_ema = self._ema(closes, slow_p)
            fast_prev = self._ema(closes[:-1], fast_p)
            slow_prev = self._ema(closes[:-1], slow_p)
            if fast_ema is None or slow_ema is None or fast_prev is None or slow_prev is None:
                continue
            # Cross: fast was below slow, now above
            if fast_prev >= slow_prev:
                continue  # already crossed, not fresh
            if fast_ema <= slow_ema:
                continue  # hasn't crossed yet
            # Score by momentum strength
            accel = (fast_ema / slow_ema - 1)
            if accel <= 0:
                continue
            if not self._passes_filters(pair, closes):
                continue
            short_mom = closes[-1] / closes[-self.cfg["short_lb"]] - 1
            long_mom = closes[-1] / closes[-self.cfg["long_lb"]] - 1
            scores.append(AccelScore(pair=pair, accel=accel, short_mom=short_mom, long_mom=long_mom))
        scores.sort(key=lambda s: s.accel, reverse=True)
        return scores

    @staticmethod
    def _ema(values, period):
        if len(values) < period:
            return None
        mult = 2 / (period + 1)
        ema = sum(values[:period]) / period
        for v in values[period:]:
            ema = (v - ema) * mult + ema
        return ema

    def _passes_filters(self, pair, closes):
        """Apply configured filters."""
        if self.cfg.get("rsi_filter", False):
            rsi = calc_rsi(closes, 14)
            max_rsi = self.cfg.get("max_rsi", 70)
            if rsi > max_rsi:
                return False
        if self.cfg.get("overbought_filter", False):
            sma20 = _sma(closes, 20)
            max_above = self.cfg.get("max_above_sma_pct", 0.15)
            if sma20 and sma20 > 0 and closes[-1] > sma20 * (1 + max_above):
                return False
        return True

    def _try_entry(self, qualifying, timestamp):
        """Execute entry for qualifying coins."""
        trades = []
        top_n = self.cfg["top_n"]
        winners = qualifying[:top_n]

        if self.cfg.get("pullback_entry", False):
            # Wait for pullback before entering
            for s in winners:
                closes = self._closes.get(s.pair, [])
                if not closes:
                    continue
                recent_high = max(closes[-48:]) if len(closes) >= 48 else closes[-1]
                pullback_pct = self.cfg.get("pullback_pct", 0.05)
                if closes[-1] > recent_high * (1 - pullback_pct):
                    # Not pulled back enough — add to watchlist
                    self._watchlist[s.pair] = recent_high
                    continue
                # Pulled back — enter
                investable = self.cash * 0.95
                per = investable / min(len(winners), top_n)
                if per > 1 and s.pair not in self.holdings:
                    t = self._buy(s.pair, per, timestamp,
                                  f"Pullback entry: {s.accel:+.1%}")
                    if t:
                        trades.append(t)
        else:
            # Immediate entry
            investable = self.cash * 0.95
            per = investable / len(winners)
            for s in winners:
                if per > 1 and s.pair not in self.holdings:
                    t = self._buy(s.pair, per, timestamp,
                                  f"Entry: {s.accel:+.1%}")
                    if t:
                        trades.append(t)
        return trades


# ---------- Backtest harness ----------

def load_candles(db_path, pairs, start, end):
    conn = sqlite3.connect(db_path)
    placeholders = ",".join("?" for _ in pairs)
    rows = conn.execute(
        f"""SELECT pair, timestamp, open, high, low, close, volume
            FROM candles WHERE pair IN ({placeholders})
            AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC""",
        list(pairs) + [start.isoformat(), end.isoformat()]
    ).fetchall()
    conn.close()
    return rows


def run_backtest(config, candle_rows, warmup_hours=750):
    engine = FlexEngine(3000.0, PAIRS, config)

    by_ts = {}
    for r in candle_rows:
        ts = r[1]
        if ts not in by_ts:
            by_ts[ts] = []
        by_ts[ts].append(r)

    sorted_ts = sorted(by_ts.keys())
    unique_hours = sorted(set(sorted_ts))
    warmup_set = set(unique_hours[:warmup_hours])

    all_trades = []
    equity_curve = []
    max_equity = 0
    max_drawdown = 0

    for ts in sorted_ts:
        is_warmup = ts in warmup_set
        for r in by_ts[ts]:
            pair, timestamp, o, h, l, c, v = r
            candle = Candle(
                pair=pair, timestamp=datetime.fromisoformat(timestamp),
                open=o, high=h, low=l, close=c, volume=v,
                granularity="ONE_HOUR",
            )
            trades = engine.feed_candle(pair, candle, warmup=is_warmup)
            all_trades.extend(trades)

        if not is_warmup:
            eq = engine.cash
            for hld in engine.holdings.values():
                pc = engine._closes.get(hld.pair, [])
                if pc:
                    eq += hld.shares * pc[-1]
            equity_curve.append((ts, eq))
            if eq > max_equity:
                max_equity = eq
            dd = (max_equity - eq) / max_equity * 100 if max_equity > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

    # Compute P&L with FIFO
    fifo = {}
    trade_pnls = []
    for t in all_trades:
        if t.side == "buy":
            fifo.setdefault(t.pair, []).append((t.amount, t.cost_usd / t.amount if t.amount > 0 else 0))
        elif t.side == "sell":
            cost_basis = 0.0
            remaining = t.amount
            lots = fifo.get(t.pair, [])
            while remaining > 1e-12 and lots:
                lq, lc = lots[0]
                take = min(remaining, lq)
                cost_basis += take * lc
                remaining -= take
                if take >= lq - 1e-12:
                    lots.pop(0)
                else:
                    lots[0] = (lq - take, lc)
            pnl = t.cost_usd - cost_basis
            trade_pnls.append(pnl)

    start_eq = equity_curve[0][1] if equity_curve else 3000
    end_eq = equity_curve[-1][1] if equity_curve else 3000
    wins = sum(1 for p in trade_pnls if p > 0)
    losses = sum(1 for p in trade_pnls if p <= 0)
    total_sells = len(trade_pnls)

    return {
        "pnl": end_eq - 3000,
        "pnl_pct": (end_eq / 3000 - 1) * 100,
        "max_dd": max_drawdown,
        "trades": len(all_trades),
        "sells": total_sells,
        "wins": wins,
        "losses": losses,
        "win_rate": wins / max(total_sells, 1) * 100,
        "end_eq": end_eq,
        "all_trades": all_trades,
    }


def main():
    end = datetime(2026, 4, 1)
    start = end - timedelta(days=180)

    print(f"Loading candles: {start.date()} to {end.date()}")
    rows = load_candles(DB, PAIRS, start, end)
    print(f"Loaded {len(rows)} candles for {len(PAIRS)} pairs")
    print()

    # ---- Define all configs to test ----
    configs = {}

    # ROUND 1: Stop-loss variants (using current acceleration entry)
    base = {
        "entry_type": "acceleration",
        "short_lb": 336, "long_lb": 720,
        "rebal_hours": 168, "top_n": 2,
        "reentry_threshold": 0.07,
        "regime_ma": 500,
        "rsi_filter": False, "overbought_filter": False,
    }

    configs["1a. Accel + trailing 2x ATR (CURRENT)"] = {**base, "stop_type": "trailing", "atr_mult": 2.0, "hard_stop_pct": 0.15}
    configs["1b. Accel + trailing 5x ATR"] = {**base, "stop_type": "trailing", "atr_mult": 5.0, "hard_stop_pct": 0.20}
    configs["1c. Accel + trailing 10x ATR"] = {**base, "stop_type": "trailing", "atr_mult": 10.0, "hard_stop_pct": 0.25}
    configs["1d. Accel + hard stop only 20%"] = {**base, "stop_type": "hard_only", "atr_mult": 0, "hard_stop_pct": 0.20}
    configs["1e. Accel + hard stop only 30%"] = {**base, "stop_type": "hard_only", "atr_mult": 0, "hard_stop_pct": 0.30}
    configs["1f. Accel + NO stops (hold to rebal)"] = {**base, "stop_type": "none", "atr_mult": 0, "hard_stop_pct": 1.0}

    # ROUND 2: Lookback variants (no stops since tight stops kill everything)
    no_stop = {"stop_type": "hard_only", "atr_mult": 0, "hard_stop_pct": 0.25}

    configs["2a. Short LB 3d/7d + hard 25%"] = {**base, **no_stop, "short_lb": 72, "long_lb": 168, "regime_ma": 200}
    configs["2b. Med LB 7d/14d + hard 25%"] = {**base, **no_stop, "short_lb": 168, "long_lb": 336, "regime_ma": 336}
    configs["2c. Short LB 3d/7d + no stops"] = {**base, "stop_type": "none", "atr_mult": 0, "hard_stop_pct": 1.0, "short_lb": 72, "long_lb": 168, "regime_ma": 200}

    # ROUND 3: Entry type variants
    configs["3a. Breakout + hard 25%"] = {**base, **no_stop, "entry_type": "breakout", "short_lb": 168, "long_lb": 336, "regime_ma": 336, "reentry_threshold": 0.01}
    configs["3b. Buy-dip + hard 25%"] = {**base, **no_stop, "entry_type": "buy_dip", "short_lb": 168, "long_lb": 336, "regime_ma": 336, "reentry_threshold": 0.01}
    configs["3c. MA crossover + hard 25%"] = {**base, **no_stop, "entry_type": "ma_crossover", "short_lb": 168, "long_lb": 336, "regime_ma": 336, "reentry_threshold": 0.001}

    # ROUND 4: Filter variants on best base
    configs["4a. Accel + RSI<65 filter + hard 25%"] = {**base, **no_stop, "rsi_filter": True, "max_rsi": 65}
    configs["4b. Accel + overbought filter + hard 25%"] = {**base, **no_stop, "overbought_filter": True, "max_above_sma_pct": 0.12}
    configs["4c. Accel + both filters + hard 25%"] = {**base, **no_stop, "rsi_filter": True, "max_rsi": 65, "overbought_filter": True, "max_above_sma_pct": 0.12}

    # ROUND 5: Rebalance frequency
    configs["5a. Daily rebal + hard 25%"] = {**base, **no_stop, "rebal_hours": 24}
    configs["5b. Biweekly rebal + hard 25%"] = {**base, **no_stop, "rebal_hours": 336}
    configs["5c. Monthly rebal + no stops"] = {**base, "stop_type": "none", "atr_mult": 0, "hard_stop_pct": 1.0, "rebal_hours": 720}

    # ROUND 6: Top N positions
    configs["6a. Top 1 + hard 25%"] = {**base, **no_stop, "top_n": 1}
    configs["6b. Top 3 + hard 25%"] = {**base, **no_stop, "top_n": 3}
    configs["6c. Top 5 + hard 25%"] = {**base, **no_stop, "top_n": 5}

    # ROUND 7: Reentry threshold
    configs["7a. Reentry 3% + hard 25%"] = {**base, **no_stop, "reentry_threshold": 0.03}
    configs["7b. Reentry 12% + hard 25%"] = {**base, **no_stop, "reentry_threshold": 0.12}

    # ROUND 8: Combined best guesses
    configs["8a. Short LB + RSI + no stops + top 1"] = {
        **base, "stop_type": "none", "atr_mult": 0, "hard_stop_pct": 1.0,
        "short_lb": 72, "long_lb": 168, "regime_ma": 200,
        "rsi_filter": True, "max_rsi": 65, "top_n": 1,
        "rebal_hours": 168, "reentry_threshold": 0.05,
    }
    configs["8b. Short LB + RSI + hard 30% + top 1"] = {
        **base, "stop_type": "hard_only", "atr_mult": 0, "hard_stop_pct": 0.30,
        "short_lb": 72, "long_lb": 168, "regime_ma": 200,
        "rsi_filter": True, "max_rsi": 65, "top_n": 1,
        "rebal_hours": 168, "reentry_threshold": 0.05,
    }
    configs["8c. Buy-dip + no stops + top 1 + daily"] = {
        **base, "stop_type": "none", "atr_mult": 0, "hard_stop_pct": 1.0,
        "entry_type": "buy_dip", "short_lb": 168, "long_lb": 336, "regime_ma": 336,
        "rsi_filter": False, "top_n": 1,
        "rebal_hours": 24, "reentry_threshold": 0.01,
    }
    configs["8d. MA cross + no stops + top 2 + daily"] = {
        **base, "stop_type": "none", "atr_mult": 0, "hard_stop_pct": 1.0,
        "entry_type": "ma_crossover", "short_lb": 168, "long_lb": 336, "regime_ma": 336,
        "top_n": 2, "rebal_hours": 24, "reentry_threshold": 0.001,
    }
    configs["8e. Breakout + hard 25% + top 1 + weekly"] = {
        **base, "stop_type": "hard_only", "atr_mult": 0, "hard_stop_pct": 0.25,
        "entry_type": "breakout", "short_lb": 168, "long_lb": 336, "regime_ma": 336,
        "top_n": 1, "rebal_hours": 168, "reentry_threshold": 0.01,
    }

    # Run all
    results = {}
    total = len(configs)
    for idx, (name, cfg) in enumerate(configs.items(), 1):
        print(f"[{idx}/{total}] {name}...", end=" ", flush=True)
        try:
            r = run_backtest(cfg, rows)
            results[name] = r
            print(f"P&L: ${r['pnl']:+.0f} ({r['pnl_pct']:+.1f}%) | {r['wins']}W/{r['losses']}L | DD:{r['max_dd']:.0f}%")
        except Exception as e:
            print(f"ERROR: {e}")

    # Sort by P&L
    print(f"\n\n{'='*90}")
    print(f"  RESULTS RANKED BY P&L (best to worst)")
    print(f"{'='*90}")
    print(f"  {'#':>3}  {'Strategy':<45} {'P&L':>10} {'P&L%':>7} {'Win%':>6} {'MaxDD':>7} {'Trades':>7}")
    print(f"  {'---':>3}  {'-'*45} {'-'*10} {'-'*7} {'-'*6} {'-'*7} {'-'*7}")

    sorted_results = sorted(results.items(), key=lambda x: x[1]["pnl"], reverse=True)
    for rank, (name, r) in enumerate(sorted_results, 1):
        marker = " <-- WINNER" if rank == 1 else ""
        print(f"  {rank:>3}. {name:<45} ${r['pnl']:>+8.0f} {r['pnl_pct']:>+6.1f}% {r['win_rate']:>5.0f}% {r['max_dd']:>6.1f}% {r['trades']:>6}{marker}")

    # Detail on top 3
    print(f"\n\n{'='*90}")
    print(f"  TOP 3 DETAILED")
    print(f"{'='*90}")
    for rank, (name, r) in enumerate(sorted_results[:3], 1):
        print(f"\n  #{rank}: {name}")
        print(f"  P&L: ${r['pnl']:+.2f} ({r['pnl_pct']:+.1f}%)")
        print(f"  Trades: {r['trades']} total, {r['wins']}W/{r['losses']}L ({r['win_rate']:.0f}%)")
        print(f"  Max drawdown: {r['max_dd']:.1f}%")
        print(f"  Final equity: ${r['end_eq']:,.2f}")

        # Show some trades
        sells = [t for t in r["all_trades"] if t.side == "sell"]
        if sells:
            print(f"  Last 5 sells:")
            for t in sells[-5:]:
                print(f"    {t.timestamp.strftime('%m/%d %H:%M')}  {t.pair:12s}  | {t.reason[:60]}")


if __name__ == "__main__":
    main()
