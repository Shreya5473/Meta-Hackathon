"""Pydantic v2 schemas — Market signals."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AssetSignalSchema(BaseModel):
    symbol: str
    asset: str | None = None  # Alias for symbol for frontend compatibility
    region: str
    sector: str | None = None
    vol_spike_prob_24h: float = Field(ge=0.0, le=1.0)
    directional_bias: float = Field(ge=-1.0, le=1.0)
    sector_stress: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    recommendation: Literal["Buy", "Sell", "Hold", "BUY", "SELL", "HOLD"]
    signal: str | None = None  # Alias for recommendation for frontend compatibility
    
    # New fields requested for AI Signals Engine
    confidence: float | None = None  # 0-100
    bullish_strength: float | None = None  # 0-100%
    bearish_strength: float | None = None  # 0-100%
    volatility: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    triggering_event: str | None = None
    
    # Trade setup
    entry: float | None = None
    stop_loss: float | None = None
    target: float | None = None
    risk_reward: float | None = None
    atr: float | None = None
    max_position: float | None = None
    
    reasoning: str | None = None
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    model_version: str
    ts: datetime

    def model_post_init(self, __context):
        if self.asset is None:
            self.asset = self.symbol
        if self.signal is None:
            self.signal = self.recommendation.upper()
        if self.confidence is None:
            self.confidence = self.confidence_score * 100


class SignalAssetsResponse(BaseModel):
    region: str | None
    timeframe: str
    signals: list[AssetSignalSchema]
    count: int
    model_version: str
    pipeline_version: str
    data_as_of: str
    not_financial_advice: bool = True


# ── Heatmap ──────────────────────────────────────────────────────────────────

class HeatmapPoint(BaseModel):
    country_iso: str
    risk_score: float  # 0..100
    gti_delta: float
    top_driver: str | None = None


class HeatmapResponse(BaseModel):
    points: list[HeatmapPoint]
    data_as_of: datetime
    not_financial_advice: bool = True
