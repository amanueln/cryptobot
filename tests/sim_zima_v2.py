"""V2: Fix regime whipsaw with hysteresis + cooldown.

Problem found in v1: regime filter flips daily around SMA, causing
buy-sell-buy-sell cycles that bleed fees. Fix with:
1. Hysteresis band: need BTC > 1.02*SMA to go bullish, < 0.98*SMA for bearish
2. Cooldown after regime exit: don't re-enter for N hours
3. Minimum hold period: once in, stay at least N hours
"""

import sqlite3
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from sim_find_winner import FlexEngine, calc_rsi
from engine.momentum_engine import _sma, _atr, AccelScore, REGIME_MA
from exchange.models import Candle

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "candles.db")


class HysteresisEngine(FlexEngine):
    """Engine with regime hysteresis to prevent whipsaw."""

    def __init__(self, allocation, pairs, config):
        super().__init__(allocation, pairs, config)
        self._regime_cooldown = 0  # hours remaining before re-entry allowed
        self._hours_in_position = 0  # minimum hold counter
        self._regime_state = "unknown"  # "bullish", "bearish", "unknown"

    def feed_candle(self, pair, candle, warmup=False):
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

        # No position-level stops (stop_type = "none")
        if pair in self.holdings:
            h = self.holdings[pair]
            if candle.close > h.peak_price:
                h.peak_price = candle.close
            h.atr_stop_price = 0

        # BTC regime with hysteresis
        if pair == 'BTC-USD':
            self._btc_closes = self._closes['BTC-USD']
            self.btc_price = candle.close
            regime_period = self.cfg.get("regime_ma", REGIME_MA)
            btc_ma = _sma(self._btc_closes, regime_period)
            if btc_ma is not None:
                self.btc_ma = btc_ma
                hyst = self.cfg.get("regime_hysteresis", 0.02)

                if self._regime_state == "bearish" or self._regime_state == "unknown":
                    # Need BTC > (1+hyst)*SMA to flip bullish
                    if self.btc_price >= btc_ma * (1 + hyst):
                        self._regime_state = "bullish"
                        self.regime_bullish = True
                elif self._regime_state == "bullish":
                    # Need BTC < (1-hyst)*SMA to flip bearish
                    if self.btc_price <= btc_ma * (1 - hyst):
                        self._regime_state = "bearish"
                        self.regime_bullish = False

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
        trades = []

        # Equity trailing stop
        if self.cfg.get("equity_trail") and self.holdings:
            eq = self.cash
            for hld in self.holdings.values():
                pc = self._closes.get(hld.pair, [])
                if pc:
                    eq += hld.shares * pc[-1]
            if not hasattr(self, '_peak_equity'):
                self._peak_equity = eq
            if eq > self._peak_equity:
                self._peak_equity = eq
            eq_stop_pct = self.cfg.get("equity_trail_pct", 0.15)
            if self._peak_equity > self.cash * 0.5 and eq < self._peak_equity * (1 - eq_stop_pct):
                exit_trades = self._exit_all(candle.timestamp, f"Equity trailing stop ({eq_stop_pct*100:.0f}%)")
                trades.extend(exit_trades)
                self._was_cash = True
                cooldown = self.cfg.get("exit_cooldown", 168)
                self._regime_cooldown = cooldown
                self._peak_equity = eq
                self._hours_in_position = 0
                return trades

        if pair != 'BTC-USD':
            return []

        self._last_candle_ts = candle.timestamp
        self._hours_since_rebal += 1
        self._hours_since_regime_check += 1

        # Decrement cooldown
        if self._regime_cooldown > 0:
            self._regime_cooldown -= 1

        # Track time in position
        if self.holdings:
            self._hours_in_position += 1

        # Daily regime check
        min_hold = self.cfg.get("min_hold_hours", 48)
        if self._hours_since_regime_check >= 24:
            self._hours_since_regime_check = 0
            if not self.regime_bullish and self.holdings:
                if self._hours_in_position >= min_hold:
                    trades.extend(self._exit_all(candle.timestamp, "Regime exit"))
                    self._was_cash = True
                    cooldown = self.cfg.get("exit_cooldown", 72)
                    self._regime_cooldown = cooldown
                    self._hours_in_position = 0
                    return trades

        # Immediate entry from cash (if cooldown expired)
        if self._was_cash and not self.holdings and self._regime_cooldown <= 0:
            if self.regime_bullish:
                scores = self._compute_flex_scores()
                qualifying = [s for s in scores if s.accel > self.cfg["reentry_threshold"]]
                if qualifying:
                    entry_trades = self._try_entry(qualifying, candle.timestamp)
                    if entry_trades:
                        trades.extend(entry_trades)
                        self._was_cash = False
                        self._hours_since_rebal = 0
                        self._hours_in_position = 0
                        if hasattr(self, '_peak_equity'):
                            eq = self.cash
                            for hld in self.holdings.values():
                                pc = self._closes.get(hld.pair, [])
                                if pc:
                                    eq += hld.shares * pc[-1]
                            self._peak_equity = eq
                        return trades

        # Rebalance
        rebal_hours = self.cfg["rebal_hours"]
        if self._hours_since_rebal >= rebal_hours:
            self._hours_since_rebal = 0
            if not self.regime_bullish:
                if self.holdings and self._hours_in_position >= min_hold:
                    trades.extend(self._exit_all(candle.timestamp, "Regime bearish at rebal"))
                    self._was_cash = True
                    cooldown = self.cfg.get("exit_cooldown", 72)
                    self._regime_cooldown = cooldown
                    self._hours_in_position = 0
            elif self._regime_cooldown <= 0:
                scores = self._compute_flex_scores()
                if self._was_cash:
                    scores = [s for s in scores if s.accel > self.cfg["reentry_threshold"]]
                if not scores:
                    if self.holdings and self._hours_in_position >= min_hold:
                        trades.extend(self._exit_all(candle.timestamp, "No qualifying scores"))
                    if not self.holdings:
                        self._was_cash = True
                else:
                    self._was_cash = False
                    top_n = self.cfg["top_n"]
                    winners = set(s.pair for s in scores[:top_n])
                    # Only rotate if held long enough
                    if self._hours_in_position >= min_hold:
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
                                    self._hours_in_position = 0

        return trades

    def _passes_filters(self, pair, closes):
        """RSI + trend filters."""
        # RSI filter
        if self.cfg.get("rsi_filter"):
            max_rsi = self.cfg.get("max_rsi", 65)
            rsi = calc_rsi(closes)
            if rsi > max_rsi:
                return False

        # Trend filter
        if self.cfg.get("trend_filter"):
            if len(closes) >= 60:
                sma_now = _sma(closes, 50)
                sma_prev = _sma(closes[:-10], 50)
                if sma_now and sma_prev and sma_now < sma_prev:
                    return False

        return True


