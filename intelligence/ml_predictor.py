"""ML prediction layer — LightGBM regression (FreqAI-inspired).

Complete overhaul from binary classification to regression with:
- Multi-timeframe, multi-period feature expansion (~150+ features)
- Shifted candle features for temporal context
- Dissimilarity Index (DI) outlier detection via OneClassSVM
- Sliding window retraining with exponential recency weighting
- MinMaxScaler normalization, Gaussian noise injection
- Model expiration, versioning, and automatic purging
- Dynamic stoploss/take-profit based on ML confidence
- Optuna Bayesian hyperparameter optimization
- do_predict confidence gating (-2 to 2 scale)
"""

import json
import logging
import os
import pickle
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import lightgbm as lgb
import yaml
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from sklearn.svm import OneClassSVM

from exchange.models import Candle

logger = logging.getLogger(__name__)

# Timeframe → minutes for resampling from 1h base
TIMEFRAME_MINUTES = {"15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def load_ml_config(path: str = "config/ml_config.yaml") -> dict:
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MLPrediction:
    pair: str
    timestamp: datetime
    direction: str                    # "up", "down", "neutral"
    predicted_change_pct: float       # raw regression output (% price change)
    confidence: float                 # 0.0–1.0
    do_predict: int                   # -2 to 2 (DI confidence gate)
    di_value: float                   # raw dissimilarity index
    feature_values: dict
    feature_contributions: dict
    top_bullish_factors: list
    top_bearish_factors: list
    recommended_action: str           # "buy full", "buy half", "skip", "sell full", "sell half"
    recommended_size_pct: float       # 0.0–1.0


@dataclass
class ModelMetadata:
    pair: str
    trained_at: datetime
    candle_count: int
    validation_rmse: float
    validation_r2: float
    version: int
    feature_names: list
    feature_importance: dict
    train_window_start: datetime
    train_window_end: datetime
    label_mean: float
    label_std: float
    pred_mean: float = 0.0   # model's prediction mean (for calibrated thresholds)
    pred_std: float = 1.0    # model's prediction std (for calibrated thresholds)


@dataclass
class TrainingArtifacts:
    """Saved alongside model for DI detection and normalization."""
    scaler: MinMaxScaler
    svm_model: OneClassSVM | None
    feature_names: list[str]
    label_mean: float
    label_std: float
    training_features_sample: np.ndarray | None
    pred_mean: float = 0.0
    pred_std: float = 1.0


# ---------------------------------------------------------------------------
# Feature extraction (multi-period, multi-timeframe, shifted)
# ---------------------------------------------------------------------------

class FeatureExtractor:
    """Expands indicators across periods, timeframes, and shifts."""

    BASE_INDICATORS = [
        "rsi", "adx", "bb_width", "volume_ratio",
        "obv_slope", "atr_pct", "ema_distance",
    ]
    FIXED_INDICATORS = ["candle_strength", "momentum_1", "momentum_3", "momentum_5"]

    def __init__(self, config: dict):
        self.periods = config.get("indicator_periods", [10, 14, 20])
        self.timeframes = config.get("include_timeframes", ["1h", "4h"])
        self.shifts = list(range(config.get("include_shifted_candles", 2) + 1))
        self.corr_pairs = config.get("include_corr_pairlist", [])
        self.min_candles = int(config.get("min_training_candles", 400))

    def get_feature_names(self) -> list[str]:
        """Ordered list of all feature names produced by extract_features."""
        names = []
        for tf in self.timeframes:
            for shift in self.shifts:
                for indicator in self.BASE_INDICATORS:
                    for period in self.periods:
                        names.append(f"{indicator}_{period}_{tf}_s{shift}")
                for indicator in self.FIXED_INDICATORS:
                    names.append(f"{indicator}_{tf}_s{shift}")
        for cp in self.corr_pairs:
            safe = cp.replace("-", "_")
            names.append(f"corr_{safe}_returns")
            names.append(f"corr_{safe}_price_ratio")
        return names

    def extract_features(
        self,
        candles: list[Candle],
        index: int,
        corr_candles: dict[str, list[Candle]] | None = None,
    ) -> dict | None:
        """Extract all expanded features for the candle at *index*."""
        if index < self.min_candles:
            return None

        features: dict[str, float] = {}

        for tf in self.timeframes:
            tf_candles = self._resample(candles[: index + 1], tf)
            if len(tf_candles) < max(self.periods) + 10:
                return None

            for shift in self.shifts:
                eff = len(tf_candles) - 1 - shift
                if eff < max(self.periods) + 10:
                    return None

                window = tf_candles[: eff + 1]
                closes = [c.close for c in window]
                highs = [c.high for c in window]
                lows = [c.low for c in window]
                volumes = [c.volume for c in window]
                sfx = f"_{tf}_s{shift}"

                for period in self.periods:
                    ps = f"_{period}{sfx}"
                    features[f"rsi{ps}"] = _calc_rsi(closes, period)
                    features[f"adx{ps}"] = _calc_adx(highs, lows, closes, period)
                    features[f"bb_width{ps}"] = _calc_bb_width(closes, period)
                    features[f"volume_ratio{ps}"] = _calc_volume_ratio(volumes, period)
                    features[f"obv_slope{ps}"] = _calc_obv_slope(closes, volumes, period)
                    features[f"atr_pct{ps}"] = _calc_atr_pct(highs, lows, closes, period)
                    features[f"ema_distance{ps}"] = _calc_ema_distance(closes, period)

                c = tf_candles[eff]
                hl = c.high - c.low
                features[f"candle_strength{sfx}"] = abs(c.close - c.open) / hl if hl > 0 else 0.0
                features[f"momentum_1{sfx}"] = (
                    (closes[-1] - closes[-2]) / closes[-2]
                    if len(closes) >= 2 and closes[-2] > 0 else 0.0
                )
                features[f"momentum_3{sfx}"] = (
                    (closes[-1] - closes[-4]) / closes[-4]
                    if len(closes) >= 4 and closes[-4] > 0 else 0.0
                )
                features[f"momentum_5{sfx}"] = (
                    (closes[-1] - closes[-6]) / closes[-6]
                    if len(closes) >= 6 and closes[-6] > 0 else 0.0
                )

        # Correlated-pair features
        if corr_candles:
            main_closes = [c.close for c in candles[max(0, index - 20) : index + 1]]
            for cp in self.corr_pairs:
                safe = cp.replace("-", "_")
                cp_data = corr_candles.get(cp, [])
                if cp_data and len(cp_data) > 20 and len(main_closes) >= 2:
                    cp_closes = [c.close for c in cp_data[-len(main_closes) :]]
                    main_ret = [
                        (main_closes[i] - main_closes[i - 1]) / main_closes[i - 1]
                        for i in range(1, len(main_closes))
                        if main_closes[i - 1] > 0
                    ]
                    cp_ret = [
                        (cp_closes[i] - cp_closes[i - 1]) / cp_closes[i - 1]
                        for i in range(1, min(len(cp_closes), len(main_closes)))
                        if cp_closes[i - 1] > 0
                    ]
                    n = min(len(main_ret), len(cp_ret))
                    if n > 5:
                        features[f"corr_{safe}_returns"] = float(
                            np.corrcoef(main_ret[-n:], cp_ret[-n:])[0, 1]
                        )
                    else:
                        features[f"corr_{safe}_returns"] = 0.0
                    features[f"corr_{safe}_price_ratio"] = (
                        main_closes[-1] / cp_closes[-1] if cp_closes[-1] > 0 else 0.0
                    )
                else:
                    features[f"corr_{safe}_returns"] = 0.0
                    features[f"corr_{safe}_price_ratio"] = 0.0

        # Sanitise NaN / None
        for k, v in features.items():
            if v is None or (isinstance(v, float) and np.isnan(v)):
                features[k] = 0.0

        return features

    def compute_labels(self, candles: list[Candle], horizon: int = 24) -> list[float | None]:
        """Regression labels: % price change over next *horizon* candles."""
        labels: list[float | None] = []
        for i in range(len(candles)):
            if i + horizon >= len(candles):
                labels.append(None)
                continue
            if candles[i].close > 0:
                labels.append(
                    (candles[i + horizon].close - candles[i].close)
                    / candles[i].close
                    * 100
                )
            else:
                labels.append(None)
        return labels

    def check_lookahead_bias(self, feature_names: list[str], candles: list[Candle]) -> list[str]:
        """Fix 17: check that features at index *i* don't change when future candles are removed."""
        suspicious: list[str] = []
        if len(candles) < self.min_candles + 10:
            return suspicious
        idx = self.min_candles + 5
        feat_full = self.extract_features(candles, idx)
        feat_trim = self.extract_features(candles[: idx + 1], idx)
        if feat_full and feat_trim:
            for name in feature_names:
                if abs(feat_full.get(name, 0) - feat_trim.get(name, 0)) > 1e-10:
                    suspicious.append(name)
        return suspicious

    # --- Timeframe resampling ---

    @staticmethod
    def _resample(candles: list[Candle], timeframe: str) -> list[Candle]:
        tf_min = TIMEFRAME_MINUTES.get(timeframe, 60)
        base_min = 60  # 1h base
        if tf_min <= base_min:
            return candles
        ratio = tf_min // base_min
        out: list[Candle] = []
        for i in range(0, len(candles) - ratio + 1, ratio):
            chunk = candles[i : i + ratio]
            out.append(
                Candle(
                    pair=chunk[0].pair,
                    granularity=timeframe,
                    timestamp=chunk[0].timestamp,
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=sum(c.volume for c in chunk),
                )
            )
        return out


# ---------------------------------------------------------------------------
# Indicator calculations (module-level for picklability & reuse)
# ---------------------------------------------------------------------------

def _calc_rsi(closes: list[float], period: int) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(len(closes) - period, len(closes))]
    gains = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _calc_adx(highs, lows, closes, period) -> float:
    if len(closes) < period * 2:
        return 25.0
    tr_l, pdm, mdm = [], [], []
    for i in range(1, len(closes)):
        tr_l.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
        up = highs[i] - highs[i - 1]
        dn = lows[i - 1] - lows[i]
        pdm.append(up if up > dn and up > 0 else 0)
        mdm.append(dn if dn > up and dn > 0 else 0)
    if len(tr_l) < period:
        return 25.0
    atr = sum(tr_l[-period:]) / period
    if atr <= 0:
        return 0.0
    pdi = (sum(pdm[-period:]) / period) / atr * 100
    mdi = (sum(mdm[-period:]) / period) / atr * 100
    s = pdi + mdi
    return abs(pdi - mdi) / s * 100 if s > 0 else 0.0


