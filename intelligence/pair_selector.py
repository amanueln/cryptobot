"""Automatic pair discovery and selection.

Scans all Coinbase USD spot pairs, scores them on volatility, range-bound
behavior, liquidity, fee clearance, regime compatibility, and backtest P&L.
Selects the top N pairs and optimizes grid configs for each.
"""

import json
import logging
import math
import os
import statistics
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests
import yaml

from exchange.models import Candle
from exchange.coinbase_client import CoinbaseClient
from data.candle_store import CandleStore
from intelligence.regime_detector import RegimeDetector, MarketRegime
from strategies.grid_strategy import GridStrategy
from engine.backtester import Backtester

logger = logging.getLogger(__name__)

# Pairs to never trade (stablecoins, wrapped tokens, etc.)
DEFAULT_EXCLUDED = {
    "USDT-USD", "USDC-USD", "DAI-USD", "BUSD-USD", "PYUSD-USD",
    "WBTC-USD", "WETH-USD", "CBETH-USD", "STETH-USD",
    "GUSD-USD", "USDP-USD", "TUSD-USD", "FRAX-USD", "LUSD-USD",
    "EURC-USD", "GYEN-USD",
}

ROUND_TRIP_FEE_PCT = 0.6  # 0.3% maker + 0.3% taker (estimate)


def _score_pair_worker(args: tuple) -> "PairScore | None":
    """Top-level function for ProcessPoolExecutor (must be picklable).

    Args is a tuple of (pair, product_info, starting_balance, candles_data, config).
    candles_data is a list of dicts to avoid pickling Candle objects.
    """
    pair, product_info, starting_balance, candles_data, config = args

    # Reconstruct Candle objects from dicts
    candles = [
        Candle(pair=c["pair"], granularity=c["granularity"],
               timestamp=datetime.fromisoformat(c["timestamp"]),
               open=c["open"], high=c["high"], low=c["low"],
               close=c["close"], volume=c["volume"])
        for c in candles_data
    ]

    if not candles or len(candles) < 100:
        return None

    price = product_info["price"]
    volume_usd = product_info["volume_24h_usd"]
    max_active = config["max_active_pairs"]
    min_daily_vol = config["min_daily_vol_pct"]
    min_fee_clr = config["min_fee_clearance"]

    # 1. Volatility
    day_highs: dict[str, float] = {}
    day_lows: dict[str, float] = {}
    day_closes: dict[str, float] = {}
    for c in candles:
        day = c.timestamp.strftime("%Y-%m-%d")
        day_highs[day] = max(day_highs.get(day, c.high), c.high)
        day_lows[day] = min(day_lows.get(day, c.low), c.low)
        day_closes[day] = c.close
    daily_ranges = []
    for day in day_closes:
        close = day_closes[day]
        if close > 0:
            daily_ranges.append((day_highs[day] - day_lows[day]) / close * 100)
    volatility = statistics.mean(daily_ranges) if daily_ranges else 0
    if volatility < min_daily_vol:
        return None

    # 2. Range-bound
    closes = [c.close for c in candles]
    if len(closes) >= 14:
        mean_price = statistics.mean(closes)
        stdev = statistics.stdev(closes)
        if stdev > 0:
            in_range = sum(1 for c in closes if abs(c - mean_price) <= stdev)
            range_bound = (in_range / len(closes)) * 100
        else:
            range_bound = 100.0
    else:
        range_bound = 0

    # 3. Liquidity
    liquidity = math.log10(max(volume_usd, 1))

    # 4. Fee clearance
    fee_clearance = volatility / ROUND_TRIP_FEE_PCT if ROUND_TRIP_FEE_PCT > 0 else 0
    if fee_clearance < min_fee_clr:
        return None

    # 5. Regime detection (simplified inline)
    detector = RegimeDetector()
    regime = MarketRegime.UNKNOWN
    try:
        regime = detector.detect(candles)
    except Exception:
        pass
    bonus_map = {
        MarketRegime.RANGING: 1.0, MarketRegime.VOLATILE: 0.5,
        MarketRegime.SQUEEZE: 0.3, MarketRegime.TRENDING_UP: 0.2,
        MarketRegime.TRENDING_DOWN: 0.0,
    }
    regime_bonus = bonus_map.get(regime, 0.1)

    # 6. Quick grid backtest
    alloc = starting_balance / max_active
    backtest_pnl = 0.0
    if len(candles) >= 50:
        low = min(c.low for c in candles) * 0.98
        high = max(c.high for c in candles) * 1.02
        bt_config = {
            "pair": pair, "granularity": "ONE_HOUR",
            "upper_price": high, "lower_price": low, "num_grids": 10,
            "total_investment_usd": alloc, "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10, "adaptive_range": False,
            "max_trades_per_day": 20,
        }
        strategy = GridStrategy()
        strategy.configure(bt_config)
        backtester = Backtester()
        try:
            result = backtester.run(strategy, candles, alloc)
            backtest_pnl = result.total_pnl
        except Exception:
            pass

    return PairScore(
        pair=pair, composite_score=0, volatility=volatility,
        range_bound=range_bound, liquidity=liquidity, fee_clearance=fee_clearance,
        regime=regime, regime_bonus=regime_bonus, backtest_pnl=backtest_pnl,
        backtest_pnl_norm=0, candle_count=len(candles), price=price,
        volume_24h=volume_usd,
    )


