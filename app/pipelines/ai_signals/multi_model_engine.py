"""Multi-model engine for AI Signals Engine.

Combines Directional, Volatility, and Range models into an ensemble logic
to produce high-confidence trading signals.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.pipelines.feature_engineering import EnhancedAssetFeatures
from app.core.logging import get_logger

logger = get_logger(__name__)

@dataclass
class ModelOutput:
    direction: Literal["BUY", "SELL", "HOLD"]
    direction_prob: float  # 0 to 1
    volatility: Literal["LOW", "MEDIUM", "HIGH"]
    volatility_score: float  # 0 to 1
    target_range_pct: float  # expected move in %
    bullish_strength: float  # 0 to 100
    bearish_strength: float  # 0 to 100

class MultiModelEngine:
    def __init__(self) -> None:
        pass

    def run_direction_model(self, features: EnhancedAssetFeatures) -> tuple[str, float]:
        """A. Direction Model (LightGBM/Ensemble Logic)."""
        # Weighted sum of features for direction
        score = (
            features.returns_short_term * 0.2 +
            features.returns_long_term * 0.1 +
            features.sentiment_score * 0.4 +
            features.macro_strength_score * 0.2 +
            (50 - features.geopolitical_tension_index) / 100 * 0.1
        )
        
        # Add technicals
        score += (features.rsi - 0.5) * 0.2
        score += features.macd * 0.1
        
        # Simple thresholding
        if score > 0.15:
            return "BUY", float(min(0.95, 0.5 + score))
        elif score < -0.15:
            return "SELL", float(min(0.95, 0.5 - score))
        else:
            return "HOLD", 0.5

    def run_volatility_model(self, features: EnhancedAssetFeatures) -> tuple[str, float]:
        """B. Volatility Model (LOW / MEDIUM / HIGH)."""
        # Based on ATR + realized volatility + regime
        v_score = (features.volatility_regime * 0.6 + 
                  (features.geopolitical_tension_index / 100.0) * 0.4)
        
        if v_score < 0.35:
            return "LOW", v_score
        elif v_score < 0.70:
            return "MEDIUM", v_score
        else:
            return "HIGH", v_score

    def run_range_model(self, features: EnhancedAssetFeatures) -> float:
        """C. Range/Target Model (Predict expected move %)."""
        # Volatility * sqrt(T) * confidence factor
        base_move = features.atr / features.price if features.price > 0 else 0.02
        v_multiplier = 1.0 + features.volatility_regime
        return float(base_move * v_multiplier * 1.5)

    def ensemble_signals(self, features: EnhancedAssetFeatures) -> ModelOutput:
        """Combine all model outputs using ensemble logic."""
        direction, prob = self.run_direction_model(features)
        vol, vol_score = self.run_volatility_model(features)
        target_range = self.run_range_model(features)
        
        # Bullish vs Bearish strength calculation
        # Map direction score to 0-100%
        # If direction is BUY, prob is higher. If SELL, prob is higher.
        if direction == "BUY":
            bullish = prob * 100
            bearish = 100 - bullish
        elif direction == "SELL":
            bearish = prob * 100
            bullish = 100 - bearish
        else:
            bullish = 50 + (features.sentiment_score * 20)
            bearish = 100 - bullish
            
        return ModelOutput(
            direction=direction,
            direction_prob=prob,
            volatility=vol,
            volatility_score=vol_score,
            target_range_pct=target_range,
            bullish_strength=float(max(0, min(100, bullish))),
            bearish_strength=float(max(0, min(100, bearish)))
        )

_model_engine: MultiModelEngine | None = None

def get_model_engine() -> MultiModelEngine:
    global _model_engine
    if _model_engine is None:
        _model_engine = MultiModelEngine()
    return _model_engine