def _calc_bb_width(closes, period) -> float:
    if len(closes) < period:
        return 0.0
    rec = closes[-period:]
    mean = sum(rec) / period
    std = (sum((x - mean) ** 2 for x in rec) / period) ** 0.5
    return (4 * std / mean) * 100 if mean > 0 else 0.0


def _calc_volume_ratio(volumes, period) -> float:
    if len(volumes) < period:
        return 1.0
    avg = sum(volumes[-period:]) / period
    return volumes[-1] / avg if avg > 0 else 1.0


def _calc_obv_slope(closes, volumes, lookback) -> float:
    if len(closes) < lookback + 1:
        return 0.0
    obv = [0.0]
    start = len(closes) - lookback - 1
    for i in range(start + 1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    n = len(obv)
    if n < 2:
        return 0.0
    xm = (n - 1) / 2
    ym = sum(obv) / n
    num = sum((i - xm) * (obv[i] - ym) for i in range(n))
    den = sum((i - xm) ** 2 for i in range(n))
    slope = num / den if den > 0 else 0
    avg_vol = sum(volumes[-lookback:]) / lookback if lookback > 0 else 1
    return slope / avg_vol if avg_vol > 0 else 0.0


def _calc_atr_pct(highs, lows, closes, period) -> float:
    if len(closes) < period + 1:
        return 0.0
    tr = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(1, len(closes))
    ]
    if len(tr) < period:
        return 0.0
    atr = sum(tr[-period:]) / period
    return atr / closes[-1] * 100 if closes[-1] > 0 else 0.0