@dataclass
class PairScore:
    pair: str
    composite_score: float
    volatility: float            # avg daily range as % of close
    range_bound: float           # % of days price stayed in 1-std-dev band
    liquidity: float             # log10 of avg 24h USD volume
    fee_clearance: float         # daily vol / round-trip fees ratio
    regime: MarketRegime
    regime_bonus: float
    backtest_pnl: float          # raw P&L from 14-day grid backtest
    backtest_pnl_norm: float     # normalized 0-1
    candle_count: int
    price: float
    volume_24h: float


@dataclass
class PairScanResult:
    timestamp: datetime
    scan_type: str               # "full" or "quick"
    total_scanned: int
    ranked: list[PairScore]      # all scored pairs, sorted by composite_score desc
    selected: list[PairScore]    # top N active pairs
    swapped_out: list[dict] = field(default_factory=list)
    swapped_in: list[dict] = field(default_factory=list)


@dataclass
class OptimizedConfig:
    pair: str
    config: dict
    backtest_pnl: float
    num_combos_tested: int


def load_pair_selector_config(path: str = "config/pair_selector.yaml") -> dict:
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


class PairSelector:
    def __init__(self, config: dict | None = None, db_path: str = "data/candles.db"):
        config = config or {}
        self.max_active_pairs: int = int(config.get("max_active_pairs", 3))
        self.min_24h_volume: float = float(config.get("min_24h_volume_usd", 100_000))
        self.min_daily_vol_pct: float = float(config.get("min_daily_volatility_pct", 3.0))
        self.min_fee_clearance: float = float(config.get("min_fee_clearance_ratio", 1.5))
        self.excluded: set[str] = set(config.get("excluded_pairs", [])) | DEFAULT_EXCLUDED
        self.optimization_combos: int = int(config.get("optimization_combos_per_pair", 100))
        self.backtest_days: int = int(config.get("backtest_days_for_scoring", 14))
        self.scan_interval_hours: int = int(config.get("scan_interval_hours", 24))
        self.quick_check_hours: int = int(config.get("quick_check_interval_hours", 6))

        self.db_path = db_path
        self.client = CoinbaseClient()
        self.store = CandleStore(db_path)

        self._last_full_scan: PairScanResult | None = None
        self._active_pairs: list[PairScore] = []
        self._active_configs: dict[str, dict] = {}  # pair -> optimized grid config

        # Thread-safe scan progress tracking
        self._progress_lock = threading.Lock()
        self._scan_progress: dict = {
            "scanning": False,
            "total_pairs": 0,
            "scanned": 0,
            "elapsed_seconds": 0,
            "estimated_remaining": 0,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_scan_progress(self) -> dict:
        """Return current scan progress (thread-safe)."""
        with self._progress_lock:
            return dict(self._scan_progress)

    def _update_progress(self, **kwargs) -> None:
        with self._progress_lock:
            self._scan_progress.update(kwargs)
            # Write to shared file for Flask API to read
            try:
                progress_path = os.path.join(os.path.dirname(self.db_path), "scan_progress.json")
                with open(progress_path, "w") as f:
                    json.dump(self._scan_progress, f)
            except Exception:
                pass  # non-critical

    def full_scan(self, starting_balance: float = 3000) -> PairScanResult:
        """Scan all Coinbase USD pairs, score, select top N, optimize configs."""
        logger.info("Starting full pair scan...")

        # Step 1: Get all eligible pairs
        products = self._fetch_products()
        eligible = self._filter_products(products)
        logger.info(f"Found {len(eligible)} eligible pairs out of {len(products)} total")

        # Step 2a: Pre-fetch all candles in parallel (I/O bound — threads help)
        total = len(eligible)
        logger.info(f"Pre-fetching candles for {total} pairs with 5 workers...")
        t0 = time.time()
        self._update_progress(scanning=True, total_pairs=total, scanned=0,
                              elapsed_seconds=0, estimated_remaining=0)
        candle_cache: dict[str, list] = {}
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(self._get_candles, prod["pair"], self.backtest_days): prod["pair"]
                for prod in eligible
            }
            fetched = 0
            for future in as_completed(futures):
                pair = futures[future]
                try:
                    candle_cache[pair] = future.result()
                except Exception as e:
                    logger.warning(f"Failed to fetch candles for {pair}: {e}")
                    candle_cache[pair] = []
                fetched += 1
                if fetched % 50 == 0:
                    elapsed = time.time() - t0
                    self._update_progress(scanned=fetched,
                                          elapsed_seconds=round(elapsed, 1),
                                          estimated_remaining=0)
        fetch_elapsed = time.time() - t0
        logger.info(f"Candles fetched in {fetch_elapsed:.1f}s")

        # Step 2b: Score each pair (CPU bound — use ProcessPoolExecutor to bypass GIL)
        worker_config = {
            "max_active_pairs": self.max_active_pairs,
            "min_daily_vol_pct": self.min_daily_vol_pct,
            "min_fee_clearance": self.min_fee_clearance,
        }
        # Serialize candles to dicts for pickling
        work_items = []
        for prod in eligible:
            pair = prod["pair"]
            candles = candle_cache.get(pair, [])
            candles_data = [
                {"pair": c.pair, "granularity": c.granularity,
                 "timestamp": c.timestamp.isoformat(),
                 "open": c.open, "high": c.high, "low": c.low,
                 "close": c.close, "volume": c.volume}
                for c in candles
            ]
            work_items.append((pair, prod, starting_balance, candles_data, worker_config))

        scored: list[PairScore] = []
        num_workers = min(os.cpu_count() or 4, 16)
        logger.info(f"Scoring {total} pairs with {num_workers} processes...")
        with ProcessPoolExecutor(max_workers=num_workers) as pool:
            futures = {
                pool.submit(_score_pair_worker, item): item[0]
                for item in work_items
            }
            done_count = 0
            for future in as_completed(futures):
                pair = futures[future]
                try:
                    score = future.result()
                    if score is not None:
                        scored.append(score)
                except Exception as e:
                    logger.warning(f"Failed to score {pair}: {e}")
                done_count += 1
                elapsed = time.time() - t0
                remaining = (elapsed / done_count) * (total - done_count) if done_count else 0
                self._update_progress(scanned=done_count,
                                      elapsed_seconds=round(elapsed, 1),
                                      estimated_remaining=round(remaining, 1))
        elapsed = time.time() - t0
        self._update_progress(scanning=False, scanned=total,
                              elapsed_seconds=round(elapsed, 1), estimated_remaining=0)
        logger.info(f"Scored {len(scored)}/{total} pairs in {elapsed:.1f}s")

        if not scored:
            logger.error("No pairs could be scored")
            return PairScanResult(
                timestamp=datetime.now(), scan_type="full",
                total_scanned=len(eligible), ranked=[], selected=[],
            )

        # Step 3: Normalize backtest P&L across all scored pairs
        self._normalize_backtest_pnl(scored)

        # Step 4: Calculate composite scores
        for s in scored:
            s.composite_score = self._composite_score(s)

        scored.sort(key=lambda s: s.composite_score, reverse=True)

        # Step 5: Select top N
        selected = scored[:self.max_active_pairs]

        # Track swaps
        old_pairs = {s.pair for s in self._active_pairs}
        new_pairs = {s.pair for s in selected}
        swapped_out = [
            {"pair": p, "reason": "score dropped below top N"}
            for p in old_pairs - new_pairs
        ]
        swapped_in = [
            {"pair": p, "reason": f"new top {self.max_active_pairs} by score"}
            for p in new_pairs - old_pairs
        ]

        # Step 6: Optimize configs for selected pairs
        alloc_per_pair = starting_balance / max(len(selected), 1)
        for s in selected:
            opt = self._optimize_config(s.pair, alloc_per_pair)
            if opt:
                self._active_configs[s.pair] = opt.config

        self._active_pairs = selected

        result = PairScanResult(
            timestamp=datetime.now(), scan_type="full",
            total_scanned=len(eligible), ranked=scored, selected=selected,
            swapped_out=swapped_out, swapped_in=swapped_in,
        )
        self._last_full_scan = result

        logger.info(
            f"Full scan complete: {len(scored)} scored, "
            f"selected {[s.pair for s in selected]}"
        )
        return result

    def quick_check(self, starting_balance: float = 3000) -> PairScanResult:
        """Re-check active pairs only. Swap out any that flipped to TRENDING_DOWN."""
        logger.info("Running quick check on active pairs...")

        refreshed: list[PairScore] = []
        for ps in self._active_pairs:
            try:
                candles = self._get_candles(ps.pair, days=7)
                if not candles or len(candles) < 50:
                    refreshed.append(ps)
                    continue
                regime = self._detect_regime(candles)
                ps.regime = regime
                ps.regime_bonus = self._regime_bonus(regime)
                ps.composite_score = self._composite_score(ps)
                refreshed.append(ps)
            except Exception as e:
                logger.warning(f"Quick check failed for {ps.pair}: {e}")
                refreshed.append(ps)

        swapped_out = []
        swapped_in = []

        # Check for TRENDING_DOWN — swap out
        bad = [ps for ps in refreshed if ps.regime == MarketRegime.TRENDING_DOWN]
        if bad and self._last_full_scan:
            active_set = {ps.pair for ps in refreshed}
            standby = [
                s for s in self._last_full_scan.ranked
                if s.pair not in active_set and s.regime != MarketRegime.TRENDING_DOWN
            ]

            for b in bad:
                if standby:
                    replacement = standby.pop(0)
                    swapped_out.append({"pair": b.pair, "reason": "regime flipped to TRENDING_DOWN"})
                    swapped_in.append({"pair": replacement.pair, "reason": "promoted from standby"})
                    refreshed.remove(b)
                    refreshed.append(replacement)

                    # Optimize config for new pair
                    alloc = starting_balance / max(len(refreshed), 1)
                    opt = self._optimize_config(replacement.pair, alloc)
                    if opt:
                        self._active_configs[replacement.pair] = opt.config

        self._active_pairs = refreshed

        return PairScanResult(
            timestamp=datetime.now(), scan_type="quick",
            total_scanned=len(refreshed), ranked=refreshed, selected=refreshed,
            swapped_out=swapped_out, swapped_in=swapped_in,
        )

    def get_active_pairs(self) -> list[str]:
        return [ps.pair for ps in self._active_pairs]

    def get_active_configs(self) -> dict[str, dict]:
        return dict(self._active_configs)

    def get_active_scores(self) -> list[PairScore]:
        return list(self._active_pairs)

    def get_last_scan(self) -> PairScanResult | None:
        return self._last_full_scan

    # ------------------------------------------------------------------
    # Coinbase product scanning
    # ------------------------------------------------------------------

    def _fetch_products(self) -> list[dict]:
        """Fetch all products from Coinbase public API."""
        url = "https://api.coinbase.com/api/v3/brokerage/market/products"
        try:
            resp = requests.get(url, timeout=30, params={"limit": "9999"})
            resp.raise_for_status()
            products = resp.json().get("products", [])
            return products
        except requests.RequestException as e:
            logger.error(f"Failed to fetch Coinbase products: {e}")
            return []

    def _filter_products(self, products: list[dict]) -> list[dict]:
        """Filter to eligible USD spot pairs."""
        eligible = []
        for p in products:
            product_id = p.get("product_id", "")
            # Must be USD quote
            if not product_id.endswith("-USD"):
                continue
            # Must be spot
            if p.get("product_type", "") != "SPOT":
                continue
            # Not excluded
            if product_id in self.excluded:
                continue
            # Must not be disabled
            if p.get("is_disabled", False):
                continue
            if p.get("trading_disabled", False):
                continue

            # Volume filter
            volume_24h = float(p.get("volume_24h", 0) or 0)
            price = float(p.get("price", 0) or 0)
            volume_usd = volume_24h * price

            if volume_usd < self.min_24h_volume:
                continue

            eligible.append({
                "pair": product_id,
                "price": price,
                "volume_24h_usd": volume_usd,
                "volume_24h": volume_24h,
            })

        return eligible

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_pair(
        self, pair: str, product_info: dict, starting_balance: float,
        candles: list | None = None,
    ) -> PairScore | None:
        """Score a single pair on all metrics."""
        if candles is None:
            candles = self._get_candles(pair, days=self.backtest_days)
        if not candles or len(candles) < 100:
            return None

        price = product_info["price"]
        volume_usd = product_info["volume_24h_usd"]

        # 1. Daily volatility: avg(daily_range / close)
        volatility = self._calc_volatility(candles)
        if volatility < self.min_daily_vol_pct:
            return None

        # 2. Range-bound score: % of days within 1 std dev of mean
        range_bound = self._calc_range_bound(candles)

        # 3. Liquidity: log10 of 24h volume in USD
        liquidity = math.log10(max(volume_usd, 1))

        # 4. Fee clearance: daily vol % / round-trip fee %
        fee_clearance = volatility / ROUND_TRIP_FEE_PCT if ROUND_TRIP_FEE_PCT > 0 else 0
        if fee_clearance < self.min_fee_clearance:
            return None

        # 5. Regime detection
        regime = self._detect_regime(candles)
        regime_bonus = self._regime_bonus(regime)

        # 6. Quick grid backtest
        alloc = starting_balance / self.max_active_pairs
        backtest_pnl = self._quick_backtest(pair, candles, alloc)

        return PairScore(
            pair=pair,
            composite_score=0,  # calculated after normalization
            volatility=volatility,
            range_bound=range_bound,
            liquidity=liquidity,
            fee_clearance=fee_clearance,
            regime=regime,
            regime_bonus=regime_bonus,
            backtest_pnl=backtest_pnl,
            backtest_pnl_norm=0,  # normalized later
            candle_count=len(candles),
            price=price,
            volume_24h=volume_usd,
        )

    def _calc_volatility(self, candles: list[Candle]) -> float:
        """Average daily (high - low) / close as percentage."""
        # Group by day
        daily_ranges: list[float] = []
        day_highs: dict[str, float] = {}
        day_lows: dict[str, float] = {}
        day_closes: dict[str, float] = {}

        for c in candles:
            day = c.timestamp.strftime("%Y-%m-%d")
            day_highs[day] = max(day_highs.get(day, c.high), c.high)
            day_lows[day] = min(day_lows.get(day, c.low), c.low)
            day_closes[day] = c.close

        for day in day_closes:
            if day in day_highs and day in day_lows:
                close = day_closes[day]
                if close > 0:
                    daily_ranges.append((day_highs[day] - day_lows[day]) / close * 100)

        return statistics.mean(daily_ranges) if daily_ranges else 0

    def _calc_range_bound(self, candles: list[Candle]) -> float:
        """% of days where close stayed within 1 std dev of 14-day mean."""
        closes = [c.close for c in candles]
        if len(closes) < 14:
            return 0

        mean_price = statistics.mean(closes)
        std_dev = statistics.stdev(closes) if len(closes) > 1 else 0
        if std_dev == 0:
            return 100

        # Group by day and check if day's close is within band
        day_closes: dict[str, float] = {}
        for c in candles:
            day = c.timestamp.strftime("%Y-%m-%d")
            day_closes[day] = c.close

        in_range = sum(
            1 for close in day_closes.values()
            if abs(close - mean_price) <= std_dev
        )
        return (in_range / len(day_closes)) * 100 if day_closes else 0

    def _detect_regime(self, candles: list[Candle]) -> MarketRegime:
        """Run regime detector on candle history, return final regime."""
        detector = RegimeDetector()
        regime = MarketRegime.UNKNOWN
        for c in candles:
            regime = detector.update(c)
        return regime

    def _regime_bonus(self, regime: MarketRegime) -> float:
        return {
            MarketRegime.RANGING: 1.0,
            MarketRegime.VOLATILE: 0.5,
            MarketRegime.SQUEEZE: 0.3,
            MarketRegime.TRENDING_UP: 0.1,
            MarketRegime.TRENDING_DOWN: 0.0,
            MarketRegime.UNKNOWN: 0.2,
        }.get(regime, 0.2)

    def _quick_backtest(self, pair: str, candles: list[Candle], allocation: float) -> float:
        """Run a quick grid backtest with default config. Returns P&L in USD."""
        if len(candles) < 50:
            return 0

        closes = [c.close for c in candles]
        low = min(c.low for c in candles) * 0.98
        high = max(c.high for c in candles) * 1.02

        config = {
            "pair": pair,
            "granularity": "ONE_HOUR",
            "upper_price": high,
            "lower_price": low,
            "num_grids": 10,
            "total_investment_usd": allocation,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.10,
            "adaptive_range": False,
            "max_trades_per_day": 20,
        }

        strategy = GridStrategy()
        strategy.configure(config)

        backtester = Backtester()
        try:
            result = backtester.run(strategy, candles, allocation)
            return result.total_pnl
        except Exception as e:
            logger.warning(f"Backtest failed for {pair}: {e}")
            return 0

    def _normalize_backtest_pnl(self, scored: list[PairScore]) -> None:
        """Normalize backtest P&L to 0-1 range across all scored pairs."""
        pnls = [s.backtest_pnl for s in scored]
        if not pnls:
            return
        min_pnl = min(pnls)
        max_pnl = max(pnls)
        rng = max_pnl - min_pnl
        if rng == 0:
            for s in scored:
                s.backtest_pnl_norm = 0.5
        else:
            for s in scored:
                s.backtest_pnl_norm = (s.backtest_pnl - min_pnl) / rng

    def _composite_score(self, s: PairScore) -> float:
        """Weighted composite score. Normalize each component to roughly 0-1."""
        # Volatility: cap at 20% daily → normalize to 0-1
        vol_norm = min(s.volatility / 20.0, 1.0)
        # Range-bound: already 0-100, normalize to 0-1
        rb_norm = s.range_bound / 100.0
        # Liquidity: log10(volume). Typical range 5-10. Normalize 5→0, 10→1
        liq_norm = min(max((s.liquidity - 5.0) / 5.0, 0), 1.0)
        # Fee clearance: typical 1-10x. Normalize 1→0, 10→1
        fc_norm = min(max((s.fee_clearance - 1.0) / 9.0, 0), 1.0)
        # Regime bonus: already 0-1
        # Backtest P&L norm: already 0-1

        return (
            vol_norm * 0.20 +
            rb_norm * 0.25 +
            liq_norm * 0.15 +
            fc_norm * 0.15 +
            s.regime_bonus * 0.10 +
            s.backtest_pnl_norm * 0.15
        )

    # ------------------------------------------------------------------
    # Config optimization (mini parameter sweep)
    # ------------------------------------------------------------------

    def _optimize_config(self, pair: str, allocation: float) -> OptimizedConfig | None:
        """Run a mini parameter sweep to find best grid config for a pair."""
        candles = self._get_candles(pair, days=self.backtest_days)
        if not candles or len(candles) < 50:
            return None

        closes = [c.close for c in candles]
        low = min(c.low for c in candles)
        high = max(c.high for c in candles)

        # Parameter grid
        grid_counts = [8, 10, 12, 15, 20]
        range_pads = [0.02, 0.05, 0.08]  # % padding beyond observed range
        spacing_floors = [0.005, 0.01, 0.015, 0.02]
        lookbacks = [7, 14, 21]

        best_pnl = float("-inf")
        best_config = None
        combos_tested = 0

        for num_grids in grid_counts:
            for pad in range_pads:
                for spacing in spacing_floors:
                    for lookback in lookbacks:
                        if combos_tested >= self.optimization_combos:
                            break

                        config = {
                            "pair": pair,
                            "granularity": "ONE_HOUR",
                            "upper_price": high * (1 + pad),
                            "lower_price": low * (1 - pad),
                            "num_grids": num_grids,
                            "total_investment_usd": allocation,
                            "stop_loss_pct": 0.15,
                            "take_profit_pct": 0.10,
                            "adaptive_range": True,
                            "range_lookback_days": lookback,
                            "recalc_interval_hours": 12,
                            "min_spacing_pct": spacing,
                            "max_trades_per_day": 20,
                            "range_only_filter": True,
                            "ema_convergence_pct": 3.0,
                            "ema_fast_period": 50,
                            "ema_slow_period": 200,
                        }

                        strategy = GridStrategy()
                        strategy.configure(config)
                        backtester = Backtester()

                        try:
                            result = backtester.run(strategy, candles, allocation)
                            if result.total_pnl > best_pnl:
                                best_pnl = result.total_pnl
                                best_config = config
                        except Exception:
                            pass

                        combos_tested += 1

        if best_config is None:
            return None

        return OptimizedConfig(
            pair=pair, config=best_config,
            backtest_pnl=best_pnl, num_combos_tested=combos_tested,
        )

    # ------------------------------------------------------------------
    # Candle fetching
    # ------------------------------------------------------------------

    def _get_candles(self, pair: str, days: int) -> list[Candle]:
        """Get candles from cache or fetch from Coinbase."""
        end = datetime.now()
        start = end - timedelta(days=days)
        granularity = "ONE_HOUR"

        # Try cache first
        cached = self.store.get_candles(pair, granularity, start, end)
        expected = int(days * 24 * 0.7)  # 70% coverage threshold

        if cached and len(cached) >= expected:
            return cached

        # Fetch from Coinbase with retry-on-429
        try:
            fetched = self._fetch_candles_with_retry(pair, granularity, start, end)
            if fetched:
                self.store.save_candles(pair, granularity, fetched)
                return fetched
        except Exception as e:
            logger.warning(f"Failed to fetch candles for {pair}: {e}")

        return cached or []

    def _fetch_candles_with_retry(
        self, pair: str, granularity: str, start: datetime, end: datetime,
        max_retries: int = 3,
    ) -> list[Candle]:
        """Fetch candles with automatic retry on 429 rate limits."""
        for attempt in range(max_retries):
            try:
                return self.client.get_candles(pair, granularity, start, end)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    backoff = 2 * (attempt + 1)
                    logger.debug(f"Rate limited on {pair}, backing off {backoff}s")
                    time.sleep(backoff)
                    continue
                raise
        # Final attempt without catching
        return self.client.get_candles(pair, granularity, start, end)

    # ------------------------------------------------------------------
    # Serialization for SQLite / API
    # ------------------------------------------------------------------

    def scan_result_to_dict(self, result: PairScanResult) -> dict:
        """Convert scan result to JSON-serializable dict."""
        return {
            "timestamp": result.timestamp.isoformat(),
            "scan_type": result.scan_type,
            "total_scanned": result.total_scanned,
            "ranked": [self._score_to_dict(s) for s in result.ranked[:50]],
            "selected": [self._score_to_dict(s) for s in result.selected],
            "swapped_out": result.swapped_out,
            "swapped_in": result.swapped_in,
        }

    def _score_to_dict(self, s: PairScore) -> dict:
        return {
            "pair": s.pair,
            "composite_score": round(s.composite_score * 100, 1),
            "volatility": round(s.volatility, 2),
            "range_bound": round(s.range_bound, 1),
            "liquidity": round(s.liquidity, 2),
            "fee_clearance": round(s.fee_clearance, 2),
            "regime": s.regime.value,
            "regime_bonus": s.regime_bonus,
            "backtest_pnl": round(s.backtest_pnl, 2),
            "candle_count": s.candle_count,
            "price": s.price,
            "volume_24h": round(s.volume_24h, 0),
        }

    def generate_explanation(self, result: PairScanResult) -> str:
        """Generate human-readable explanation of pair selection."""
        if not result.selected:
            return "No pairs selected — insufficient data or all pairs filtered out."

        total = result.total_scanned
        when = result.timestamp.strftime("%I:%M %p")
        selected = result.selected

        parts = [
            f"The bot selected {', '.join(s.pair for s in selected)} as the top "
            f"{len(selected)} pairs out of {total} eligible Coinbase pairs "
            f"scanned at {when}."
        ]

        for i, s in enumerate(selected):
            score_pct = s.composite_score * 100
            pair_short = s.pair.replace("-USD", "")
            detail = (
                f"{s.pair} (score {score_pct:.0f}): "
                f"Daily volatility {s.volatility:.1f}% "
                f"with {s.range_bound:.0f}% range-bound behavior. "
                f"Currently in {s.regime.value.upper()} regime"
            )
            if s.regime == MarketRegime.RANGING:
                detail += " — ideal for grid trading"
            elif s.regime == MarketRegime.VOLATILE:
                detail += " — grid running at reduced size"

            detail += f". Fee clearance {s.fee_clearance:.1f}x."
            if s.backtest_pnl != 0:
                sign = "+" if s.backtest_pnl >= 0 else ""
                detail += f" 14-day backtest returned {sign}${s.backtest_pnl:.2f}."

            parts.append(detail)

        # Note next scan
        parts.append(
            f"Next full scan in {self.scan_interval_hours} hours."
        )

        return " ".join(parts)
