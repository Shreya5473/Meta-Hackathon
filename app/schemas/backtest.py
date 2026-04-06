"""Pydantic v2 schemas — Backtesting."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    assets: list[str] = Field(
        default_factory=lambda: ["SPY", "GLD", "USO", "TLT", "XLE", "QQQ", "ITA", "JETS"],
        description="List of asset symbols to backtest",
    )
    lookback_days: int = Field(default=7, ge=1, le=90, description="Days of history to replay")
    asset_meta: dict[str, dict[str, Any]] | None = Field(
        default=None,
        description="Optional per-asset metadata: {symbol: {sector, region, realized_vol}}",
    )


class BacktestMetricsSchema(BaseModel):
    total_signals: int
    buy_signals: int
    sell_signals: int
    hold_signals: int
    signal_accuracy: float = Field(ge=0.0, le=1.0)
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    profit_factor: float
    win_loss_ratio: float
    cumulative_return: float
    calmar_ratio: float
    avg_confidence: float
    avg_vol_prediction: float
    time_period_days: int
    annualized_return: float
    annualized_volatility: float


class BacktestSignalSchema(BaseModel):
    timestamp: datetime
    asset: str
    recommendation: str
    confidence: float
    vol_spike_prob: float
    directional_bias: float
    actual_return: float
    hit: bool
    pnl: float


class AssetBacktestResultSchema(BaseModel):
    asset: str
    metrics: BacktestMetricsSchema
    equity_curve: list[float]
    signals: list[BacktestSignalSchema]


class BacktestResponse(BaseModel):
    start_date: datetime
    end_date: datetime
    overall_metrics: BacktestMetricsSchema
    asset_results: list[AssetBacktestResultSchema]
    gti_path: list[dict[str, Any]]
    summary: str
    not_financial_advice: bool = True


# ── Impact Graph schemas ─────────────────────────────────────────────────────

class ShockPropagationRequest(BaseModel):
    source_country: str = Field(description="ISO-3166 alpha-3 country code")
    event_type: str = Field(description="Event category like military_escalation, sanctions, etc.")
    severity: float = Field(ge=0.0, le=1.0, default=0.7)


class ImpactNodeSchema(BaseModel):
    id: str
    impact_score: float
    path: list[str]
    hops: int


class ShockPropagationResponse(BaseModel):
    source_country: str
    event_type: str
    severity: float
    total_nodes_affected: int
    commodity_impacts: list[ImpactNodeSchema]
    sector_impacts: list[ImpactNodeSchema]
    asset_impacts: list[ImpactNodeSchema]
    country_spillover: list[ImpactNodeSchema]
    not_financial_advice: bool = True


class GraphDataResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class AssetExposureResponse(BaseModel):
    asset: str
    exposures: dict[str, float]


# ── Enhanced Trading Signal schemas ──────────────────────────────────────────

class ReasoningStepSchema(BaseModel):
    step_number: int
    description: str
    evidence: str
    confidence_contribution: float


class EnhancedSignalSchema(BaseModel):
    asset: str
    asset_class: str
    action: str  # BUY / SELL / HOLD
    confidence_pct: float
    uncertainty_pct: float
    reasoning_summary: str
    reasoning_chain: list[ReasoningStepSchema]
    triggering_event: str
    event_category: str
    impact_path: list[str]
    vol_spike_prob: float
    directional_bias: float
    sector_stress: float
    price_direction: str
    expected_magnitude: str
    time_horizon: str
    related_assets: list[str]
    generated_at: datetime


class EnhancedSignalBatchResponse(BaseModel):
    signals: list[EnhancedSignalSchema]
    global_tension_index: float
    event_count: int
    timestamp: datetime
    not_financial_advice: bool = True


# ── WebSocket stats ──────────────────────────────────────────────────────────

class WSStatsResponse(BaseModel):
    total_connections: int
    channels: dict[str, int]
