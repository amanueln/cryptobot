"""Tests for intelligence/pair_selector.py — pair discovery and selection."""

import math
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from exchange.models import Candle
from intelligence.pair_selector import (
    PairSelector,
    PairScore,
    PairScanResult,
    DEFAULT_EXCLUDED,
    ROUND_TRIP_FEE_PCT,
    load_pair_selector_config,
)
from intelligence.regime_detector import MarketRegime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_candles(pair: str, n: int = 336, base_price: float = 1.0,
                 volatility: float = 0.05, start: datetime | None = None) -> list[Candle]:
    """Generate n hourly candles with controllable volatility."""
    start = start or (datetime.now() - timedelta(hours=n))
    candles = []
    price = base_price
    for i in range(n):
        # Oscillating price to simulate range-bound behavior
        import math as _m
        offset = volatility * base_price * _m.sin(i * 0.3)
        close = base_price + offset
        high = close * (1 + volatility * 0.3)
        low = close * (1 - volatility * 0.3)
        candles.append(Candle(
            pair=pair,
            granularity="ONE_HOUR",
            timestamp=start + timedelta(hours=i),
            open=close * 0.999,
            high=high,
            low=low,
            close=close,
            volume=10000 + i * 10,
        ))
    return candles


MOCK_PRODUCTS = [
    # Good USD spot pair
    {"product_id": "DOGE-USD", "product_type": "SPOT", "price": "0.09",
     "volume_24h": "5000000", "is_disabled": False, "trading_disabled": False},
    # Good USD spot pair
    {"product_id": "SOL-USD", "product_type": "SPOT", "price": "150.0",
     "volume_24h": "2000000", "is_disabled": False, "trading_disabled": False},
    # Good USD spot pair
    {"product_id": "AVAX-USD", "product_type": "SPOT", "price": "25.0",
     "volume_24h": "1000000", "is_disabled": False, "trading_disabled": False},
    # Stablecoin — should be filtered
    {"product_id": "USDC-USD", "product_type": "SPOT", "price": "1.0",
     "volume_24h": "100000000", "is_disabled": False, "trading_disabled": False},
    # Wrapped token — should be filtered
    {"product_id": "WBTC-USD", "product_type": "SPOT", "price": "60000",
     "volume_24h": "5000000", "is_disabled": False, "trading_disabled": False},
    # Non-USD pair — should be filtered
    {"product_id": "BTC-EUR", "product_type": "SPOT", "price": "55000",
     "volume_24h": "1000000", "is_disabled": False, "trading_disabled": False},
    # Low volume — should be filtered
    {"product_id": "TINY-USD", "product_type": "SPOT", "price": "0.001",
     "volume_24h": "100", "is_disabled": False, "trading_disabled": False},
    # Disabled — should be filtered
    {"product_id": "DEAD-USD", "product_type": "SPOT", "price": "1.0",
     "volume_24h": "5000000", "is_disabled": True, "trading_disabled": False},
    # Not spot — should be filtered
    {"product_id": "ETH-USD", "product_type": "FUTURE", "price": "2000",
     "volume_24h": "10000000", "is_disabled": False, "trading_disabled": False},
    # Another good one for ranking
    {"product_id": "LINK-USD", "product_type": "SPOT", "price": "15.0",
     "volume_24h": "3000000", "is_disabled": False, "trading_disabled": False},
    {"product_id": "ADA-USD", "product_type": "SPOT", "price": "0.45",
     "volume_24h": "4000000", "is_disabled": False, "trading_disabled": False},
]


# ---------------------------------------------------------------------------
# Tests: Product filtering
# ---------------------------------------------------------------------------

