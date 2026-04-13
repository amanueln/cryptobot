"""Sweep cooldown and min-hold values with 5% hysteresis locked in."""

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
    def __init__(self, allocation, pairs, config):
        super().__init__(allocation, pairs, config)
        self._regime_cooldown = 0
        self._hours_in_position = 0
        self._regime_state = "unknown"

    def feed_candle(self, pair, candle, warmup=False):
        if pair not in self._closes:
            return []
        ts_list = self._timestamps[pair]
        if ts_list and candle.timestamp <= ts_list[-1]:
            return []

        self._closes[pair].append(candle.close)
        self._highs[pair].append(candle.high)
        self._lows[pair].append(candle.low)
        self._timestamps[pair].append(candle.timestamp)
        self._candles_fed += 1

        max_hist = max(self.cfg["long_lb"], REGIME_MA) + 200
        if len(self._closes[pair]) > max_hist:
            self._closes[pair] = self._closes[pair][-max_hist:]
            self._highs[pair] = self._highs[pair][-max_hist:]
            self._lows[pair] = self._lows[pair][-max_hist:]
            self._timestamps[pair] = self._timestamps[pair][-max_hist:]

        if pair in self.holdings:
            h = self.holdings[pair]
            if candle.close > h.peak_price:
                h.peak_price = candle.close
            h.atr_stop_price = 0

        if pair == 'BTC-USD':
            self._btc_closes = self._closes['BTC-USD']
            self.btc_price = candle.close
            regime_period = self.cfg.get("regime_ma", REGIME_MA)
            btc_ma = _sma(self._btc_closes, regime_period)
            if btc_ma is not None:
                self.btc_ma = btc_ma
                hyst = self.cfg.get("regime_hysteresis", 0.05)
                if self._regime_state in ("bearish", "unknown"):
                    if self.btc_price >= btc_ma * (1 + hyst):
                        self._regime_state = "bullish"
                        self.regime_bullish = True
                elif self._regime_state == "bullish":
                    if self.btc_price <= btc_ma * (1 - hyst):
                        self._regime_state = "bearish"
                        self.regime_bullish = False

        if warmup:
            return []

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
                cooldown = self.cfg.get("exit_cooldown", 0)
                self._regime_cooldown = cooldown
                self._peak_equity = eq
                self._hours_in_position = 0
                return trades

        if pair != 'BTC-USD':
            return []

        self._last_candle_ts = candle.timestamp
        self._hours_since_rebal += 1
        self._hours_since_regime_check += 1

        if self._regime_cooldown > 0:
            self._regime_cooldown -= 1
        if self.holdings:
            self._hours_in_position += 1

        # Daily regime check
        min_hold = self.cfg.get("min_hold_hours", 0)
        if self._hours_since_regime_check >= 24:
            self._hours_since_regime_check = 0
            if not self.regime_bullish and self.holdings:
                if self._hours_in_position >= min_hold:
                    trades.extend(self._exit_all(candle.timestamp, "Regime exit"))
                    self._was_cash = True
                    self._regime_cooldown = self.cfg.get("exit_cooldown", 0)
                    self._hours_in_position = 0
                    return trades

        # Immediate entry from cash
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
                    self._regime_cooldown = self.cfg.get("exit_cooldown", 0)
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
        if self.cfg.get("rsi_filter"):
            max_rsi = self.cfg.get("max_rsi", 65)
            rsi = calc_rsi(closes)
            if rsi > max_rsi:
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
    buys = sum(1 for t in all_trades if t.side == "buy")

    # Compute avg hold time
    buy_times = {}
    hold_durations = []
    for t in all_trades:
        if t.side == "buy":
            buy_times[t.pair] = t.timestamp
        elif t.side == "sell" and t.pair in buy_times:
            dur = (t.timestamp - buy_times[t.pair]).total_seconds() / 3600
            hold_durations.append(dur)
            del buy_times[t.pair]

    avg_hold = sum(hold_durations) / len(hold_durations) if hold_durations else 0

    return {
        "pnl": pnl, "pnl_pct": pnl / starting_balance * 100,
        "max_dd": max_dd, "trades": len(all_trades), "buys": buys,
        "end_eq": end_eq, "peak_eq": peak_eq,
        "avg_hold_hrs": avg_hold,
        "equity_curve": equity_curve,
        "all_trades": all_trades,
    }


