from __future__ import annotations

"""GARCH-LightGBM hybrid volatility forecaster.

Academic basis: Crypto volatility clusters (Bollerslev 1986, Hansen & Lunde 2005).
GARCH captures volatility persistence; LightGBM captures nonlinear cross-feature
patterns. The hybrid consistently outperforms either model alone (R² 0.3–0.6).

Usage:
    vp = VolatilityPredictor(config)
    vp.train(pair, candles)
    pred = vp.predict(pair, candles)
    # pred.predicted_vol_12h = annualized volatility forecast
    # pred.spacing_multiplier = how to adjust grid spacing (0.5–2.0)
"""

import json
import logging
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)

MODEL_DIR = "models"


@dataclass
class VolatilityPrediction:
    timestamp: datetime
    pair: str
    predicted_vol_12h: float          # annualized volatility forecast
    current_vol_12h: float            # current realized volatility
    vol_30d_avg: float                # 30-day average for context
    vol_regime: str                   # "low", "normal", "high", "extreme"
    spacing_multiplier: float         # 0.5–2.0 for grid adjustment
    recommended_num_grids: int        # suggested grid count
    confidence: float                 # 0–1
    garch_vol: float                  # GARCH conditional volatility
    feature_importance: dict = field(default_factory=dict)


@dataclass
class VolModelMeta:
    pair: str
    trained_at: datetime
    candle_count: int
    validation_rmse: float
    validation_r2: float
    version: int
    feature_names: list
    feature_importance: dict
    vol_mean: float                   # mean realized vol in training set
    vol_std: float                    # std of realized vol in training set


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _build_vol_features(df: pd.DataFrame, btc_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build volatility-specific features from OHLCV dataframe.

    Features based on HAR (Heterogeneous Autoregressive) model plus
    GARCH conditional volatility and auxiliary indicators.
    """
    feat = pd.DataFrame(index=df.index)

    # Log returns
    log_ret = np.log(df["close"] / df["close"].shift(1))
    feat["log_return"] = log_ret

    # Realized volatility at multiple horizons (HAR model lags)
    for h in [1, 6, 12, 24, 168]:  # 1h, 6h, 12h, 24h, 7d
        if h == 1:
            # rolling(1).std() is always NaN; use absolute return as proxy
            feat[f"rv_{h}h"] = log_ret.abs() * np.sqrt(24)
        else:
            rv = log_ret.rolling(h).std() * np.sqrt(24)  # annualized
            feat[f"rv_{h}h"] = rv

    # Parkinson volatility (uses high-low, more efficient estimator)
    hl_ratio = np.log(df["high"] / df["low"])
    for h in [12, 24]:
        feat[f"parkinson_{h}h"] = hl_ratio.rolling(h).apply(
            lambda x: np.sqrt((1 / (4 * np.log(2))) * (x ** 2).mean())
        ) * np.sqrt(24)

    # ATR as % of price
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    for h in [14, 24]:
        feat[f"atr_pct_{h}h"] = (tr.rolling(h).mean() / df["close"]) * 100

    # Bollinger Band width (volatility proxy)
    for h in [20, 50]:
        sma = df["close"].rolling(h).mean()
        std = df["close"].rolling(h).std()
        feat[f"bb_width_{h}"] = (2 * std / sma) * 100

    # Volume ratio (volume spikes precede volatility)
    vol_avg_24 = df["volume"].rolling(24).mean()
    vol_avg_168 = df["volume"].rolling(168).mean()
    feat["vol_ratio_24h"] = df["volume"] / vol_avg_24.clip(lower=1e-10)
    feat["vol_ratio_7d"] = df["volume"] / vol_avg_168.clip(lower=1e-10)
    feat["vol_trend"] = vol_avg_24 / vol_avg_168.clip(lower=1e-10)

    # Return dispersion (abs returns over window)
    for h in [6, 12, 24]:
        feat[f"abs_return_sum_{h}h"] = log_ret.abs().rolling(h).sum()

    # Momentum features (large moves predict future volatility)
    for h in [1, 3, 6, 12]:
        feat[f"momentum_{h}h"] = (df["close"] / df["close"].shift(h) - 1) * 100

    # Candle body ratio (large candles = volatile)
    feat["candle_body_pct"] = ((df["close"] - df["open"]) / df["open"]).abs() * 100
    feat["candle_range_pct"] = ((df["high"] - df["low"]) / df["low"]) * 100

    # Hour of day and day of week (volatility has temporal patterns)
    if hasattr(df.index, 'hour'):
        feat["hour"] = df.index.hour
        feat["day_of_week"] = df.index.dayofweek
    elif "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"])
        feat["hour"] = ts.dt.hour
        feat["day_of_week"] = ts.dt.dayofweek

    # GARCH conditional volatility (computed separately, added as feature)
    garch_vol = _fit_garch(log_ret)
    if garch_vol is not None:
        feat["garch_vol"] = garch_vol
    else:
        feat["garch_vol"] = feat.get("rv_12h", 0)

    # BTC cross-market volatility spillover
    if btc_df is not None and len(btc_df) >= len(df):
        btc_ret = np.log(btc_df["close"] / btc_df["close"].shift(1))
        btc_aligned = btc_ret.reindex(df.index, method="nearest")
        for h in [12, 24]:
            feat[f"btc_rv_{h}h"] = btc_aligned.rolling(h).std() * np.sqrt(24)
        feat["btc_corr_24h"] = log_ret.rolling(24).corr(btc_aligned)

    return feat


def _fit_garch(returns: pd.Series) -> pd.Series | None:
    """Fit GARCH(1,1) and return conditional volatility series."""
    try:
        from arch import arch_model
        clean = returns.dropna() * 100  # arch expects percentage returns
        if len(clean) < 100:
            return None
        am = arch_model(clean, vol="Garch", p=1, q=1, mean="Constant", rescale=False)
        res = am.fit(disp="off", show_warning=False)
        cond_vol = res.conditional_volatility / 100 * np.sqrt(24)  # annualize
        return cond_vol.reindex(returns.index)
    except Exception as e:
        logger.debug(f"GARCH fitting failed: {e}")
        return None


def _compute_vol_label(df: pd.DataFrame, horizon: int = 12) -> pd.Series:
    """Compute realized volatility label: annualized vol over next `horizon` hours."""
    log_ret = np.log(df["close"] / df["close"].shift(1))
    # Forward-looking realized volatility
    future_vol = log_ret.shift(-1).rolling(horizon).std().shift(-horizon + 1) * np.sqrt(24)
    return future_vol


# ---------------------------------------------------------------------------
# Predictor class
# ---------------------------------------------------------------------------

class VolatilityPredictor:
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.forecast_horizon = self.config.get("forecast_horizon", 12)
        self.har_lags = self.config.get("har_lags", [1, 6, 12, 24, 168])
        self.include_btc_vol = self.config.get("include_btc_vol", True)

        self._models: dict[str, lgb.Booster] = {}
        self._metadata: dict[str, VolModelMeta] = {}
        self._scalers: dict[str, MinMaxScaler] = {}
        self._feature_names: dict[str, list] = {}

        os.makedirs(MODEL_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, pair: str, candles: list, btc_candles: list | None = None) -> VolModelMeta | None:
        """Train volatility prediction model for a pair."""
        from exchange.models import Candle

        df = self._candles_to_df(candles)
        if len(df) < 200:
            logger.warning(f"Not enough candles for {pair} volatility training ({len(df)})")
            return None

        btc_df = self._candles_to_df(btc_candles) if btc_candles else None

        # Build features and label
        features = _build_vol_features(df, btc_df)
        label = _compute_vol_label(df, self.forecast_horizon)

        # Merge and drop NaNs (also treat ±Inf as NaN — can appear in ratio features on zero denominators)
        combined = features.copy()
        combined["label"] = label
        combined = combined.replace([np.inf, -np.inf], np.nan).dropna()

        if len(combined) < 100:
            logger.warning(f"Not enough valid samples for {pair} after NaN drop ({len(combined)})")
            return None

        X = combined.drop(columns=["label"])
        y = combined["label"]
        feature_names = list(X.columns)

        # Train/val split (80/20, recent data trains)
        split = int(len(X) * 0.8)
        X_train, X_val = X.iloc[:split], X.iloc[split:]
        y_train, y_val = y.iloc[:split], y.iloc[split:]

        # Scale features
        scaler = MinMaxScaler(feature_range=(-1, 1))
        X_train_s = scaler.fit_transform(X_train)
        X_val_s = scaler.transform(X_val)

        # Recency weighting
        n = len(X_train_s)
        weights = np.exp(np.linspace(-2, 0, n))

        # LightGBM training
        lgb_params = {
            "objective": "regression",
            "metric": "rmse",
            "num_leaves": 16,
            "learning_rate": 0.03,
            "feature_fraction": 0.6,
            "max_depth": 6,
            "reg_alpha": 0.5,
            "reg_lambda": 0.5,
            "verbose": -1,
        }
        lgb_params.update(self.config.get("lgb_params", {}))

        train_ds = lgb.Dataset(X_train_s, label=y_train.values, weight=weights,
                               feature_name=feature_names)
        val_ds = lgb.Dataset(X_val_s, label=y_val.values, feature_name=feature_names,
                             reference=train_ds)

        model = lgb.train(
            lgb_params,
            train_ds,
            num_boost_round=self.config.get("n_estimators", 200),
            valid_sets=[val_ds],
            callbacks=[lgb.log_evaluation(0)],
        )

        # Evaluate
        preds_val = model.predict(X_val_s)
        residuals = y_val.values - preds_val
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y_val.values - y_val.mean()) ** 2))
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Feature importance
        importance = dict(zip(feature_names, model.feature_importance(importance_type="gain").tolist()))
        total_imp = sum(importance.values()) or 1
        importance = {k: round(v / total_imp, 4) for k, v in
                      sorted(importance.items(), key=lambda x: -x[1])[:20]}

        # Version
        prev = self._metadata.get(pair)
        version = (prev.version + 1) if prev else 1

        meta = VolModelMeta(
            pair=pair,
            trained_at=datetime.utcnow(),
            candle_count=len(df),
            validation_rmse=round(rmse, 4),
            validation_r2=round(r2, 4),
            version=version,
            feature_names=feature_names,
            feature_importance=importance,
            vol_mean=float(y.mean()),
            vol_std=float(y.std()),
        )

        # Store
        self._models[pair] = model
        self._metadata[pair] = meta
        self._scalers[pair] = scaler
        self._feature_names[pair] = feature_names

        # Save to disk
        self._save_model(pair, model, meta, scaler)

        logger.info(
            f"Trained volatility model for {pair}: RMSE={rmse:.4f} R²={r2:.4f} "
            f"vol_mean={meta.vol_mean:.2f}% features={len(feature_names)} v{version}"
        )

        return meta

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, pair: str, candles: list, btc_candles: list | None = None) -> VolatilityPrediction | None:
        """Predict volatility for next forecast_horizon hours."""
        model = self._models.get(pair)
        meta = self._metadata.get(pair)
        scaler = self._scalers.get(pair)

        if model is None or meta is None or scaler is None:
            if not self._load_model(pair):
                return None
            model = self._models[pair]
            meta = self._metadata[pair]
            scaler = self._scalers[pair]

        df = self._candles_to_df(candles)
        if len(df) < 50:
            return None

        btc_df = self._candles_to_df(btc_candles) if btc_candles else None

        features = _build_vol_features(df, btc_df)
        features = features.dropna()
        if len(features) == 0:
            return None

        # Use latest row
        latest = features.iloc[[-1]]

        # Ensure same features
        for col in self._feature_names.get(pair, []):
            if col not in latest.columns:
                latest[col] = 0.0
        latest = latest[self._feature_names.get(pair, latest.columns)]

        X_scaled = scaler.transform(latest)
        pred_vol = float(model.predict(X_scaled)[0])
        pred_vol = max(pred_vol, 0.01)  # volatility can't be negative

        # Current realized volatility
        log_ret = np.log(df["close"] / df["close"].shift(1))
        current_vol = float(log_ret.tail(12).std() * np.sqrt(24) * 100)  # as percentage
        vol_30d = float(log_ret.tail(720).std() * np.sqrt(24) * 100) if len(log_ret) > 720 else current_vol

        # GARCH component
        garch_vol = float(features["garch_vol"].iloc[-1]) if "garch_vol" in features.columns else current_vol

        # Classify regime
        if pred_vol < meta.vol_mean * 0.5:
            regime = "low"
        elif pred_vol < meta.vol_mean * 1.5:
            regime = "normal"
        elif pred_vol < meta.vol_mean * 2.5:
            regime = "high"
        else:
            regime = "extreme"

        # Spacing multiplier: ratio of predicted vol to average vol
        # Clamped to [0.5, 2.0]
        ratio = pred_vol / meta.vol_mean if meta.vol_mean > 0 else 1.0
        spacing_mult = max(0.5, min(2.0, ratio))

        # Recommended grid count: inverse of spacing_mult (more grids when tighter)
        base_grids = 10
        rec_grids = max(6, min(25, int(base_grids / spacing_mult)))

        # Confidence from R² of model (simple proxy)
        confidence = max(0.0, min(1.0, meta.validation_r2))

        # Top feature contributions
        importance = meta.feature_importance

        return VolatilityPrediction(
            timestamp=datetime.utcnow(),
            pair=pair,
            predicted_vol_12h=round(pred_vol, 2),
            current_vol_12h=round(current_vol, 2),
            vol_30d_avg=round(vol_30d, 2),
            vol_regime=regime,
            spacing_multiplier=round(spacing_mult, 3),
            recommended_num_grids=rec_grids,
            confidence=round(confidence, 3),
            garch_vol=round(garch_vol, 4),
            feature_importance=importance,
        )

    # ------------------------------------------------------------------
    # Grid spacing recommendation
    # ------------------------------------------------------------------

    def get_spacing_adjustment(self, pair: str, candles: list,
                                btc_candles: list | None = None) -> dict:
        """Return spacing adjustment for the grid strategy.

        Returns:
            {
                "spacing_multiplier": 1.3,   # multiply current spacing by this
                "recommended_grids": 8,      # or use this many grids
                "vol_regime": "high",
                "predicted_vol": 28.5,
                "confidence": 0.45,
            }
        """
        pred = self.predict(pair, candles, btc_candles)
        if pred is None:
            return {"spacing_multiplier": 1.0, "recommended_grids": 10,
                    "vol_regime": "unknown", "predicted_vol": 0, "confidence": 0}

        return {
            "spacing_multiplier": pred.spacing_multiplier,
            "recommended_grids": pred.recommended_num_grids,
            "vol_regime": pred.vol_regime,
            "predicted_vol": pred.predicted_vol_12h,
            "confidence": pred.confidence,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_model(self, pair: str, model: lgb.Booster, meta: VolModelMeta,
                    scaler: MinMaxScaler):
        safe = pair.replace("-", "_").lower()
        prefix = os.path.join(MODEL_DIR, f"{safe}_vol")

        model.save_model(f"{prefix}_v{meta.version}_model.txt")
        with open(f"{prefix}_v{meta.version}_meta.json", "w") as f:
            json.dump({
                "pair": meta.pair,
                "trained_at": meta.trained_at.isoformat(),
                "candle_count": meta.candle_count,
                "validation_rmse": meta.validation_rmse,
                "validation_r2": meta.validation_r2,
                "version": meta.version,
                "feature_names": meta.feature_names,
                "feature_importance": meta.feature_importance,
                "vol_mean": meta.vol_mean,
                "vol_std": meta.vol_std,
            }, f, indent=2)
        with open(f"{prefix}_v{meta.version}_scaler.pkl", "wb") as f:
            pickle.dump(scaler, f)

        # Latest pointers
        model.save_model(f"{prefix}_latest_model.txt")
        with open(f"{prefix}_latest_meta.json", "w") as f:
            json.dump({
                "pair": meta.pair,
                "trained_at": meta.trained_at.isoformat(),
                "candle_count": meta.candle_count,
                "validation_rmse": meta.validation_rmse,
                "validation_r2": meta.validation_r2,
                "version": meta.version,
                "feature_names": meta.feature_names,
                "feature_importance": meta.feature_importance,
                "vol_mean": meta.vol_mean,
                "vol_std": meta.vol_std,
            }, f, indent=2)
        with open(f"{prefix}_latest_scaler.pkl", "wb") as f:
            pickle.dump(scaler, f)

    def _load_model(self, pair: str) -> bool:
        safe = pair.replace("-", "_").lower()
        prefix = os.path.join(MODEL_DIR, f"{safe}_vol")

        model_path = f"{prefix}_latest_model.txt"
        meta_path = f"{prefix}_latest_meta.json"
        scaler_path = f"{prefix}_latest_scaler.pkl"

        if not all(os.path.exists(p) for p in [model_path, meta_path, scaler_path]):
            return False

        try:
            model = lgb.Booster(model_file=model_path)
            with open(meta_path) as f:
                md = json.load(f)
            with open(scaler_path, "rb") as f:
                scaler = pickle.load(f)

            meta = VolModelMeta(
                pair=md["pair"],
                trained_at=datetime.fromisoformat(md["trained_at"]),
                candle_count=md["candle_count"],
                validation_rmse=md["validation_rmse"],
                validation_r2=md["validation_r2"],
                version=md["version"],
                feature_names=md["feature_names"],
                feature_importance=md["feature_importance"],
                vol_mean=md["vol_mean"],
                vol_std=md["vol_std"],
            )

            self._models[pair] = model
            self._metadata[pair] = meta
            self._scalers[pair] = scaler
            self._feature_names[pair] = meta.feature_names
            return True
        except Exception as e:
            logger.warning(f"Failed to load volatility model for {pair}: {e}")
            return False

    # ------------------------------------------------------------------
    # Model info for dashboard
    # ------------------------------------------------------------------

    def get_model_info(self) -> list[dict]:
        """Return info for all trained volatility models."""
        info = []
        for pair, meta in self._metadata.items():
            age_hours = (datetime.utcnow() - meta.trained_at).total_seconds() / 3600
            info.append({
                "pair": pair,
                "version": meta.version,
                "trained_at": meta.trained_at.isoformat(),
                "candle_count": meta.candle_count,
                "validation_rmse": meta.validation_rmse,
                "validation_r2": meta.validation_r2,
                "feature_count": len(meta.feature_names),
                "feature_importance": meta.feature_importance,
                "vol_mean": meta.vol_mean,
                "vol_std": meta.vol_std,
                "age_hours": round(age_hours, 1),
                "model_type": "GARCH-LightGBM",
            })
        return info

    def get_latest_predictions(self) -> dict[str, VolatilityPrediction]:
        """Return cached latest predictions (call predict first)."""
        return {}  # predictions are not cached by default — call predict() each cycle

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _candles_to_df(candles) -> pd.DataFrame:
        if not candles:
            return pd.DataFrame()
        rows = []
        for c in candles:
            if hasattr(c, "timestamp"):
                rows.append({
                    "timestamp": c.timestamp,
                    "open": c.open, "high": c.high,
                    "low": c.low, "close": c.close,
                    "volume": c.volume,
                })
            elif isinstance(c, dict):
                rows.append(c)
        df = pd.DataFrame(rows)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp").sort_index()
        return df