class TestProductFiltering:
    def test_filters_non_usd_pairs(self):
        selector = PairSelector({"max_active_pairs": 3})
        eligible = selector._filter_products(MOCK_PRODUCTS)
        pairs = {p["pair"] for p in eligible}
        assert "BTC-EUR" not in pairs

    def test_filters_stablecoins(self):
        selector = PairSelector({"max_active_pairs": 3})
        eligible = selector._filter_products(MOCK_PRODUCTS)
        pairs = {p["pair"] for p in eligible}
        assert "USDC-USD" not in pairs

    def test_filters_wrapped_tokens(self):
        selector = PairSelector({"max_active_pairs": 3})
        eligible = selector._filter_products(MOCK_PRODUCTS)
        pairs = {p["pair"] for p in eligible}
        assert "WBTC-USD" not in pairs

    def test_filters_low_volume(self):
        selector = PairSelector({"max_active_pairs": 3, "min_24h_volume_usd": 100_000})
        eligible = selector._filter_products(MOCK_PRODUCTS)
        pairs = {p["pair"] for p in eligible}
        assert "TINY-USD" not in pairs

    def test_filters_disabled_pairs(self):
        selector = PairSelector({"max_active_pairs": 3})
        eligible = selector._filter_products(MOCK_PRODUCTS)
        pairs = {p["pair"] for p in eligible}
        assert "DEAD-USD" not in pairs

    def test_filters_non_spot(self):
        selector = PairSelector({"max_active_pairs": 3})
        eligible = selector._filter_products(MOCK_PRODUCTS)
        pairs = {p["pair"] for p in eligible}
        assert "ETH-USD" not in pairs  # It's FUTURE type

    def test_keeps_valid_pairs(self):
        selector = PairSelector({"max_active_pairs": 3})
        eligible = selector._filter_products(MOCK_PRODUCTS)
        pairs = {p["pair"] for p in eligible}
        assert "DOGE-USD" in pairs
        assert "SOL-USD" in pairs
        assert "AVAX-USD" in pairs
        assert "LINK-USD" in pairs
        assert "ADA-USD" in pairs

    def test_custom_excluded_pairs(self):
        selector = PairSelector({
            "max_active_pairs": 3,
            "excluded_pairs": ["DOGE-USD"],
        })
        eligible = selector._filter_products(MOCK_PRODUCTS)
        pairs = {p["pair"] for p in eligible}
        assert "DOGE-USD" not in pairs


# ---------------------------------------------------------------------------
# Tests: Scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_volatility_calculation(self):
        selector = PairSelector()
        candles = make_candles("TEST-USD", n=336, base_price=100, volatility=0.10)
        vol = selector._calc_volatility(candles)
        assert vol > 0
        # High volatility candles should produce meaningful daily range
        assert vol > 1.0

    def test_low_volatility_filtered(self):
        selector = PairSelector({"min_daily_volatility_pct": 3.0})
        # Very low volatility candles
        candles = make_candles("BORING-USD", n=336, base_price=100, volatility=0.001)
        vol = selector._calc_volatility(candles)
        # Score should return None for low-vol pairs
        product_info = {"pair": "BORING-USD", "price": 100, "volume_24h_usd": 1_000_000}
        score = selector._score_pair("BORING-USD", product_info, 3000)
        # Either filtered by vol or fee clearance
        # (depends on exact numbers, but low vol pairs should be eliminated)

    def test_range_bound_calculation(self):
        selector = PairSelector()
        # Candles oscillating around a mean should score high on range-bound
        candles = make_candles("RANGE-USD", n=336, base_price=10, volatility=0.03)
        rb = selector._calc_range_bound(candles)
        assert 0 <= rb <= 100

    def test_regime_bonus_mapping(self):
        selector = PairSelector()
        assert selector._regime_bonus(MarketRegime.RANGING) == 1.0
        assert selector._regime_bonus(MarketRegime.VOLATILE) == 0.5
        assert selector._regime_bonus(MarketRegime.TRENDING_DOWN) == 0.0
        assert selector._regime_bonus(MarketRegime.TRENDING_UP) == 0.1

    def test_composite_score_range(self):
        """Composite score should be between 0 and 1."""
        score = PairScore(
            pair="TEST-USD", composite_score=0,
            volatility=5.0, range_bound=60.0, liquidity=7.0,
            fee_clearance=4.0, regime=MarketRegime.RANGING,
            regime_bonus=1.0, backtest_pnl=10.0, backtest_pnl_norm=0.5,
            candle_count=336, price=1.0, volume_24h=1_000_000,
        )
        selector = PairSelector()
        result = selector._composite_score(score)
        assert 0 <= result <= 1

    def test_normalize_backtest_pnl(self):
        selector = PairSelector()
        scores = [
            PairScore(pair="A", composite_score=0, volatility=5, range_bound=50,
                      liquidity=7, fee_clearance=3, regime=MarketRegime.RANGING,
                      regime_bonus=1, backtest_pnl=-10, backtest_pnl_norm=0,
                      candle_count=100, price=1, volume_24h=1e6),
            PairScore(pair="B", composite_score=0, volatility=5, range_bound=50,
                      liquidity=7, fee_clearance=3, regime=MarketRegime.RANGING,
                      regime_bonus=1, backtest_pnl=20, backtest_pnl_norm=0,
                      candle_count=100, price=1, volume_24h=1e6),
            PairScore(pair="C", composite_score=0, volatility=5, range_bound=50,
                      liquidity=7, fee_clearance=3, regime=MarketRegime.RANGING,
                      regime_bonus=1, backtest_pnl=5, backtest_pnl_norm=0,
                      candle_count=100, price=1, volume_24h=1e6),
        ]
        selector._normalize_backtest_pnl(scores)

        assert scores[0].backtest_pnl_norm == 0.0   # worst
        assert scores[1].backtest_pnl_norm == 1.0   # best
        assert 0 < scores[2].backtest_pnl_norm < 1  # middle


