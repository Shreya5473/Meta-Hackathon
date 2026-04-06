"""Pydantic v2 schemas — Portfolio evaluation."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class Holding(BaseModel):
    symbol: str
    weight: float = Field(gt=0.0, le=1.0)
    sector: str | None = None
    region: str | None = None


class PortfolioEvalRequest(BaseModel):
    holdings: list[Holding] = Field(min_length=1, max_length=500)
    include_scenario: bool = False
    scenario_conflict_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    scenario_duration_hours: int = Field(default=24, ge=1, le=720)

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "PortfolioEvalRequest":
        total = sum(h.weight for h in self.holdings)
        if not (0.98 <= total <= 1.02):
            msg = f"Portfolio weights must sum to ~1.0, got {total:.4f}"
            raise ValueError(msg)
        return self


class SectorExposure(BaseModel):
    sector: str
    weight: float


class RegionExposure(BaseModel):
    region: str
    weight: float


class PnLRange(BaseModel):
    p05: float   # 5th percentile (worst)
    p25: float   # 25th
    p50: float   # median
    p75: float   # 75th
    p95: float   # 95th (best)


class DrawdownBucket(BaseModel):
    bucket: str  # LOW/MODERATE/ELEVATED/HIGH/SEVERE
    max_drawdown_estimate: float


class PortfolioEvalResponse(BaseModel):
    expected_stress_impact: float = Field(ge=0.0, le=1.0)
    simulated_pnl_range: PnLRange
    drawdown_risk: DrawdownBucket
    sector_exposure: list[SectorExposure]
    region_exposure: list[RegionExposure]
    scenario_adjusted: bool
    model_version: str
    pipeline_version: str
    data_as_of: str
    not_financial_advice: bool = True


# ── Cart / anonymous-email portfolio ─────────────────────────────────────────

class CartHolding(BaseModel):
    """A single position in the user's cart portfolio."""
    symbol: str = Field(min_length=1, max_length=20)
    label: str = ""
    weight: float = Field(default=1.0, gt=0.0)
    sector: str | None = None
    region: str | None = None


class CartSaveRequest(BaseModel):
    """Save (upsert) portfolio for an email-identified user."""
    email: EmailStr
    holdings: list[CartHolding] = Field(min_length=0, max_length=100)
    name: str = Field(default="My Portfolio", max_length=100)


class CartResponse(BaseModel):
    """Response for GET /portfolio/cart."""
    email: str
    holdings: list[CartHolding]
    name: str
    updated_at: datetime | None = None


class CartHoldingRisk(BaseModel):
    """Per-asset risk data in portfolio risk response."""
    symbol: str
    label: str
    weight: float
    sector: str | None
    region: str | None
    vol_spike_prob: float | None = None    # 0–1, None if data unavailable
    directional_bias: float | None = None  # -1..1
    gti_exposure: float | None = None      # weighted GTI contribution
    recommendation: str | None = None      # BUY/SELL/HOLD
    data_status: str = "ok"               # "ok" | "data_unavailable"


class PortfolioRiskRequest(BaseModel):
    """Request portfolio risk analysis."""
    email: EmailStr


class PortfolioRiskResponse(BaseModel):
    """Aggregated portfolio risk response."""
    email: str
    holdings: list[CartHoldingRisk]
    overall_gti_exposure: float
    overall_vol_risk: float
    risk_classification: str  # LOW / MODERATE / ELEVATED / HIGH
    top_risk_driver: str | None = None
    not_financial_advice: bool = True


# ── Portfolio Persistence & Heatmap ──────────────────────────────────────────

class UserPortfolioSaved(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    # [{"symbol": "SPY", "weight": 0.6, "sector": "equity", "region": "americas"}]
    holdings: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime | None


class UserPortfolioCreate(BaseModel):
    name: str
    description: str | None = None
    holdings: list[dict[str, Any]]


class SimulationSnapshotShare(BaseModel):
    id: UUID
    share_url: str
    summary: str
    created_at: datetime



# -- Trade Execution & P&L ---------------------------------------------------

class TradeExecuteRequest(BaseModel):
    """Request to run signal evaluation + execute trades for a portfolio."""
    email: EmailStr
    dry_run: bool = Field(
        default=True,
        description="If True, evaluate signals but do NOT place real orders",
    )


class TradeDecisionOut(BaseModel):
    """Result of one trade decision (buy / sell / hold)."""
    symbol: str
    action: str
    reason: str
    status: str
    broker: str
    quantity: float | None = None
    fill_price: float | None = None
    order_id: str | None = None
    signal_vol_spike: float | None = None
    signal_bias: float | None = None
    recommendation: str | None = None
    note: str = ""
    ts: str


class TradeExecuteResponse(BaseModel):
    email: str
    decisions: list[TradeDecisionOut]
    executed: int
    dry_run: bool


class TradeLogEntry(BaseModel):
    """A single row from trade_log for P&L display."""
    id: UUID
    ts: datetime
    symbol: str
    action: str
    quantity: float | None = None
    price: float | None = None
    signal_vol_spike: float | None = None
    signal_bias: float | None = None
    recommendation: str | None = None
    order_id: str | None = None
    status: str | None = None
    broker: str | None = None
    pnl: float | None = None
    note: str | None = None

    class Config:
        from_attributes = True


class PnLSummary(BaseModel):
    total_trades: int
    buys: int
    sells: int
    holds: int
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float


class PnLResponse(BaseModel):
    email: str
    summary: PnLSummary
    trades: list[TradeLogEntry]
    as_of: datetime