def _calc_ema_distance(closes, period) -> float:
    if len(closes) < period:
        return 0.0
    mult = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for v in closes[period:]:
        ema = (v - ema) * mult + ema
    return (closes[-1] - ema) / ema * 100 if ema > 0 else 0.0


# ---------------------------------------------------------------------------
# Outlier detection — Dissimilarity Index via OneClassSVM  (Fix 4)
# ---------------------------------------------------------------------------

class OutlierDetector:
    def __init__(self, di_threshold: float = 1.0):
        self.di_threshold = di_threshold
        self.svm: OneClassSVM | None = None

    def fit(self, X_train: np.ndarray) -> None:
        # Sub-sample for speed
        if len(X_train) > 2000:
            idx = np.random.choice(len(X_train), 2000, replace=False)
            X_sub = X_train[idx]
        else:
            X_sub = X_train
        self.svm = OneClassSVM(kernel="rbf", gamma="scale", nu=0.1)
        self.svm.fit(X_sub)

    def compute_di(self, X: np.ndarray) -> np.ndarray:
        if self.svm is None:
            return np.zeros(len(X))
        return np.clip(-self.svm.decision_function(X), 0, None)

    def get_do_predict(self, di_value: float) -> int:
        """Map DI → do_predict on a -2…2 scale."""
        if di_value < self.di_threshold * 0.5:
            return 2
        if di_value < self.di_threshold:
            return 1
        if di_value < self.di_threshold * 1.5:
            return 0
        if di_value < self.di_threshold * 2.0:
            return -1
        return -2


# ---------------------------------------------------------------------------
# Human-readable feature explanations
# ---------------------------------------------------------------------------

def _explain_feature(name: str, value: float, contribution: float) -> str:
    direction = "bullish" if contribution > 0 else "bearish"
    if "rsi" in name:
        if value < 35:
            return f"RSI oversold at {value:.0f} ({direction})"
        if value > 65:
            return f"RSI overbought at {value:.0f} ({direction})"
        return f"RSI neutral at {value:.0f}"
    if "adx" in name:
        return f"ADX {value:.0f} ({'strong trend' if value > 25 else 'range-bound'})"
    if "bb_width" in name:
        return f"BB width {value:.1f}% ({'squeeze' if value < 3 else 'wide' if value > 8 else 'normal'})"
    if "volume_ratio" in name:
        return f"Volume {'spike' if value > 1.5 else 'low' if value < 0.7 else 'normal'} {value:.1f}x"
    if "momentum" in name:
        return f"{name} {value:+.2%}"
    return f"{name}={value:.3f} ({contribution:+.3f})"


# ---------------------------------------------------------------------------
# ML Predictor
# ---------------------------------------------------------------------------