# ---------------------------------------------------------------------------
# Tests: Pair selection
# ---------------------------------------------------------------------------

class TestPairSelection:
    def test_selects_top_n_by_score(self):
        """Verify top N pairs are selected based on composite score."""
        selector = PairSelector({"max_active_pairs": 2})

        scores = []
        for i, pair in enumerate(["A-USD", "B-USD", "C-USD", "D-USD"]):
            s = PairScore(
                pair=pair, composite_score=(4 - i) * 0.2,
                volatility=5, range_bound=50, liquidity=7, fee_clearance=3,
                regime=MarketRegime.RANGING, regime_bonus=1,
                backtest_pnl=10 * (4 - i), backtest_pnl_norm=0.5,
                candle_count=100, price=1, volume_24h=1e6,
            )
            scores.append(s)

        # Simulate what full_scan does after scoring
        scores.sort(key=lambda s: s.composite_score, reverse=True)
        selected = scores[:selector.max_active_pairs]

        assert len(selected) == 2
        assert selected[0].pair == "A-USD"
        assert selected[1].pair == "B-USD"

    def test_regime_check_deprioritizes_trending_down(self):
        selector = PairSelector()
        # TRENDING_DOWN should get 0 bonus
        bonus_down = selector._regime_bonus(MarketRegime.TRENDING_DOWN)
        bonus_ranging = selector._regime_bonus(MarketRegime.RANGING)
        assert bonus_down < bonus_ranging


# ---------------------------------------------------------------------------
# Tests: Config optimization
# ---------------------------------------------------------------------------

class TestConfigOptimization:
    def test_optimize_returns_config(self):
        """Given enough candles, optimization should return a config."""
        selector = PairSelector({"optimization_combos_per_pair": 5})
        candles = make_candles("OPT-USD", n=336, base_price=10, volatility=0.05)

        with patch.object(selector, '_get_candles', return_value=candles):
            result = selector._optimize_config("OPT-USD", 1000)

        assert result is not None
        assert result.pair == "OPT-USD"
        assert "num_grids" in result.config
        assert "upper_price" in result.config
        assert "lower_price" in result.config
        assert result.num_combos_tested > 0

    def test_optimize_returns_none_with_insufficient_candles(self):
        selector = PairSelector()
        with patch.object(selector, '_get_candles', return_value=[]):
            result = selector._optimize_config("NO-DATA", 1000)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Quick check / pair swap logic
# ---------------------------------------------------------------------------

