"""AI reasoning engine for AI Signals Engine.

Generates human-readable, structured explanations for trading signals,
combining geopolitical events, macro strength, and market sentiment.
"""
from __future__ import annotations

from typing import Any
from app.pipelines.feature_engineering import EnhancedAssetFeatures
from app.pipelines.ai_signals.multi_model_engine import ModelOutput
from app.core.logging import get_logger

logger = get_logger(__name__)

class ReasoningEngine:
    def __init__(self) -> None:
        pass

    def generate_reasoning(self, features: EnhancedAssetFeatures, model_output: ModelOutput, triggering_event: str | None = None) -> str:
        """Generate human-readable explanation of WHY the signal exists."""
        direction = model_output.direction
        vol = model_output.volatility
        sentiment = features.sentiment_score
        macro = features.macro_strength_score
        
        # Rule-based logic for explanation
        reasoning = []
        
        # 1. Start with the overall direction and sentiment
        if direction == "BUY":
            if sentiment > 0.2:
                reasoning.append(f"Strong bullish sentiment (score: {sentiment:.2f})")
            else:
                reasoning.append("Bullish momentum building despite neutral sentiment")
        elif direction == "SELL":
            if sentiment < -0.2:
                reasoning.append(f"Bearish sentiment (score: {sentiment:.2f})")
            else:
                reasoning.append("Bearish pressure increasing")
        else:
            reasoning.append("Consolidation phase detected")

        # 2. Add macro and geopolitical context
        if triggering_event:
            reasoning.append(f"triggered by '{triggering_event}'")
            
        if abs(macro) > 0.3:
            macro_type = "positive" if macro > 0 else "negative"
            reasoning.append(f"supported by {macro_type} macro indicators (score: {macro:.2f})")
            
        # 3. Add technical context
        if features.rsi > 0.7:
            reasoning.append("RSI shows overbought conditions")
        elif features.rsi < 0.3:
            reasoning.append("RSI shows oversold conditions")
            
        if vol == "HIGH":
            reasoning.append("with high volatility expectations")
            
        # Join and format
        if not reasoning:
            return "Market conditions are currently balanced with no significant bias."
            
        explanation = " ".join(reasoning) + "."
        # Capitalize first letter
        return explanation[0].upper() + explanation[1:]

_reasoning_engine: ReasoningEngine | None = None

def get_reasoning_engine() -> ReasoningEngine:
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine()
    return _reasoning_engine
