"""Tests for intelligence/ml_predictor.py — ML regression prediction layer."""

import math
import os
import shutil
import tempfile
from datetime import datetime, timedelta

import numpy as np
import pytest

from exchange.models import Candle
from intelligence.ml_predictor import (
    MLPredictor,
    MLPrediction,
    FeatureExtractor,
    OutlierDetector,
    _explain_feature,
    load_ml_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_candles(pair: str = "TEST-USD", n: int = 600, base_price: float = 100.0,
                 volatility: float = 0.02, trend: float = 0.0) -> list[Candle]:
    """Generate n hourly candles with controllable properties."""
    candles = []
    price = base_price
    start = datetime.now() - timedelta(hours=n)
    for i in range(n):
        noise = volatility * price * math.sin(i * 0.5) + volatility * price * 0.3 * math.sin(i * 1.7)
        price = base_price + trend * i + noise
        price = max(price, base_price * 0.5)
        high = price * (1 + abs(volatility) * 0.5)
        low = price * (1 - abs(volatility) * 0.5)
        candles.append(Candle(
            pair=pair,
            granularity="ONE_HOUR",
            timestamp=start + timedelta(hours=i),
            open=price * 0.999,
            high=high,
            low=low,
            close=price,
            volume=50000 + 1000 * math.sin(i * 0.2),
        ))
    return candles


@pytest.fixture
def tmp_models_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def predictor(tmp_models_dir):
    return MLPredictor(
        config={"min_training_candles": 100, "include_timeframes": ["1h"]},
        models_dir=tmp_models_dir,
    )


@pytest.fixture
def candles():
    return make_candles(n=600, volatility=0.03)


# ---------------------------------------------------------------------------
# Tests: Feature extraction
# ---------------------------------------------------------------------------

class TestFeatureExtraction:
    def test_features_extracted(self):
        extractor = FeatureExtractor({"min_training_candles": 100, "include_timeframes": ["1h"]})
        candles = make_candles(n=500)
        features = extractor.extract_features(candles, 450)
        assert features is not None
        names = extractor.get_feature_names()
        for name in names:
            assert name in features, f"Missing feature: {name}"

    def test_returns_none_insufficient_data(self):
        extractor = FeatureExtractor({"min_training_candles": 400, "include_timeframes": ["1h"]})
        candles = make_candles(n=10)
        features = extractor.extract_features(candles, 5)
        assert features is None

    def test_no_nan_values(self):
        extractor = FeatureExtractor({"min_training_candles": 100, "include_timeframes": ["1h"]})
        candles = make_candles(n=300)
        features = extractor.extract_features(candles, 250)
        assert features is not None
        for name, val in features.items():
            assert not np.isnan(val), f"NaN in feature {name}"

    def test_multi_period_features(self):
        extractor = FeatureExtractor({
            "min_training_candles": 100,
            "include_timeframes": ["1h"],
            "indicator_periods": [10, 14, 20],
        })
        names = extractor.get_feature_names()
        assert "rsi_10_1h_s0" in names
        assert "rsi_14_1h_s0" in names
        assert "rsi_20_1h_s0" in names

    def test_shifted_features(self):
        extractor = FeatureExtractor({
            "min_training_candles": 100,
            "include_timeframes": ["1h"],
            "include_shifted_candles": 2,
        })
        names = extractor.get_feature_names()
        assert "rsi_14_1h_s0" in names
        assert "rsi_14_1h_s1" in names
        assert "rsi_14_1h_s2" in names

    def test_multi_timeframe_features(self):
        extractor = FeatureExtractor({
            "min_training_candles": 100,
            "include_timeframes": ["1h", "4h"],
        })
        names = extractor.get_feature_names()
        assert any("_1h_" in n for n in names)
        assert any("_4h_" in n for n in names)

    def test_feature_count(self):
        extractor = FeatureExtractor({
            "min_training_candles": 100,
            "include_timeframes": ["1h", "4h"],
            "indicator_periods": [10, 14, 20],
            "include_shifted_candles": 2,
            "include_corr_pairlist": ["BTC-USD", "ETH-USD"],
        })
        names = extractor.get_feature_names()
        # 7 base × 3 periods × 2 tf × 3 shifts + 4 fixed × 2 tf × 3 shifts + 4 corr
        expected = (7 * 3 + 4) * 2 * 3 + 4
        assert len(names) == expected


# ---------------------------------------------------------------------------
# Tests: Label computation (regression)
# ---------------------------------------------------------------------------

class TestLabels:
    def test_labels_length_matches_candles(self):
        candles = make_candles(n=100)
        extractor = FeatureExtractor({"min_training_candles": 100})
        labels = extractor.compute_labels(candles, horizon=24)
        assert len(labels) == len(candles)

    def test_last_candles_have_none_labels(self):
        candles = make_candles(n=100)
        extractor = FeatureExtractor({"min_training_candles": 100})
        labels = extractor.compute_labels(candles, horizon=24)
        for label in labels[-24:]:
            assert label is None

    def test_labels_are_floats(self):
        candles = make_candles(n=100)
        extractor = FeatureExtractor({"min_training_candles": 100})
        labels = extractor.compute_labels(candles, horizon=4)
        for label in labels:
            assert label is None or isinstance(label, float)


# ---------------------------------------------------------------------------
# Tests: Outlier detection
# ---------------------------------------------------------------------------

class TestOutlierDetector:
    def test_fit_and_detect(self):
        X_train = np.random.randn(200, 10)
        detector = OutlierDetector(di_threshold=1.0)
        detector.fit(X_train)
        di = detector.compute_di(X_train[:5])
        assert len(di) == 5
        assert all(v >= 0 for v in di)

    def test_do_predict_scale(self):
        det = OutlierDetector(di_threshold=1.0)
        assert det.get_do_predict(0.3) == 2
        assert det.get_do_predict(0.8) == 1
        assert det.get_do_predict(1.2) == 0
        assert det.get_do_predict(1.8) == -1
        assert det.get_do_predict(3.0) == -2


# ---------------------------------------------------------------------------
# Tests: Training
# ---------------------------------------------------------------------------

class TestTraining:
    def test_train_produces_model(self, predictor, candles):
        meta = predictor.train("TEST-USD", candles)
        assert meta is not None
        assert meta.pair == "TEST-USD"
        assert meta.version == 1
        assert meta.candle_count == len(candles)
        assert meta.validation_rmse >= 0

    def test_train_saves_model_files(self, predictor, candles, tmp_models_dir):
        predictor.train("TEST-USD", candles)
        assert os.path.exists(os.path.join(tmp_models_dir, "TEST_USD_latest_model.txt"))
        assert os.path.exists(os.path.join(tmp_models_dir, "TEST_USD_latest_meta.json"))
        assert os.path.exists(os.path.join(tmp_models_dir, "TEST_USD_latest_artifacts.pkl"))

    def test_train_insufficient_candles(self, tmp_models_dir):
        predictor = MLPredictor(
            config={"min_training_candles": 1000},
            models_dir=tmp_models_dir,
        )
        candles = make_candles(n=50)
        meta = predictor.train("SMALL-USD", candles)
        assert meta is None

    def test_version_increments(self, predictor, candles):
        meta1 = predictor.train("TEST-USD", candles)
        assert meta1.version == 1
        meta2 = predictor.train("TEST-USD", candles)
        assert meta2 is not None
        assert meta2.version == 2

    def test_feature_importance_populated(self, predictor, candles):
        meta = predictor.train("TEST-USD", candles)
        fn = predictor._extractor.get_feature_names()
        assert len(meta.feature_importance) == len(fn)

    def test_label_stats(self, predictor, candles):
        meta = predictor.train("TEST-USD", candles)
        assert isinstance(meta.label_mean, float)
        assert isinstance(meta.label_std, float)
        assert meta.label_std > 0


# ---------------------------------------------------------------------------
# Tests: Prediction
# ---------------------------------------------------------------------------

class TestPrediction:
    def test_prediction_fully_populated(self, predictor, candles):
        predictor.train("TEST-USD", candles)
        pred = predictor.predict("TEST-USD", candles)
        assert pred is not None
        assert isinstance(pred, MLPrediction)
        assert pred.pair == "TEST-USD"
        assert pred.direction in ("up", "down", "neutral")
        assert 0 <= pred.confidence <= 1
        assert isinstance(pred.predicted_change_pct, float)
        assert pred.do_predict in (-2, -1, 0, 1, 2)
        assert isinstance(pred.di_value, float)
        assert isinstance(pred.top_bullish_factors, list)
        assert isinstance(pred.top_bearish_factors, list)
        assert pred.recommended_action in ("buy full", "buy half", "skip", "sell full", "sell half")
        assert 0 <= pred.recommended_size_pct <= 1

    def test_prediction_without_model_returns_none(self, predictor, candles):
        pred = predictor.predict("NOMODEL-USD", candles)
        assert pred is None

    def test_contributions_finite(self, predictor, candles):
        predictor.train("TEST-USD", candles)
        pred = predictor.predict("TEST-USD", candles)
        assert pred is not None
        total = sum(pred.feature_contributions.values())
        assert not np.isnan(total)
        assert abs(total) < 1000


# ---------------------------------------------------------------------------
# Tests: Position sizing
# ---------------------------------------------------------------------------

class TestPositionSizing:
    def test_full_confidence_mapping(self):
        pred = MLPrediction(
            pair="X", timestamp=datetime.now(), direction="up",
            predicted_change_pct=2.0, confidence=0.85, do_predict=2, di_value=0.1,
            feature_values={}, feature_contributions={},
            top_bullish_factors=[], top_bearish_factors=[],
            recommended_action="buy full", recommended_size_pct=1.0,
        )
        predictor = MLPredictor()
        assert predictor.get_size_multiplier(pred) == 1.0

    def test_skip_returns_zero(self):
        pred = MLPrediction(
            pair="X", timestamp=datetime.now(), direction="neutral",
            predicted_change_pct=0.1, confidence=0.1, do_predict=0, di_value=0.5,
            feature_values={}, feature_contributions={},
            top_bullish_factors=[], top_bearish_factors=[],
            recommended_action="skip", recommended_size_pct=0.0,
        )
        predictor = MLPredictor()
        assert predictor.get_size_multiplier(pred) == 0.0

    def test_none_prediction_returns_full_size(self):
        predictor = MLPredictor()
        assert predictor.get_size_multiplier(None) == 1.0


# ---------------------------------------------------------------------------
# Tests: Model health & dynamic stoploss
# ---------------------------------------------------------------------------

class TestModelHealth:
    def test_no_model_health(self, predictor):
        health = predictor.check_model_health("FAKE-USD")
        assert health["status"] == "no_model"
        assert health["needs_retrain"] is True

    def test_healthy_model(self, predictor, candles):
        predictor.train("TEST-USD", candles)
        health = predictor.check_model_health("TEST-USD")
        assert health["status"] == "healthy"
        assert health["needs_retrain"] is False

    def test_dynamic_stoploss(self, predictor, candles):
        predictor.train("TEST-USD", candles)
        pred = predictor.predict("TEST-USD", candles)
        sl = predictor.get_dynamic_stoploss("TEST-USD", pred, hold_hours=6)
        assert "stoploss_pct" in sl
        assert "takeprofit_pct" in sl
        assert sl["stoploss_pct"] >= 0.5
        assert sl["takeprofit_pct"] >= 1.0


# ---------------------------------------------------------------------------
# Tests: Explanations
# ---------------------------------------------------------------------------

class TestExplanations:
    def test_rsi_oversold(self):
        result = _explain_feature("rsi_14_1h_s0", 28.0, 0.15)
        assert "oversold" in result.lower()

    def test_rsi_overbought(self):
        result = _explain_feature("rsi_14_1h_s0", 75.0, -0.10)
        assert "overbought" in result.lower()

    def test_volume_spike(self):
        result = _explain_feature("volume_ratio_14_1h_s0", 2.1, 0.12)
        assert "spike" in result.lower()

    def test_adx_trending(self):
        result = _explain_feature("adx_14_1h_s0", 30.0, -0.08)
        assert "trend" in result.lower()

    def test_momentum(self):
        result = _explain_feature("momentum_3_1h_s0", 0.025, 0.10)
        assert "momentum" in result.lower()


# ---------------------------------------------------------------------------
# Tests: Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_load_saved_model(self, predictor, candles, tmp_models_dir):
        predictor.train("TEST-USD", candles)

        predictor2 = MLPredictor(
            config={"min_training_candles": 100, "include_timeframes": ["1h"]},
            models_dir=tmp_models_dir,
        )
        pred = predictor2.predict("TEST-USD", candles)
        assert pred is not None

    def test_load_nonexistent_returns_none(self, predictor):
        model = predictor._load_model("FAKE-USD")
        assert model is None

    def test_model_info(self, predictor, candles):
        predictor.train("TEST-USD", candles)
        info = predictor.get_model_info("TEST-USD")
        assert info is not None
        assert info["pair"] == "TEST-USD"
        assert "validation_rmse" in info
        assert "validation_r2" in info
        assert "feature_importance" in info
        assert "model_health" in info

    def test_purge_old_models(self, predictor, candles, tmp_models_dir):
        # Train 4 versions
        for _ in range(4):
            predictor.train("TEST-USD", candles)
        # With purge_keep=2, only v3+v4 + latest should remain
        import glob
        versions = glob.glob(os.path.join(tmp_models_dir, "TEST_USD_v*_model.txt"))
        assert len(versions) <= 2


# ---------------------------------------------------------------------------
# Tests: Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_prediction_to_dict(self, predictor, candles):
        predictor.train("TEST-USD", candles)
        pred = predictor.predict("TEST-USD", candles)
        d = predictor.prediction_to_dict(pred)
        assert d["pair"] == "TEST-USD"
        assert "direction" in d
        assert "confidence" in d
        assert "predicted_change_pct" in d
        assert "do_predict" in d
        assert "di_value" in d
        assert "recommended_action" in d


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_config_loader_missing_file(self):
        config = load_ml_config("nonexistent.yaml")
        assert config == {}

    def test_predict_at_specific_index(self, predictor, candles):
        predictor.train("TEST-USD", candles)
        pred = predictor.predict("TEST-USD", candles, index=450)
        assert pred is not None
        assert pred.timestamp == candles[450].timestamp

    def test_predict_early_index_returns_none(self, predictor, candles):
        predictor.train("TEST-USD", candles)
        pred = predictor.predict("TEST-USD", candles, index=5)
        assert pred is None

    def test_lookahead_bias_check(self):
        extractor = FeatureExtractor({"min_training_candles": 100, "include_timeframes": ["1h"]})
        candles = make_candles(n=300)
        names = extractor.get_feature_names()
        suspicious = extractor.check_lookahead_bias(names, candles)
        assert len(suspicious) == 0, f"Lookahead bias detected: {suspicious}"
