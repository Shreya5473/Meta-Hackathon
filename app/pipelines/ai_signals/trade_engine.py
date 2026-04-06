"""Trade construction and confidence engines for AI Signals Engine.

Computes trade setups (Entry, SL, TP, R/R, ATR, Max Position Size) and
calculates mathematically derived confidence scores.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.pipelines.feature_engineering import EnhancedAssetFeatures
from app.pipelines.ai_signals.multi_model_engine import ModelOutput
from app.core.logging import get_logger

logger = get_logger(__name__)

@dataclass
class TradeSetup:
    entry: float
    stop_loss: float
    target: float
    risk_reward: float
    atr: float
    max_position: float
    confidence: float  # 0 to 100

class TradeEngine:
    def __init__(self, risk_per_trade: float = 0.02, account_balance: float = 100000.0) -> None:
        self.risk_per_trade = risk_per_trade  # 2% of account
        self.account_balance = account_balance

    def calculate_confidence(self, model_prob: float, features: EnhancedAssetFeatures) -> float:
        """Mathematically derived confidence:
        (model_probability × 0.5) + (signal_alignment × 0.3) + (data_quality × 0.2)
        """
        # Signal alignment: Agreement between sentiment and macro
        alignment = 0.5
        if features.sentiment_score * features.macro_strength_score > 0:
            alignment += 0.3
        else:
            alignment -= 0.2
        
        # Data quality: Heuristic based on freshness (could use ts in real app)
        data_quality = 0.9 # High freshness for live feed
        
        confidence = (model_prob * 0.5) + (alignment * 0.3) + (data_quality * 0.2)
        return float(max(0, min(100, confidence * 100)))

    def construct_trade(self, features: EnhancedAssetFeatures, model_output: ModelOutput) -> TradeSetup:
        """Build trade setup based on volatility and direction."""
        entry = features.price
        atr = features.atr
        
        # Stop loss based on ATR multiplier (1.5x to 3x depending on volatility)
        sl_multiplier = 2.0
        if model_output.volatility == "HIGH":
            sl_multiplier = 3.0
        elif model_output.volatility == "LOW":
            sl_multiplier = 1.5
            
        # Target based on predicted range and minimum 2:1 R/R
        if model_output.direction == "BUY":
            stop_loss = entry - (atr * sl_multiplier)
            target = entry + (atr * sl_multiplier * 2.5) # Minimum 2.5x risk
        elif model_output.direction == "SELL":
            stop_loss = entry + (atr * sl_multiplier)
            target = entry - (atr * sl_multiplier * 2.5)
        else:
            # HOLD - dummy values
            stop_loss = entry * 0.95
            target = entry * 1.05
            
        risk = abs(entry - stop_loss)
        reward = abs(target - entry)
        rr = reward / max(0.0001, risk)
        
        # Max Position Size calculation
        # Risk amount = Balance * RiskPerTrade
        # PosSize = RiskAmount / RiskPerPoint
        risk_amount = self.account_balance * self.risk_per_trade
        # Adjust risk by confidence
        confidence_factor = model_output.direction_prob
        max_pos = (risk_amount * confidence_factor) / max(0.0001, risk)
        
        confidence = self.calculate_confidence(model_output.direction_prob, features)
        
        return TradeSetup(
            entry=float(entry),
            stop_loss=float(stop_loss),
            target=float(target),
            risk_reward=float(rr),
            atr=float(atr),
            max_position=float(max_pos),
            confidence=float(confidence)
        )

_trade_engine: TradeEngine | None = None

def get_trade_engine() -> TradeEngine:
    global _trade_engine
    if _trade_engine is None:
        _trade_engine = TradeEngine()
    return _trade_engine