def run_test(rows, pairs, cfg, starting_balance=3000.0, warmup=750):
    engine = HysteresisEngine(starting_balance, pairs, cfg)
    by_ts = {}
    for r in rows:
        ts = r[1]
        if ts not in by_ts:
            by_ts[ts] = []
        by_ts[ts].append(r)

    sorted_ts = sorted(by_ts.keys())
    unique_hours = sorted(set(sorted_ts))
    warmup_set = set(unique_hours[:warmup])

    all_trades = []
    equity_curve = []
    peak_eq = starting_balance
    max_dd = 0

    for ts in sorted_ts:
        is_warmup = ts in warmup_set
        for r in by_ts[ts]:
            pair, timestamp, o, h, l, c, v = r
            candle = Candle(pair=pair, timestamp=datetime.fromisoformat(timestamp),
                            open=o, high=h, low=l, close=c, volume=v,
                            granularity="ONE_HOUR")
            trades = engine.feed_candle(pair, candle, warmup=is_warmup)
            all_trades.extend(trades)

        if not is_warmup:
            eq = engine.cash
            for hld in engine.holdings.values():
                pc = engine._closes.get(hld.pair, [])
                if pc:
                    eq += hld.shares * pc[-1]
            equity_curve.append((ts, eq))
            if eq > peak_eq:
                peak_eq = eq
            dd = (peak_eq - eq) / peak_eq * 100 if peak_eq > 0 else 0
            if dd > max_dd:
                max_dd = dd

    end_eq = equity_curve[-1][1] if equity_curve else starting_balance
    pnl = end_eq - starting_balance

    # Count trade round-trips
    buys = sum(1 for t in all_trades if t.side == "buy")
    sells = sum(1 for t in all_trades if t.side == "sell")

    return {
        "pnl": pnl, "pnl_pct": pnl / starting_balance * 100,
        "max_dd": max_dd, "trades": len(all_trades),
        "buys": buys, "sells": sells,
        "end_eq": end_eq, "peak_eq": peak_eq,
        "equity_curve": equity_curve,
        "all_trades": all_trades,
    }