def main():
    conn = sqlite3.connect(DB)
    pair_data = conn.execute("""
        SELECT pair, COUNT(*) as cnt FROM candles
        GROUP BY pair HAVING cnt > 720 ORDER BY cnt DESC
    """).fetchall()
    all_pairs = [p[0] for p in pair_data]

    placeholders = ",".join("?" for _ in all_pairs)
    rows = conn.execute(
        f"""SELECT pair, timestamp, open, high, low, close, volume
            FROM candles WHERE pair IN ({placeholders})
            ORDER BY timestamp ASC""",
        all_pairs
    ).fetchall()
    conn.close()
    print(f"Loaded {len(rows)} candles, {len(all_pairs)} pairs\n")

    base = {
        "entry_type": "acceleration", "short_lb": 336, "long_lb": 720,
        "rebal_hours": 168, "top_n": 1,
        "reentry_threshold": 0.20, "regime_ma": 500,
        "stop_type": "none", "atr_mult": 0, "hard_stop_pct": 1.0,
        "rsi_filter": True, "max_rsi": 65, "overbought_filter": False,
        "equity_trail": True, "equity_trail_pct": 0.15,
        "regime_hysteresis": 0.05,
    }

    configs = {}

    # Cooldown sweep (0 to 72 hours) x min hold (0 to 168)
    for cd in [0, 2, 4, 6, 8, 12, 24, 48]:
        for mh in [0, 6, 12, 24, 48, 72, 168]:
            cd_label = f"{cd}h" if cd < 24 else f"{cd//24}d"
            mh_label = f"{mh}h" if mh < 24 else f"{mh//24}d"
            configs[f"CD={cd_label} MH={mh_label}"] = {
                **base,
                "exit_cooldown": cd,
                "min_hold_hours": mh,
            }

    results = {}
    total = len(configs)
    for idx, (name, cfg) in enumerate(configs.items(), 1):
        print(f"[{idx}/{total}] {name}...", end=" ", flush=True)
        try:
            r = run_test(rows, all_pairs, cfg, warmup=750)
            results[name] = r
            print(f"${r['pnl']:+,.0f} ({r['pnl_pct']:+.1f}%) Trades:{r['trades']} AvgHold:{r['avg_hold_hrs']:.0f}h")
        except Exception as e:
            print(f"ERROR: {e}")

    # Ranked
    print(f"\n{'=' * 105}")
    print(f"  COOLDOWN + MIN HOLD SWEEP (5% hysteresis locked)")
    print(f"{'=' * 105}")
    print(f"  {'#':>3}  {'Strategy':<25} {'P&L':>10} {'P&L%':>7} {'Peak':>8} {'MaxDD':>7} {'Trades':>7} {'AvgHold':>8}")
    print(f"  {'---':>3}  {'-'*25} {'-'*10} {'-'*7} {'-'*8} {'-'*7} {'-'*7} {'-'*8}")

    sorted_r = sorted(results.items(), key=lambda x: x[1]["pnl"], reverse=True)
    for rank, (name, r) in enumerate(sorted_r, 1):
        marker = " ***" if rank <= 10 else ""
        hold_str = f"{r['avg_hold_hrs']:.0f}h"
        print(f"  {rank:>3}. {name:<25} ${r['pnl']:>+8,.0f} {r['pnl_pct']:>+6.1f}% ${r['peak_eq']:>6,.0f} {r['max_dd']:>6.1f}% {r['trades']:>6} {hold_str:>8}{marker}")

    # Heatmap-style view
    print(f"\n\n  P&L HEATMAP: Cooldown (cols) x MinHold (rows)")
    print(f"  {'':>12}", end="")
    cds = [0, 2, 4, 6, 8, 12, 24, 48]
    mhs = [0, 6, 12, 24, 48, 72, 168]
    for cd in cds:
        cd_label = f"{cd}h" if cd < 24 else f"{cd//24}d"
        print(f"  {cd_label:>8}", end="")
    print()

    for mh in mhs:
        mh_label = f"{mh}h" if mh < 24 else f"{mh//24}d"
        print(f"  MH={mh_label:>6}", end="")
        for cd in cds:
            cd_label = f"{cd}h" if cd < 24 else f"{cd//24}d"
            key = f"CD={cd_label} MH={mh_label}"
            if key in results:
                pnl = results[key]["pnl"]
                print(f"  ${pnl:>+6,.0f}", end="")
            else:
                print(f"  {'N/A':>7}", end="")
        print()


if __name__ == "__main__":
    main()
