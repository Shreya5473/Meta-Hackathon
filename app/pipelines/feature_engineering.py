"""Feature engineering layer for AI Signals Engine.

Generates structured feature vectors for all asset classes, incorporating
market data, technical indicators, macro strength, and geopolitical sentiment.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.core.logging import get_logger
from app.pipelines.macro_data import MacroIndicator
from app.pipelines.geopolitical_news import GeopoliticalArticle

logger = get_logger(__name__)

@dataclass
class EnhancedAssetFeatures:
    symbol: str
    asset_class: str
    price: float
    returns_short_term: float  # 1-day return
    returns_long_term: float   # 5-day or 20-day return
    atr: float                 # Average True Range
    volatility_regime: float   # 0 to 1 (LOW to HIGH)
    sentiment_score: float     # -1 to 1 (BEARISH to BULLISH)
    geopolitical_tension_index: float # 0 to 100
    macro_strength_score: float # -1 to 1
    correlation_factors: dict[str, float] = field(default_factory=dict)
    
    # Technical indicators
    rsi: float = 0.5
    macd: float = 0.0
    bb_pct_b: float = 0.5

    def to_vector(self) -> list[float]:
        """Normalize all values to a structured feature vector."""
        return [
            self.returns_short_term,
            self.returns_long_term,
            self.atr / self.price if self.price > 0 else 0.0,
            self.volatility_regime,
            (self.sentiment_score + 1) / 2, # Map [-1, 1] to [0, 1]
            self.geopolitical_tension_index / 100.0,
            (self.macro_strength_score + 1) / 2, # Map [-1, 1] to [0, 1]
            self.rsi,
            self.macd,
            self.bb_pct_b
        ]

class FeatureEngineeringService:
    def __init__(self) -> None:
        pass

    def calculate_atr(self, high: list[float], low: list[float], close: list[float], period: int = 14) -> float:
        """Calculate Average True Range (ATR)."""
        if len(close) < period + 1:
            return 0.0
        
        tr_list = []
        for i in range(1, len(close)):
            h_l = high[i] - low[i]
            h_pc = abs(high[i] - close[i-1])
            l_pc = abs(low[i] - close[i-1])
            tr = max(h_l, h_pc, l_pc)
            tr_list.append(tr)
        
        # Simple moving average of True Range
        return sum(tr_list[-period:]) / period

    def calculate_volatility_regime(self, returns: list[float], window: int = 20) -> float:
        """Determine volatility regime (0 to 1)."""
        if len(returns) < window:
            return 0.5
        
        realized_vol = np.std(returns[-window:]) * math.sqrt(252)
        # Normalize: Assume 0.1 (10%) is low, 0.4 (40%) is high
        normalized_vol = (realized_vol - 0.1) / (0.4 - 0.1)
        return float(np.clip(normalized_vol, 0.0, 1.0))

    def compute_sentiment_score(self, articles: list[GeopoliticalArticle], region: str = "global") -> float:
        """Aggregate sentiment from news articles for a region."""
        relevant_articles = [a for a in articles if a.region == region or a.region == "global"]
        if not relevant_articles:
            return 0.0
        
        # Simple weighted sentiment (in real app, use NLP model)
        total_score = 0.0
        total_weight = 0.0
        
        for a in relevant_articles:
            # Heuristic: titles with 'growth', 'rise', 'recovery' are positive
            # titles with 'sanctions', 'conflict', 'fall' are negative
            score = 0.0
            title = a.title.lower()
            if any(w in title for w in ["rise", "growth", "recovery", "positive", "strong"]):
                score += 0.5
            if any(w in title for w in ["sanctions", "conflict", "fall", "tension", "crisis", "war"]):
                score -= 0.8
            
            total_score += score * a.relevance_score
            total_weight += a.relevance_score
            
        return float(np.clip(total_score / max(0.1, total_weight), -1.0, 1.0))

    def compute_macro_strength(self, indicators: list[MacroIndicator], region: str = "americas") -> float:
        """Compute aggregate macro strength score (-1 to 1)."""
        relevant = [i for i in indicators if i.region == region or i.region == "global"]
        if not relevant:
            return 0.0
        
        score = 0.0
        count = 0
        for i in relevant:
            # Heuristic based on indicator type
            if i.symbol == "FEDFUNDS":
                # High rates can be bearish for stocks, bullish for currency
                score += (5.0 - i.value) / 5.0 # normalized around 5%
            elif i.symbol == "UNRATE":
                score += (5.0 - i.value) / 5.0 # low unemployment is bullish
            elif i.symbol == "T10Y2Y":
                score += i.value # inverted yield curve is bearish
            count += 1
            
        return float(np.clip(score / max(1, count), -1.0, 1.0))

_feature_service: FeatureEngineeringService | None = None

def get_feature_service() -> FeatureEngineeringService:
    global _feature_service
    if _feature_service is None:
        _feature_service = FeatureEngineeringService()
    return _feature_service