def main():
    conn = sqlite3.connect(DB)
    pair_data = conn.execute("""
        SELECT pair, COUNT(*) as cnt FROM candles
        GROUP BY pair HAVING cnt > 720
        ORDER BY cnt DESC
    """).fetchall()
    all_pairs = [p[0] for p in pair_data]
    print(f"Found {len(all_pairs)} pairs with 720+ candles")

    placeholders = ",".join("?" for _ in all_pairs)
    rows = conn.execute(
        f"""SELECT pair, timestamp, open, high, low, close, volume
            FROM candles WHERE pair IN ({placeholders})
            ORDER BY timestamp ASC""",
        all_pairs
    ).fetchall()
    conn.close()

    timestamps = sorted(set(r[1] for r in rows))
    print(f"Loaded {len(rows)} candles, {timestamps[0][:10]} to {timestamps[-1][:10]}")

    # BTC benchmark
    btc_rows = [r for r in rows if r[0] == 'BTC-USD']
    warmup_ts = set(timestamps[:750])
    trading_btc = [r for r in btc_rows if r[1] not in warmup_ts]
    if trading_btc:
        btc_start = trading_btc[0][5]
        btc_end = trading_btc[-1][5]
        btc_ret = (btc_end / btc_start - 1) * 100
        print(f"BTC buy-and-hold: ${btc_start:,.0f} -> ${btc_end:,.0f} ({btc_ret:+.1f}%) = ${3000*(1+btc_ret/100):,.0f}")
    print()

    # Base winning config
    base = {
        "entry_type": "acceleration", "short_lb": 336, "long_lb": 720,
        "rebal_hours": 168, "top_n": 1,
        "reentry_threshold": 0.20, "regime_ma": 500,
        "stop_type": "none", "atr_mult": 0, "hard_stop_pct": 1.0,
        "rsi_filter": True, "max_rsi": 65, "overbought_filter": False,
        "equity_trail": True, "equity_trail_pct": 0.15,
    }

    configs = {}

    # --- Hysteresis sweep ---
    for hyst in [0.01, 0.02, 0.03, 0.05]:
        for cooldown in [48, 72, 168]:
            for min_hold in [24, 48, 72, 168]:
                cd_label = {48: "2d", 72: "3d", 168: "1w"}[cooldown]
                mh_label = {24: "1d", 48: "2d", 72: "3d", 168: "1w"}[min_hold]
                configs[f"H{hyst:.0%} CD{cd_label} MH{mh_label}"] = {
                    **base,
                    "regime_hysteresis": hyst,
                    "exit_cooldown": cooldown,
                    "min_hold_hours": min_hold,
                }

    # --- Reentry threshold sweep with best hysteresis ---
    for thresh in [0.15, 0.20, 0.25, 0.30]:
        for hyst in [0.02, 0.03, 0.05]:
            configs[f"Re{thresh:.0%} H{hyst:.0%} CD3d MH2d"] = {
                **base,
                "reentry_threshold": thresh,
                "regime_hysteresis": hyst,
                "exit_cooldown": 72,
                "min_hold_hours": 48,
            }

    # --- Top N variants ---
    for n in [1, 2]:
        configs[f"Top{n} H3% CD3d MH2d"] = {
            **base, "top_n": n,
            "regime_hysteresis": 0.03,
            "exit_cooldown": 72,
            "min_hold_hours": 48,
        }

    # --- Biweekly rebalance ---
    configs["Biweekly H3% CD3d MH2d"] = {
        **base, "rebal_hours": 336,
        "regime_hysteresis": 0.03,
        "exit_cooldown": 72,
        "min_hold_hours": 48,
    }

    # --- Monthly rebalance ---
    configs["Monthly H3% CD1w MH3d"] = {
        **base, "rebal_hours": 720,
        "regime_hysteresis": 0.03,
        "exit_cooldown": 168,
        "min_hold_hours": 72,
    }

    # --- No regime filter at all ---
    configs["No regime, 25% re, MH3d"] = {
        **base, "reentry_threshold": 0.25,
        "regime_hysteresis": 999,  # effectively disables regime exit
        "exit_cooldown": 0,
        "min_hold_hours": 72,
    }

    # Run all
    results = {}
    total = len(configs)
    for idx, (name, cfg) in enumerate(configs.items(), 1):
        print(f"[{idx}/{total}] {name}...", end=" ", flush=True)
        try:
            r = run_test(rows, all_pairs, cfg, warmup=750)
            results[name] = r
            print(f"${r['pnl']:+,.0f} ({r['pnl_pct']:+.1f}%) Peak:${r['peak_eq']:,.0f} DD:{r['max_dd']:.0f}% Trades:{r['trades']}")
        except Exception as e:
            import traceback
            print(f"ERROR: {e}")
            traceback.print_exc()

    # Ranked
    print(f"\n{'=' * 110}")
    print(f"  HYSTERESIS OPTIMIZATION — RANKED BY P&L")
    print(f"{'=' * 110}")
    print(f"  {'#':>3}  {'Strategy':<45} {'P&L':>10} {'P&L%':>7} {'Peak':>8} {'MaxDD':>7} {'Trades':>7}")
    print(f"  {'---':>3}  {'-' * 45} {'-' * 10} {'-' * 7} {'-' * 8} {'-' * 7} {'-' * 7}")

    sorted_r = sorted(results.items(), key=lambda x: x[1]["pnl"], reverse=True)
    for rank, (name, r) in enumerate(sorted_r, 1):
        marker = " ***" if rank <= 10 else ""
        print(f"  {rank:>3}. {name:<45} ${r['pnl']:>+8,.0f} {r['pnl_pct']:>+6.1f}% ${r['peak_eq']:>6,.0f} {r['max_dd']:>6.1f}% {r['trades']:>6}{marker}")

    # Top 5 detail
    print(f"\n{'=' * 110}")
    print(f"  TOP 5 DETAILED")
    print(f"{'=' * 110}")
    for rank, (name, r) in enumerate(sorted_r[:5], 1):
        print(f"\n  #{rank}: {name}")
        print(f"  P&L: ${r['pnl']:+,.2f} ({r['pnl_pct']:+.1f}%)")
        print(f"  Peak: ${r['peak_eq']:,.2f} | Final: ${r['end_eq']:,.2f} | Max DD: {r['max_dd']:.1f}%")
        print(f"  Trades: {r['trades']} ({r['buys']} buys, {r['sells']} sells)")

        curve = r["equity_curve"]
        if curve:
            print(f"\n  Equity snapshots:")
            step = max(len(curve) // 12, 1)
            for i in range(0, len(curve), step):
                ts, eq = curve[i]
                print(f"    {ts[:16]}  ${eq:>10,.2f}")
            ts, eq = curve[-1]
            print(f"    {ts[:16]}  ${eq:>10,.2f}  (final)")

        # Show last 15 trades
        trades_list = r["all_trades"]
        if trades_list:
            show = min(15, len(trades_list))
            print(f"\n  Last {show} trades:")
            for t in trades_list[-show:]:
                side_icon = "BUY " if t.side == "buy" else "SELL"
                print(f"    {t.timestamp.strftime('%Y-%m-%d %H:%M')}  {side_icon}  {t.pair:12s}  "
                      f"${t.price:>10,.4f}  ${t.cost_usd:>8,.2f}  | {t.reason}")


if __name__ == "__main__":
    main()