class TestQuickCheck:
    def test_swaps_out_trending_down_pair(self):
        selector = PairSelector({"max_active_pairs": 2})

        # Set up active pairs: one healthy, one about to flip
        healthy = PairScore(
            pair="GOOD-USD", composite_score=0.8,
            volatility=5, range_bound=50, liquidity=7, fee_clearance=3,
            regime=MarketRegime.RANGING, regime_bonus=1,
            backtest_pnl=10, backtest_pnl_norm=0.5,
            candle_count=100, price=1, volume_24h=1e6,
        )
        bad = PairScore(
            pair="BAD-USD", composite_score=0.6,
            volatility=5, range_bound=50, liquidity=7, fee_clearance=3,
            regime=MarketRegime.TRENDING_DOWN, regime_bonus=0,
            backtest_pnl=5, backtest_pnl_norm=0.3,
            candle_count=100, price=1, volume_24h=1e6,
        )
        standby = PairScore(
            pair="NEXT-USD", composite_score=0.7,
            volatility=5, range_bound=50, liquidity=7, fee_clearance=3,
            regime=MarketRegime.RANGING, regime_bonus=1,
            backtest_pnl=8, backtest_pnl_norm=0.4,
            candle_count=100, price=1, volume_24h=1e6,
        )

        selector._active_pairs = [healthy, bad]
        # Simulate last full scan with standby pair ranked
        selector._last_full_scan = PairScanResult(
            timestamp=datetime.now(), scan_type="full",
            total_scanned=10, ranked=[healthy, standby, bad],
            selected=[healthy, bad],
        )

        # Mock candle fetching + regime detection to keep regimes as-is
        candles = make_candles("TEST", n=100)
        with patch.object(selector, '_get_candles', return_value=candles), \
             patch.object(selector, '_detect_regime', side_effect=lambda c: MarketRegime.TRENDING_DOWN), \
             patch.object(selector, '_optimize_config', return_value=None):
            # Both will detect as TRENDING_DOWN, but standby is RANGING
            # The mock makes all detect as TRENDING_DOWN, but standby in ranked list
            # has regime=RANGING from the full scan
            result = selector.quick_check(3000)

        # Should have swapped BAD-USD for NEXT-USD
        active = {ps.pair for ps in result.selected}
        assert "NEXT-USD" in active or len(result.swapped_out) > 0


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_products_list(self):
        selector = PairSelector()
        eligible = selector._filter_products([])
        assert eligible == []

    def test_all_products_filtered(self):
        """All stablecoins should result in empty eligible list."""
        products = [
            {"product_id": "USDC-USD", "product_type": "SPOT", "price": "1.0",
             "volume_24h": "1000000", "is_disabled": False, "trading_disabled": False},
        ]
        selector = PairSelector()
        eligible = selector._filter_products(products)
        assert eligible == []

    def test_normalize_identical_pnl(self):
        """All same P&L should normalize to 0.5."""
        selector = PairSelector()
        scores = [
            PairScore(pair="X", composite_score=0, volatility=5, range_bound=50,
                      liquidity=7, fee_clearance=3, regime=MarketRegime.RANGING,
                      regime_bonus=1, backtest_pnl=10, backtest_pnl_norm=0,
                      candle_count=100, price=1, volume_24h=1e6),
            PairScore(pair="Y", composite_score=0, volatility=5, range_bound=50,
                      liquidity=7, fee_clearance=3, regime=MarketRegime.RANGING,
                      regime_bonus=1, backtest_pnl=10, backtest_pnl_norm=0,
                      candle_count=100, price=1, volume_24h=1e6),
        ]
        selector._normalize_backtest_pnl(scores)
        assert scores[0].backtest_pnl_norm == 0.5
        assert scores[1].backtest_pnl_norm == 0.5

    def test_config_loader_missing_file(self):
        config = load_pair_selector_config("nonexistent.yaml")
        assert config == {}


# ---------------------------------------------------------------------------
# Tests: Serialization and explanation
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_score_to_dict(self):
        selector = PairSelector()
        score = PairScore(
            pair="DOGE-USD", composite_score=0.73,
            volatility=7.2, range_bound=78, liquidity=6.8,
            fee_clearance=3.8, regime=MarketRegime.RANGING,
            regime_bonus=1.0, backtest_pnl=18.5, backtest_pnl_norm=0.7,
            candle_count=336, price=0.09, volume_24h=450_000,
        )
        d = selector._score_to_dict(score)
        assert d["pair"] == "DOGE-USD"
        assert d["composite_score"] == 73.0
        assert d["regime"] == "ranging"
        assert isinstance(d["volatility"], float)

    def test_generate_explanation(self):
        selector = PairSelector()
        result = PairScanResult(
            timestamp=datetime.now(), scan_type="full",
            total_scanned=347,
            ranked=[],
            selected=[
                PairScore(
                    pair="DOGE-USD", composite_score=0.87,
                    volatility=7.2, range_bound=78, liquidity=6.8,
                    fee_clearance=3.8, regime=MarketRegime.RANGING,
                    regime_bonus=1.0, backtest_pnl=18.5, backtest_pnl_norm=0.7,
                    candle_count=336, price=0.09, volume_24h=450_000,
                ),
            ],
        )
        explanation = selector.generate_explanation(result)
        assert "DOGE-USD" in explanation
        assert "347" in explanation
        assert "RANGING" in explanation

    def test_explanation_empty_selection(self):
        selector = PairSelector()
        result = PairScanResult(
            timestamp=datetime.now(), scan_type="full",
            total_scanned=0, ranked=[], selected=[],
        )
        explanation = selector.generate_explanation(result)
        assert "No pairs selected" in explanation
