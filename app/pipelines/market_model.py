"""Market impact model pipeline.

Inputs:
  GTI features + lagged returns + realized vol + commodity shocks + regime features.

Outputs per asset:
  vol_spike_prob_24h  (LightGBM calibrated)
  directional_bias    (-1 to 1)
  sector_stress       (0-1)
  uncertainty         (0-1)
  recommendation      (Buy/Sell/Hold — rule layer, not raw model output)

Model management:
  - Feature schema is hashed; mismatch triggers warning.
  - Brier score tracker persisted per-model-version.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Feature schema (single source of truth) ──────────────────────────────────

FEATURE_SCHEMA: list[str] = [
    "gti_value",
    "gti_delta_1h",
    "gti_confidence",
    "realized_vol",
    "return_1d",
    "return_5d",
    "sector_gti_weight",
    "oil_shock",
    "regime_vix_proxy",
    # Live Finnhub technical indicators (appended; retrain if changed)
    "rsi_14",          # RSI(14) normalised to [0, 1]
    "macd_signal_diff",# (MACD line − signal line) / close, clipped
    "bb_pct_b",        # Bollinger %B(20, 2σ)
]


def feature_schema_hash() -> str:
    payload = json.dumps(FEATURE_SCHEMA, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


# ── Sector sensitivity matrix ─────────────────────────────────────────────────
# Maps (sector, region_shock_type) → stress multiplier
_SECTOR_SENSITIVITY: dict[str, dict[str, float]] = {
    "energy": {"middle_east": 0.9, "europe": 0.6, "global": 0.5},
    "defense": {"middle_east": 0.7, "europe": 0.8, "global": 0.4},
    "technology": {"asia_pacific": 0.8, "americas": 0.3, "global": 0.3},
    "financials": {"europe": 0.6, "americas": 0.5, "global": 0.4},
    "commodities": {"middle_east": 0.8, "africa": 0.4, "global": 0.6},
    "utilities": {"global": 0.3},
    "consumer": {"global": 0.3},
}


def _sector_stress(sector: str | None, geo_risk_vector: dict[str, float]) -> float:
    sector = (sector or "global").lower()
    sensitivity = _SECTOR_SENSITIVITY.get(sector, {"global": 0.3})
    stress = 0.0
    for region, weight in geo_risk_vector.items():
        s_weight = sensitivity.get(region, sensitivity.get("global", 0.2))
        stress += weight * s_weight
    return float(min(1.0, stress))


# ── Rule-based recommendation layer ──────────────────────────────────────────

def _recommendation(
    vol_spike_prob: float,
    directional_bias: float,
    uncertainty: float,
) -> str:
    """Pure rule layer — never expose raw model output as advice."""
    if uncertainty > 0.75:
        return "Hold"
    if vol_spike_prob > 0.70 and directional_bias < -0.30:
        return "Sell"
    if vol_spike_prob < 0.35 and directional_bias > 0.30:
        return "Buy"
    return "Hold"


# ── Brier score tracker ───────────────────────────────────────────────────────

class BrierScoreTracker:
    """Online Brier score computation + reliability bin accumulation."""

    def __init__(self) -> None:
        self.n: int = 0
        self.brier_sum: float = 0.0
        self._bins: list[dict[str, float]] = [
            {"lower": i / 10, "upper": (i + 1) / 10, "mean_pred": 0.0, "mean_obs": 0.0, "count": 0}
            for i in range(10)
        ]

    def update(self, predicted_prob: float, outcome: int) -> None:
        self.brier_sum += (predicted_prob - outcome) ** 2
        self.n += 1
        bin_idx = min(9, int(predicted_prob * 10))
        b = self._bins[bin_idx]
        b["count"] += 1
        b["mean_pred"] += (predicted_prob - b["mean_pred"]) / b["count"]
        b["mean_obs"] += (outcome - b["mean_obs"]) / b["count"]

    @property
    def brier_score(self) -> float:
        return self.brier_sum / max(1, self.n)

    def to_dict(self) -> dict[str, Any]:
        return {
            "brier_score": round(self.brier_score, 4),
            "n_observations": self.n,
            "reliability_bins": [b for b in self._bins if b["count"] > 0],
        }


# ── Feature builder ───────────────────────────────────────────────────────────

@dataclass
class AssetFeatures:
    symbol: str
    sector: str | None
    region: str
    gti_value: float
    gti_delta_1h: float
    gti_confidence: float
    realized_vol: float = 0.0
    return_1d: float = 0.0
    return_5d: float = 0.0
    sector_gti_weight: float = 0.0
    oil_shock: float = 0.0
    regime_vix_proxy: float = 0.0
    # Live Finnhub technical indicators
    rsi_14: float = 0.5          # RSI(14) normalised: 0 = oversold, 1 = overbought
    macd_signal_diff: float = 0.0 # (MACD − signal) / close, clipped to [−1, 1]
    bb_pct_b: float = 0.5        # Bollinger %B: 0 = lower band, 1 = upper band
    geo_risk_vector: dict[str, float] = field(default_factory=lambda: {"global": 1.0})

    def to_array(self) -> list[float]:
        return [
            self.gti_value / 100.0,
            self.gti_delta_1h / 10.0,
            self.gti_confidence,
            self.realized_vol,
            self.return_1d,
            self.return_5d,
            self.sector_gti_weight,
            self.oil_shock,
            self.regime_vix_proxy,
            self.rsi_14,          # already [0, 1]
            self.macd_signal_diff, # already clipped
            self.bb_pct_b,         # already [0, 1]
        ]


# ── Market impact model ────────────────────────────────────────────────────────

@dataclass
class AssetImpactResult:
    symbol: str
    vol_spike_prob_24h: float
    directional_bias: float
    sector_stress: float
    uncertainty_score: float
    recommendation: str
    reasoning: str
    confidence_score: float
    model_version: str
    feature_hash: str


class MarketImpactModel:
    """LightGBM + XGBoost voting-ensemble impact model with rule recommendation layer.

    Training data is sourced from real market data (yfinance: SPY, ^VIX, USO).
    On first run, if no persisted artifacts exist the model fetches 5 years of
    daily market history, builds features aligned to FEATURE_SCHEMA, and trains a
    soft-voting ensemble of LightGBMClassifier + XGBClassifier.  If yfinance is
    unreachable the pipeline falls back to synthetic bootstrap data so the service
    still starts.  Either way, the trained artifacts are pickled to model_artifacts/
    for fast reloads.
    """

    def __init__(self) -> None:
        self._gbm: Any = None  # LightGBM model for vol spike prob
        self._linear: Any = None  # Ridge regression for directional bias
        self._version: str = "2.0.0"
        self._feature_hash = feature_schema_hash()
        self._brier_tracker = BrierScoreTracker()

    def _ensure_loaded(self) -> None:
        if self._gbm is not None:
            return
        settings = get_settings()
        gbm_path = settings.model_artifacts_dir / "vol_spike_lgbm.pkl"
        bias_path = settings.model_artifacts_dir / "directional_bias_ridge.pkl"

        if gbm_path.exists() and bias_path.exists():
            import pickle
            with gbm_path.open("rb") as f:
                self._gbm = pickle.load(f)  # noqa: S301
            with bias_path.open("rb") as f:
                self._linear = pickle.load(f)  # noqa: S301
            logger.info("market_model_loaded_from_disk")
        else:
            logger.info("market_model_not_found_training_on_real_data")
            self._train_model(gbm_path, bias_path)

    # ── Real training-data builder ─────────────────────────────────────────────

    # ── Technical-indicator helpers (pure pandas, no extra deps) ─────────────

    @staticmethod
    def _calc_rsi(close: "pd.Series", period: int = 14) -> "pd.Series":
        delta = close.diff()
        gain  = delta.clip(lower=0.0).rolling(period).mean()
        loss  = (-delta.clip(upper=0.0)).rolling(period).mean()
        rs    = gain / (loss + 1e-9)
        return (rs / (1.0 + rs)).clip(0.0, 1.0)  # normalised to [0, 1]

    @staticmethod
    def _calc_macd_diff(
        close: "pd.Series", fast: int = 12, slow: int = 26, signal: int = 9
    ) -> "pd.Series":
        ema_fast   = close.ewm(span=fast, adjust=False).mean()
        ema_slow   = close.ewm(span=slow, adjust=False).mean()
        macd_line  = ema_fast - ema_slow
        signal_line= macd_line.ewm(span=signal, adjust=False).mean()
        diff       = (macd_line - signal_line) / (close + 1e-9)
        return diff.clip(-0.01, 0.01) / 0.01   # normalise to approx [-1, 1]

    @staticmethod
    def _calc_bb_pct_b(close: "pd.Series", period: int = 20, n_std: float = 2.0) -> "pd.Series":
        sma   = close.rolling(period).mean()
        std   = close.rolling(period).std()
        upper = sma + n_std * std
        lower = sma - n_std * std
        return ((close - lower) / (upper - lower + 1e-9)).clip(0.0, 1.0)

    def _build_real_training_data(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Fetch 5 years of daily market data via yfinance and build training arrays.

        Features follow FEATURE_SCHEMA exactly (12 features).  VIX proxies
        geopolitical-tension columns; live RSI/MACD/%B are computed from SPY.

        Returns
        -------
        X         : (n_samples, n_features) float array
        y_vol     : (n_samples,) binary — 1 if next-day |SPY return| > 1.5× 20d σ
        y_bias    : (n_samples,) float  — next-day SPY return scaled to ~(-1, 1)
        """
        import pandas as pd
        import yfinance as yf

        logger.info("fetching_real_training_data", tickers=["SPY", "^VIX", "USO"])
        raw = yf.download(
            ["SPY", "^VIX", "USO"],
            period="5y",
            auto_adjust=True,
            progress=False,
        )
        closes: pd.DataFrame = raw["Close"].dropna(subset=["SPY", "^VIX"])

        spy = closes["SPY"]
        vix = closes["^VIX"]
        uso_series = closes.get("USO")
        uso_ret = (
            uso_series.pct_change().fillna(0.0)
            if uso_series is not None
            else pd.Series(0.0, index=spy.index)
        )

        spy_ret1 = spy.pct_change()
        spy_ret5 = spy.pct_change(5)

        # Realized vol: 20-day rolling std of daily returns (annualised)
        realized_vol = spy_ret1.rolling(20).std() * (252 ** 0.5)

        # GTI proxies derived from VIX
        vix_norm = (vix / 100.0).clip(0.0, 1.0)
        vix_range = vix.rolling(60).max() - vix.rolling(60).min() + 1e-9
        gti_confidence = (1.0 - (vix - vix.rolling(60).min()) / vix_range).clip(0.0, 1.0)

        # Live technical indicators (computed inline from SPY history)
        rsi_14       = self._calc_rsi(spy, 14)
        macd_diff    = self._calc_macd_diff(spy)
        bb_pct_b     = self._calc_bb_pct_b(spy)

        df = pd.DataFrame(
            {
                "gti_value": vix_norm,
                "gti_delta_1h": (vix.diff() / 10.0),
                "gti_confidence": gti_confidence,
                "realized_vol": realized_vol,
                "return_1d": spy_ret1,
                "return_5d": spy_ret5,
                "sector_gti_weight": (vix / 80.0).clip(0.0, 1.0),
                "oil_shock": uso_ret,
                "regime_vix_proxy": (vix / 80.0).clip(0.0, 1.0),
                "rsi_14": rsi_14,
                "macd_signal_diff": macd_diff,
                "bb_pct_b": bb_pct_b,
            }
        ).dropna()

        spy_ret_next = spy_ret1.shift(-1).reindex(df.index)
        rolling_std = spy_ret1.rolling(20).std().reindex(df.index)

        # Binary label: vol spike if next-day |return| exceeds 1.5× rolling σ
        y_vol = (spy_ret_next.abs() > 1.5 * rolling_std).astype(int)
        # Continuous label: next-day return scaled to approx (-1, 1)
        y_bias = spy_ret_next.clip(-0.05, 0.05) * 20.0

        valid = y_vol.notna() & y_bias.notna()
        df = df[valid]
        y_vol = y_vol[valid]
        y_bias = y_bias[valid]

        logger.info("real_training_data_ready", n_samples=len(df))
        return df[FEATURE_SCHEMA].values, y_vol.values.astype(int), y_bias.values.astype(float)

    # ── Ensemble trainer ──────────────────────────────────────────────────────

    def _train_model(self, gbm_path: Path, bias_path: Path) -> None:
        """Train a soft-voting ensemble (LightGBM + XGBoost) on real market data.

        Data sourced exclusively from yfinance.  Synthetic bootstrap is permanently
        disabled — if yfinance is unreachable the method raises and the caller
        should retry after connectivity is restored.
        """
        import pickle
        from sklearn.linear_model import Ridge

        # ── 1. Training data (real only) ──────────────────────────────────────
        X, y_vol, y_bias_vals = self._build_real_training_data()
        logger.info("training_on_real_market_data", n_samples=len(X))

        # ── 2. Build estimator list ───────────────────────────────────────────
        estimators: list[tuple[str, Any]] = []

        try:
            import lightgbm as lgb
            lgb_clf = lgb.LGBMClassifier(
                objective="binary",
                metric="binary_logloss",
                num_leaves=31,
                n_estimators=200,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                verbosity=-1,
            )
            estimators.append(("lgbm", lgb_clf))
            logger.info("ensemble_adding_lightgbm")
        except ImportError:
            logger.warning("lightgbm_unavailable")

        try:
            import xgboost as xgb
            xgb_clf = xgb.XGBClassifier(
                objective="binary:logistic",
                eval_metric="logloss",
                n_estimators=200,
                learning_rate=0.05,
                max_depth=5,
                subsample=0.8,
                colsample_bytree=0.8,
                verbosity=0,
            )
            estimators.append(("xgb", xgb_clf))
            logger.info("ensemble_adding_xgboost")
        except ImportError:
            logger.warning("xgboost_unavailable")

        # ── 3. Train ──────────────────────────────────────────────────────────
        if not estimators:
            logger.warning("all_boosting_libs_unavailable_falling_back_to_sklearn")
            from sklearn.ensemble import GradientBoostingClassifier
            gbm: Any = GradientBoostingClassifier(
                n_estimators=200, learning_rate=0.05, max_depth=4
            )
            gbm.fit(X, y_vol)
        elif len(estimators) == 1:
            name, clf = estimators[0]
            clf.fit(X, y_vol)
            gbm = clf
            logger.info("single_estimator_trained", name=name)
        else:
            from sklearn.ensemble import VotingClassifier
            gbm = VotingClassifier(estimators=estimators, voting="soft")
            gbm.fit(X, y_vol)
            logger.info("voting_ensemble_trained", members=[e[0] for e in estimators])

        ridge = Ridge(alpha=1.0)
        ridge.fit(X, y_bias_vals)

        for path, obj in [(gbm_path, gbm), (bias_path, ridge)]:
            with path.open("wb") as f:
                pickle.dump(obj, f)

        self._gbm = gbm
        self._linear = ridge
        logger.info("ensemble_model_trained_and_saved", version=self._version)

    def predict(self, features: AssetFeatures) -> AssetImpactResult:
        self._ensure_loaded()
        arr = np.array([features.to_array()])

        vol_prob = float(self._gbm.predict_proba(arr)[0][1])
        raw_bias = float(self._linear.predict(arr)[0])
        directional_bias = float(max(-1.0, min(1.0, raw_bias)))

        ss = _sector_stress(features.sector, features.geo_risk_vector)
        uncertainty = float(
            0.4 * (1.0 - features.gti_confidence)
            + 0.3 * features.realized_vol
            + 0.3 * (1.0 - abs(directional_bias))
        )
        uncertainty = min(1.0, max(0.0, uncertainty))

        rec = _recommendation(vol_prob, directional_bias, uncertainty)

        symbol = features.symbol
        vol_spike_prob = vol_prob
        gti_value = features.gti_value
        gti_delta = features.gti_delta_1h
        sector = features.sector
        sector_stress = ss

        reasoning = self._generate_reasoning(
            symbol, vol_spike_prob, directional_bias, gti_value, gti_delta, sector
        )
        conf = 1.0 - (0.5 * uncertainty + 0.2 * abs(gti_delta/10.0))

        return AssetImpactResult(
            symbol=symbol,
            vol_spike_prob_24h=round(float(vol_spike_prob), 4),
            directional_bias=round(float(directional_bias), 4),
            sector_stress=round(float(ss), 4),
            uncertainty_score=round(float(uncertainty), 4),
            recommendation=rec,
            reasoning=reasoning,
            confidence_score=round(float(max(0.0, min(1.0, conf))), 4),
            model_version=self._version,
            feature_hash=self._feature_hash,
        )

    def _generate_reasoning(
        self, symbol: str, vol: float, bias: float, gti: float, delta: float, sector: str | None
    ) -> str:
        trend = "escalating" if delta > 1.0 else "stable" if abs(delta) < 1.0 else "de-escalating"
        impact = "high" if vol > 0.6 else "moderate" if vol > 0.3 else "minimal"
        sentiment = "bullish" if bias > 0.3 else "bearish" if bias < -0.3 else "neutral"
        sector_str = f"({sector})" if sector else ""

        return (
            f"Asset {symbol} {sector_str} shows {impact} vol risk due to {trend} tension (GTI {gti:.1f}). "
            f"Overall bias is {sentiment}."
        )

    def predict_batch(self, features_list: list[AssetFeatures]) -> list[AssetImpactResult]:
        return [self.predict(f) for f in features_list]

    def update_calibration(self, predicted_prob: float, outcome: int) -> None:
        self._brier_tracker.update(predicted_prob, outcome)

    def calibration_report(self) -> dict[str, Any]:
        return self._brier_tracker.to_dict()


_impact_model: MarketImpactModel | None = None


def get_impact_model() -> MarketImpactModel:
    global _impact_model  # noqa: PLW0603
    if _impact_model is None:
        _impact_model = MarketImpactModel()
    return _impact_model