class MLPredictor:
    def __init__(self, config: dict | None = None, models_dir: str = "models"):
        config = config or {}
        self.config = config
        self.models_dir = models_dir

        # Training
        self.train_period_days = int(config.get("train_period_days", 30))
        self.min_training_candles = int(config.get("min_training_candles", 400))
        self.validation_split = float(config.get("validation_split", 0.2))
        self.label_horizon = int(config.get("label_period_candles", 24))
        self.dynamic_threshold = bool(config.get("dynamic_threshold", True))
        self.reverse_train_test = bool(config.get("reverse_train_test_order", True))

        # Regularisation
        self.noise_std = float(config.get("noise_standard_deviation", 0.05))
        self.weight_factor = float(config.get("weight_factor", 0.1))

        # Outlier detection
        self.di_threshold = float(config.get("DI_threshold", 1.0))
        self.outlier_protection_pct = float(config.get("outlier_protection_pct", 0.30))

        # Prediction calibration
        self.fit_live_candles = int(config.get("fit_live_predictions_candles", 100))

        # Model management
        self.expiration_hours = int(config.get("expiration_hours", 48))
        self.purge_keep = int(config.get("purge_old_models", 2))
        self.continual_learning = bool(config.get("continual_learning", False))

        # Confidence → sizing
        self.conf_strong = float(config.get("size_full_threshold", 0.65))
        self.conf_weak = float(config.get("size_half_threshold", 0.40))

        # Dynamic stoploss
        self.stoploss_config = config.get("dynamic_stoploss", {})

        # LightGBM
        lgb_cfg = config.get("lgb_params", {})
        self.lgb_params = {
            "objective": "regression",
            "metric": "rmse",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "min_child_samples": 20,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
            **lgb_cfg,
        }
        self.n_estimators = int(self.lgb_params.pop("n_estimators", 300))

        # Feature extractor
        self._extractor = FeatureExtractor(config)
        self._feature_names = self._extractor.get_feature_names()

        # Per-pair runtime state
        self._models: dict[str, lgb.Booster] = {}
        self._metadata: dict[str, ModelMetadata] = {}
        self._artifacts: dict[str, TrainingArtifacts] = {}
        self._live_predictions: dict[str, list[float]] = {}
        self._retrain_lock = threading.Lock()

        # Backward compat: expose prediction_horizon for outcome tracking
        self.prediction_horizon = self.label_horizon

        os.makedirs(models_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        pair: str,
        candles: list[Candle],
        corr_candles: dict[str, list[Candle]] | None = None,
    ) -> ModelMetadata | None:
        """Train a LightGBM regression model for *pair*."""
        if len(candles) < self.min_training_candles:
            logger.warning(
                "Insufficient candles for %s: %d < %d", pair, len(candles), self.min_training_candles
            )
            return None

        # Fix 17: lookahead check (log-only, non-blocking)
        suspicious = self._extractor.check_lookahead_bias(self._feature_names, candles)
        if suspicious:
            logger.warning("Possible lookahead bias in features: %s", suspicious[:5])

        # Build samples
        labels = self._extractor.compute_labels(candles, self.label_horizon)
        feature_names = self._extractor.get_feature_names()
        rows_X: list[list[float]] = []
        rows_y: list[float] = []

        for i in range(len(candles)):
            if labels[i] is None:
                continue
            feat = self._extractor.extract_features(candles, i, corr_candles)
            if feat is None:
                continue
            rows_X.append([feat.get(n, 0.0) for n in feature_names])
            rows_y.append(labels[i])

        if len(rows_X) < 100:
            logger.warning("Too few valid samples for %s: %d", pair, len(rows_X))
            return None

        X = np.array(rows_X)
        y = np.array(rows_y)

        # Fix 15: reverse train/test — train on recent, validate on older data
        split_n = max(1, int(len(X) * self.validation_split))
        if self.reverse_train_test:
            X_val, X_train = X[:split_n], X[split_n:]
            y_val, y_train = y[:split_n], y[split_n:]
        else:
            X_train, X_val = X[:-split_n], X[-split_n:]
            y_train, y_val = y[:-split_n], y[-split_n:]

        # Fix 7: MinMaxScaler to [-1, 1]
        scaler = MinMaxScaler(feature_range=(-1, 1))
        X_train_s = scaler.fit_transform(X_train)
        X_val_s = scaler.transform(X_val) if len(X_val) > 0 else np.empty((0, X_train.shape[1]))

        # Fix 9: Gaussian noise injection
        if self.noise_std > 0:
            X_train_noisy = X_train_s + np.random.normal(0, self.noise_std, X_train_s.shape)
        else:
            X_train_noisy = X_train_s

        # Fix 6: exponential recency weighting
        n = len(X_train_noisy)
        weights = np.exp(-self.weight_factor * np.arange(n)[::-1] / n)
        weights = weights / weights.sum() * n

        # Fix 4: train SVM outlier detector
        outlier_det = OutlierDetector(self.di_threshold)
        try:
            outlier_det.fit(X_train_s)
        except Exception as e:
            logger.warning("SVM outlier detector training failed: %s", e)
            outlier_det.svm = None

        # Fix 22: continual learning (warm-start)
        init_model = None
        if self.continual_learning and pair in self._models:
            tmp = os.path.join(self.models_dir, f"_tmp_{pair.replace('-', '_')}.txt")
            self._models[pair].save_model(tmp)
            init_model = tmp

        train_ds = lgb.Dataset(X_train_noisy, label=y_train, weight=weights, feature_name=feature_names)
        model = lgb.train(
            self.lgb_params,
            train_ds,
            num_boost_round=self.n_estimators,
            init_model=init_model,
            callbacks=[lgb.log_evaluation(period=0)],
        )

        if init_model and os.path.exists(init_model):
            os.remove(init_model)

        # Evaluate
        rmse, r2 = 0.0, 0.0
        if len(X_val_s) > 0:
            preds = model.predict(X_val_s)
            rmse = float(np.sqrt(mean_squared_error(y_val, preds)))
            ss_res = float(np.sum((y_val - preds) ** 2))
            ss_tot = float(np.sum((y_val - np.mean(y_val)) ** 2))
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        importance = dict(zip(feature_names, model.feature_importance(importance_type="gain").tolist()))
        label_mean, label_std = float(np.mean(y_train)), float(np.std(y_train))

        # Compute model's prediction distribution for calibrated thresholds
        train_preds = model.predict(X_train_s)
        pred_mean = float(np.mean(train_preds))
        pred_std = max(float(np.std(train_preds)), 0.01)  # floor to prevent div-by-zero

        old_meta = self._metadata.get(pair)
        version = (old_meta.version + 1) if old_meta else 1

        metadata = ModelMetadata(
            pair=pair,
            trained_at=datetime.now(),
            candle_count=len(candles),
            validation_rmse=rmse,
            validation_r2=r2,
            version=version,
            feature_names=feature_names,
            feature_importance=importance,
            train_window_start=candles[0].timestamp,
            train_window_end=candles[-1].timestamp,
            label_mean=label_mean,
            label_std=label_std,
            pred_mean=pred_mean,
            pred_std=pred_std,
        )

        artifacts = TrainingArtifacts(
            scaler=scaler,
            svm_model=outlier_det.svm,
            feature_names=feature_names,
            label_mean=label_mean,
            label_std=label_std,
            training_features_sample=X_train_s[:500] if len(X_train_s) > 0 else None,
            pred_mean=pred_mean,
            pred_std=pred_std,
        )

        self._models[pair] = model
        self._metadata[pair] = metadata
        self._artifacts[pair] = artifacts
        self._save_model(pair, model, metadata, artifacts)
        self._purge_old_models(pair)

        logger.info(
            "Trained regression model for %s: RMSE=%.4f  R²=%.3f  pred_std=%.3f  features=%d  v%d",
            pair, rmse, r2, pred_std, len(feature_names), version,
        )
        return metadata

    def retrain_if_needed(
        self, pair: str, candles: list[Candle], corr_candles: dict | None = None,
    ) -> bool:
        """Retrain when model is missing or expired (Fix 13)."""
        meta = self._metadata.get(pair)
        if meta is None:
            if self._load_model(pair):
                meta = self._metadata.get(pair)

        if meta is None:
            return self.train(pair, candles, corr_candles) is not None

        elapsed = datetime.now() - meta.trained_at
        if elapsed < timedelta(hours=self.expiration_hours):
            return False

        logger.info("Model for %s expired (%.1fh), retraining…", pair, elapsed.total_seconds() / 3600)
        return self.train(pair, candles, corr_candles) is not None

    def retrain_in_background(
        self, pair: str, candles: list[Candle], corr_candles: dict | None = None,
    ) -> None:
        def _work():
            with self._retrain_lock:
                self.retrain_if_needed(pair, candles, corr_candles)

        threading.Thread(target=_work, daemon=True).start()

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        pair: str,
        candles: list[Candle],
        index: int = -1,
        corr_candles: dict[str, list[Candle]] | None = None,
    ) -> MLPrediction | None:
        """Generate a regression prediction with DI gating."""
        if index < 0:
            index = len(candles) - 1

        model = self._models.get(pair)
        if model is None:
            model = self._load_model(pair)
            if model is None:
                return None

        artifacts = self._artifacts.get(pair)
        meta = self._metadata.get(pair)
        if artifacts is None or meta is None:
            return None

        features = self._extractor.extract_features(candles, index, corr_candles)
        if features is None:
            return None

        fn = artifacts.feature_names
        X_raw = np.array([[features.get(n, 0.0) for n in fn]])
        X_scaled = artifacts.scaler.transform(X_raw)

        # Fix 4/10: DI gating
        di_value = 0.0
        do_predict = 2
        if artifacts.svm_model is not None:
            det = OutlierDetector(self.di_threshold)
            det.svm = artifacts.svm_model
            di_value = float(det.compute_di(X_scaled)[0])
            do_predict = det.get_do_predict(di_value)

        # Regression prediction (% change)
        raw_pred = float(model.predict(X_scaled)[0])

        # Fix 11: rolling calibration buffer
        buf = self._live_predictions.setdefault(pair, [])
        buf.append(raw_pred)
        if len(buf) > self.fit_live_candles:
            self._live_predictions[pair] = buf[-self.fit_live_candles :]

        # Fix 5: calibrated threshold from model's own prediction distribution
        # Use pred_std (what the model actually outputs) not label_std (raw target spread)
        p_std = getattr(meta, 'pred_std', None) or (meta.label_std * 0.3)
        threshold = p_std * 0.5 if (self.dynamic_threshold and p_std > 0) else 0.5

        # Direction
        if raw_pred > threshold:
            direction = "up"
        elif raw_pred < -threshold:
            direction = "down"
        else:
            direction = "neutral"

        # Confidence: how many pred_stds away from zero (capped at 1.0)
        confidence = min(abs(raw_pred) / p_std, 1.0) if p_std > 0 else 0.5

        # Gate unreliable predictions
        if do_predict <= -1:
            direction = "neutral"
            confidence *= 0.3

        # Feature contributions (SHAP-style leaf values)
        contributions: dict[str, float] = {}
        try:
            raw_c = model.predict(X_scaled, pred_contrib=True)[0]
            contributions = dict(zip(fn, raw_c[:-1].tolist()))
        except Exception:
            pass

        sorted_c = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
        top_bull = [
            _explain_feature(n, features.get(n, 0), v) for n, v in sorted_c if v > 0.001
        ][:5]
        top_bear = [
            _explain_feature(n, features.get(n, 0), v) for n, v in sorted_c if v < -0.001
        ][:5]

        # Action / sizing
        if direction == "up" and confidence >= self.conf_strong:
            action, size = "buy full", 1.0
        elif direction == "up" and confidence >= self.conf_weak:
            action, size = "buy half", 0.5
        elif direction == "down" and confidence >= self.conf_strong:
            action, size = "sell full", 0.0
        elif direction == "down" and confidence >= self.conf_weak:
            action, size = "sell half", 0.25
        else:
            action, size = "skip", 0.0

        return MLPrediction(
            pair=pair,
            timestamp=candles[index].timestamp,
            direction=direction,
            predicted_change_pct=raw_pred,
            confidence=confidence,
            do_predict=do_predict,
            di_value=di_value,
            feature_values={k: features.get(k, 0) for k in fn[:20]},
            feature_contributions=contributions,
            top_bullish_factors=top_bull,
            top_bearish_factors=top_bear,
            recommended_action=action,
            recommended_size_pct=size,
        )

    def get_size_multiplier(self, prediction: MLPrediction | None) -> float:
        if prediction is None:
            return 1.0
        return prediction.recommended_size_pct

    # ------------------------------------------------------------------
    # Fix 25: dynamic stoploss / take-profit
    # ------------------------------------------------------------------

    def get_dynamic_stoploss(
        self, pair: str, prediction: MLPrediction | None, hold_hours: float = 0,
    ) -> dict:
        cfg = self.stoploss_config
        if not cfg.get("enabled", False):
            return {"stoploss_pct": 3.0, "takeprofit_pct": 6.0, "trailing": False}

        base_sl = float(cfg.get("initial_pct", 3.0))
        trailing = bool(cfg.get("trailing", True))
        time_decay_h = float(cfg.get("time_decay_hours", 24))
        conf_decay = bool(cfg.get("confidence_decay", True))

        sl = base_sl

        # Time decay: tighten as position ages
        if time_decay_h > 0 and hold_hours > 0:
            sl *= max(0.3, 1.0 - (hold_hours / time_decay_h) * 0.5)

        # Confidence decay
        if conf_decay and prediction is not None:
            sl *= 0.5 + prediction.confidence * 0.5

        tp = sl * 2
        if prediction and prediction.predicted_change_pct > 0:
            tp = max(tp, abs(prediction.predicted_change_pct) * 0.8)

        return {
            "stoploss_pct": round(max(sl, 0.5), 2),
            "takeprofit_pct": round(max(tp, 1.0), 2),
            "trailing": trailing,
        }

    # ------------------------------------------------------------------
    # Fix 24: Optuna hyperparameter optimisation
    # ------------------------------------------------------------------

    def hyperopt(
        self,
        pair: str,
        candles: list[Candle],
        n_trials: int = 50,
        timeout: int = 300,
    ) -> dict:
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)

        labels = self._extractor.compute_labels(candles, self.label_horizon)
        fn = self._extractor.get_feature_names()
        rows_X, rows_y = [], []
        for i in range(len(candles)):
            if labels[i] is None:
                continue
            feat = self._extractor.extract_features(candles, i)
            if feat is None:
                continue
            rows_X.append([feat.get(n, 0.0) for n in fn])
            rows_y.append(labels[i])

        if len(rows_X) < 200:
            logger.warning("Too few samples for hyperopt: %d", len(rows_X))
            return {"lgb_params": self.lgb_params, "n_estimators": self.n_estimators}

        X, y = np.array(rows_X), np.array(rows_y)
        split = max(1, int(len(X) * 0.2))
        X_val, X_tr = X[:split], X[split:]
        y_val, y_tr = y[:split], y[split:]

        scaler = MinMaxScaler(feature_range=(-1, 1))
        X_tr_s = scaler.fit_transform(X_tr)
        X_val_s = scaler.transform(X_val)

        def objective(trial):
            params = {
                "objective": "regression", "metric": "rmse", "verbose": -1,
                "num_leaves": trial.suggest_int("num_leaves", 15, 63),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
                "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 0.95),
                "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 0.95),
                "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 1.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 1.0, log=True),
            }
            nr = trial.suggest_int("n_estimators", 100, 500)
            ds = lgb.Dataset(X_tr_s, label=y_tr, feature_name=fn)
            m = lgb.train(params, ds, num_boost_round=nr, callbacks=[lgb.log_evaluation(period=0)])
            return float(np.sqrt(mean_squared_error(y_val, m.predict(X_val_s))))

        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=n_trials, timeout=timeout)

        best = study.best_params
        best_n = best.pop("n_estimators", 300)
        logger.info("Hyperopt for %s: best RMSE=%.4f, params=%s", pair, study.best_value, best)
        return {"lgb_params": {**self.lgb_params, **best}, "n_estimators": best_n, "best_rmse": study.best_value}

    # ------------------------------------------------------------------
    # Auto-tune: grid-search over horizons, windows, and thresholds
    # ------------------------------------------------------------------

    def auto_tune(
        self,
        pair: str,
        candles: list[Candle],
        horizons: list[int] | None = None,
        train_windows_days: list[int] | None = None,
        conf_thresholds: list[float] | None = None,
        n_estimators_list: list[int] | None = None,
    ) -> dict:
        """Grid-search over prediction horizons, training windows, confidence
        thresholds, and n_estimators. Returns the best config (by validation R²)
        and saves it to config/ml_tuned/<pair>.yaml.

        This is a one-time calibration that runs before trading starts.
        """
        if horizons is None:
            horizons = [4, 6, 8, 12, 24]
        if train_windows_days is None:
            train_windows_days = [30, 60, 90, 120]
        if conf_thresholds is None:
            conf_thresholds = [0.3, 0.4, 0.5, 0.6]
        if n_estimators_list is None:
            n_estimators_list = [100, 200, 400]

        fn = self._extractor.get_feature_names()
        best_r2 = -999.0
        best_config: dict = {}
        results: list[dict] = []

        total = len(horizons) * len(train_windows_days) * len(n_estimators_list)
        trial = 0

        for horizon in horizons:
            # Compute labels for this horizon
            labels = self._extractor.compute_labels(candles, horizon)

            for window_days in train_windows_days:
                window_candles = window_days * 24

                if window_candles + 200 > len(candles):
                    trial += len(n_estimators_list)
                    continue

                # Build feature matrix once per (horizon, window) pair
                train_end = min(window_candles, len(candles))
                rows_X, rows_y = [], []
                for i in range(len(candles[:train_end])):
                    if labels[i] is None:
                        continue
                    feat = self._extractor.extract_features(candles[:train_end], i)
                    if feat is None:
                        continue
                    rows_X.append([feat.get(n, 0.0) for n in fn])
                    rows_y.append(labels[i])

                if len(rows_X) < 200:
                    trial += len(n_estimators_list)
                    continue

                X = np.array(rows_X)
                y = np.array(rows_y)

                # Split: train on recent, validate on older (reverse)
                split_n = max(1, int(len(X) * 0.2))
                X_val, X_train = X[:split_n], X[split_n:]
                y_val, y_train = y[:split_n], y[split_n:]

                scaler = MinMaxScaler(feature_range=(-1, 1))
                X_train_s = scaler.fit_transform(X_train)
                X_val_s = scaler.transform(X_val)

                # Add noise
                if self.noise_std > 0:
                    X_train_noisy = X_train_s + np.random.normal(0, self.noise_std, X_train_s.shape)
                else:
                    X_train_noisy = X_train_s

                # Recency weighting
                n_tr = len(X_train_noisy)
                weights = np.exp(-self.weight_factor * np.arange(n_tr)[::-1] / n_tr)
                weights = weights / weights.sum() * n_tr

                for n_est in n_estimators_list:
                    trial += 1
                    ds = lgb.Dataset(X_train_noisy, label=y_train, weight=weights, feature_name=fn)
                    model = lgb.train(
                        self.lgb_params, ds,
                        num_boost_round=n_est,
                        callbacks=[lgb.log_evaluation(period=0)],
                    )

                    preds = model.predict(X_val_s)
                    rmse = float(np.sqrt(mean_squared_error(y_val, preds)))
                    ss_res = float(np.sum((y_val - preds) ** 2))
                    ss_tot = float(np.sum((y_val - np.mean(y_val)) ** 2))
                    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

                    train_preds = model.predict(X_train_s)
                    pred_std = max(float(np.std(train_preds)), 0.01)

                    for conf_thresh in conf_thresholds:
                        result_row = {
                            "horizon": horizon,
                            "window_days": window_days,
                            "n_estimators": n_est,
                            "conf_threshold": conf_thresh,
                            "rmse": rmse,
                            "r2": r2,
                            "pred_std": pred_std,
                            "samples": len(rows_X),
                        }
                        results.append(result_row)

                        if r2 > best_r2:
                            best_r2 = r2
                            best_config = {
                                "label_period_candles": horizon,
                                "train_period_days": window_days,
                                "n_estimators": n_est,
                                "size_half_threshold": conf_thresh,
                                "size_full_threshold": min(conf_thresh + 0.15, 0.95),
                                "r2": r2,
                                "rmse": rmse,
                                "pred_std": pred_std,
                            }

                    print(f"  [{trial}/{total}] horizon={horizon}h window={window_days}d "
                          f"n_est={n_est} => R2={r2:.4f}  RMSE={rmse:.4f}  "
                          f"pred_std={pred_std:.3f}  samples={len(rows_X)}")

        if not best_config:
            logger.warning("Auto-tune failed: no valid configs found for %s", pair)
            return {"error": "no valid configs"}

        # Save best config per pair
        tuned_dir = os.path.join("config", "ml_tuned")
        os.makedirs(tuned_dir, exist_ok=True)
        safe = pair.replace("-", "_").lower()
        tuned_path = os.path.join(tuned_dir, f"{safe}.yaml")

        tuned_data = {
            "pair": pair,
            "label_period_candles": best_config["label_period_candles"],
            "train_period_days": best_config["train_period_days"],
            "n_estimators": best_config["n_estimators"],
            "size_half_threshold": best_config["size_half_threshold"],
            "size_full_threshold": best_config["size_full_threshold"],
            "best_r2": best_config["r2"],
            "best_rmse": best_config["rmse"],
            "pred_std": best_config["pred_std"],
        }
        with open(tuned_path, "w") as f:
            yaml.dump(tuned_data, f, default_flow_style=False)

        logger.info("Auto-tune for %s: best R2=%.4f (horizon=%dh, window=%dd, n_est=%d, conf=%.2f) saved to %s",
                     pair, best_r2, best_config["label_period_candles"],
                     best_config["train_period_days"], best_config["n_estimators"],
                     best_config["size_half_threshold"], tuned_path)

        return {
            "best_config": best_config,
            "all_results": results,
            "saved_to": tuned_path,
        }

    # ------------------------------------------------------------------
    # Fix 21: model health check
    # ------------------------------------------------------------------

    def check_model_health(self, pair: str) -> dict:
        meta = self._metadata.get(pair)
        if meta is None:
            return {"status": "no_model", "needs_retrain": True}

        age_h = (datetime.now() - meta.trained_at).total_seconds() / 3600
        expired = age_h > self.expiration_hours

        buf = self._live_predictions.get(pair, [])
        outlier_rate = 0.0
        if buf and meta.label_std > 0:
            outlier_rate = sum(1 for p in buf if abs(p) > meta.label_std * 3) / len(buf)

        needs = expired or outlier_rate > self.outlier_protection_pct
        if expired:
            status = "expired"
        elif outlier_rate > self.outlier_protection_pct:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "version": meta.version,
            "trained_at": meta.trained_at.isoformat(),
            "age_hours": round(age_h, 1),
            "expiration_hours": self.expiration_hours,
            "validation_rmse": meta.validation_rmse,
            "validation_r2": meta.validation_r2,
            "feature_count": len(meta.feature_names),
            "label_mean": meta.label_mean,
            "label_std": meta.label_std,
            "live_predictions_count": len(buf),
            "outlier_rate": round(outlier_rate, 3),
            "needs_retrain": needs,
        }

    # ------------------------------------------------------------------
    # Model persistence
    # ------------------------------------------------------------------

    def _save_model(
        self, pair: str, model: lgb.Booster, metadata: ModelMetadata, artifacts: TrainingArtifacts,
    ) -> None:
        safe = pair.replace("-", "_")
        v = metadata.version

        model_v = os.path.join(self.models_dir, f"{safe}_v{v}_model.txt")
        meta_v = os.path.join(self.models_dir, f"{safe}_v{v}_meta.json")
        art_v = os.path.join(self.models_dir, f"{safe}_v{v}_artifacts.pkl")

        latest_m = os.path.join(self.models_dir, f"{safe}_latest_model.txt")
        latest_meta = os.path.join(self.models_dir, f"{safe}_latest_meta.json")
        latest_art = os.path.join(self.models_dir, f"{safe}_latest_artifacts.pkl")

        model.save_model(model_v)
        model.save_model(latest_m)

        md = {
            "pair": metadata.pair,
            "trained_at": metadata.trained_at.isoformat(),
            "candle_count": metadata.candle_count,
            "validation_rmse": metadata.validation_rmse,
            "validation_r2": metadata.validation_r2,
            "version": metadata.version,
            "feature_names": metadata.feature_names,
            "feature_importance": metadata.feature_importance,
            "train_window_start": metadata.train_window_start.isoformat(),
            "train_window_end": metadata.train_window_end.isoformat(),
            "label_mean": metadata.label_mean,
            "label_std": metadata.label_std,
            "pred_mean": metadata.pred_mean,
            "pred_std": metadata.pred_std,
        }
        for p in (meta_v, latest_meta):
            with open(p, "w") as f:
                json.dump(md, f, indent=2)

        for p in (art_v, latest_art):
            with open(p, "wb") as f:
                pickle.dump(artifacts, f)

    def _load_model(self, pair: str) -> lgb.Booster | None:
        safe = pair.replace("-", "_")
        model_p = os.path.join(self.models_dir, f"{safe}_latest_model.txt")
        meta_p = os.path.join(self.models_dir, f"{safe}_latest_meta.json")
        art_p = os.path.join(self.models_dir, f"{safe}_latest_artifacts.pkl")

        if not os.path.exists(model_p):
            legacy = os.path.join(self.models_dir, f"{safe}_predictor.txt")
            if os.path.exists(legacy):
                logger.info("Found legacy model for %s — needs retraining with new pipeline", pair)
            return None

        try:
            model = lgb.Booster(model_file=model_p)
            self._models[pair] = model

            if os.path.exists(meta_p):
                with open(meta_p) as f:
                    d = json.load(f)
                self._metadata[pair] = ModelMetadata(
                    pair=d["pair"],
                    trained_at=datetime.fromisoformat(d["trained_at"]),
                    candle_count=d["candle_count"],
                    validation_rmse=d.get("validation_rmse", 0),
                    validation_r2=d.get("validation_r2", 0),
                    version=d["version"],
                    feature_names=d.get("feature_names", []),
                    feature_importance=d.get("feature_importance", {}),
                    train_window_start=datetime.fromisoformat(d.get("train_window_start", d["trained_at"])),
                    train_window_end=datetime.fromisoformat(d.get("train_window_end", d["trained_at"])),
                    label_mean=d.get("label_mean", 0),
                    label_std=d.get("label_std", 1),
                    pred_mean=d.get("pred_mean", 0),
                    pred_std=d.get("pred_std", d.get("label_std", 1) * 0.3),
                )

            if os.path.exists(art_p):
                with open(art_p, "rb") as f:
                    self._artifacts[pair] = pickle.load(f)

            return model
        except Exception as e:
            logger.error("Failed to load model for %s: %s", pair, e)
            return None

    def _purge_old_models(self, pair: str) -> None:
        """Fix 14: keep only the latest N versioned model sets."""
        import glob as _glob

        safe = pair.replace("-", "_")
        versions = sorted(_glob.glob(os.path.join(self.models_dir, f"{safe}_v*_model.txt")))
        if len(versions) <= self.purge_keep:
            return
        for mf in versions[: -self.purge_keep]:
            base = os.path.basename(mf).replace("_model.txt", "")
            for ext in ("_model.txt", "_meta.json", "_artifacts.pkl"):
                p = os.path.join(self.models_dir, base + ext)
                if os.path.exists(p):
                    os.remove(p)
                    logger.debug("Purged %s", p)

    # ------------------------------------------------------------------
    # API helpers (backward-compatible)
    # ------------------------------------------------------------------

    def get_model_info(self, pair: str) -> dict | None:
        meta = self._metadata.get(pair)
        if meta is None:
            return None
        health = self.check_model_health(pair)
        top_imp = dict(sorted(meta.feature_importance.items(), key=lambda x: -x[1])[:20])
        return {
            "pair": meta.pair,
            "version": meta.version,
            "trained_at": meta.trained_at.isoformat(),
            "candle_count": meta.candle_count,
            "validation_rmse": meta.validation_rmse,
            "validation_r2": meta.validation_r2,
            "feature_count": len(meta.feature_names),
            "feature_importance": top_imp,
            "label_mean": meta.label_mean,
            "label_std": meta.label_std,
            "model_health": health["status"],
            "age_hours": health["age_hours"],
            "next_retrain_hours": max(0, self.expiration_hours - health["age_hours"]),
        }

    def get_feature_importance(self, pair: str) -> dict:
        meta = self._metadata.get(pair)
        return meta.feature_importance if meta else {}

    def prediction_to_dict(self, pred: MLPrediction) -> dict:
        return {
            "pair": pred.pair,
            "timestamp": pred.timestamp.isoformat(),
            "direction": pred.direction,
            "predicted_change_pct": round(pred.predicted_change_pct, 4),
            "confidence": round(pred.confidence, 4),
            "do_predict": pred.do_predict,
            "di_value": round(pred.di_value, 4),
            "feature_values": {k: round(v, 4) for k, v in pred.feature_values.items()},
            "feature_contributions": {k: round(v, 4) for k, v in pred.feature_contributions.items()},
            "top_bullish_factors": pred.top_bullish_factors,
            "top_bearish_factors": pred.top_bearish_factors,
            "recommended_action": pred.recommended_action,
            "recommended_size_pct": pred.recommended_size_pct,
        }
