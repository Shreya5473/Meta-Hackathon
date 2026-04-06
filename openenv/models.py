"""GeoTrade OpenEnv — typed Pydantic models.

Observation, Action, and Reward models that satisfy the OpenEnv spec.
All models use Pydantic v2 with full type annotations.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


# ── Sub-components ────────────────────────────────────────────────────────────

class AssetSnapshot(BaseModel):
    """Point-in-time price and risk data for a single tradable asset."""
    symbol: str
    name: str
    asset_class: Literal["forex", "commodity", "equity", "bond"]
    price: float
    daily_change_pct: float = 0.0
    volatility_regime: Literal["LOW", "NORMAL", "HIGH", "EXTREME"] = "NORMAL"
    gti_sensitivity: float = Field(
        default=0.5,
        ge=0.0, le=1.0,
        description="How strongly this asset responds to geopolitical stress (0=immune, 1=very sensitive)",
    )


class GeopoliticalContext(BaseModel):
    """Snapshot of the geopolitical situation."""
    gti_score: float = Field(ge=0.0, le=100.0, description="Geopolitical Tension Index (0=calm, 100=crisis)")
    gti_delta: float = Field(default=0.0, description="Change in GTI since last step")
    region: str
    severity: Literal["low", "medium", "high", "critical"]
    categories: list[str] = Field(description="E.g. ['energy_supply_disruption', 'sanctions']")
    headline: str
    description: str
    news_headlines: list[str] = Field(default_factory=list)
    affected_sectors: list[str] = Field(default_factory=list)


class PortfolioState(BaseModel):
    """Current portfolio snapshot (weights normalised to sum ≤ 1; remainder = cash)."""
    weights: dict[str, float] = Field(description="Asset symbol → portfolio weight [0, 1]")
    cash_pct: float = Field(ge=0.0, le=1.0)
    total_value: float = Field(default=1.0, description="Normalised to 1.0 at episode start")
    unrealized_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_partial: float = 0.0


# ── Observation ───────────────────────────────────────────────────────────────

class GeoTradeObservation(BaseModel):
    """Full observation returned by reset() and step()."""

    task_id: Literal["task_easy", "task_medium", "task_hard"]
    scenario_id: str
    step: int = Field(ge=0)
    max_steps: int

    geopolitical_context: GeopoliticalContext
    market_snapshot: dict[str, AssetSnapshot]
    portfolio: PortfolioState

    prompt: str = Field(description="Natural-language description of what the agent must do this step")
    available_assets: list[str] = Field(description="Symbols the agent may trade this step")

    info: dict[str, Any] = Field(default_factory=dict)


# ── Action ────────────────────────────────────────────────────────────────────

class AssetDecision(BaseModel):
    """Single-asset trading decision."""
    symbol: str
    direction: Literal["BUY", "SELL", "HOLD"]
    weight: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Target portfolio weight for this asset (0–1)",
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class GeoTradeAction(BaseModel):
    """Action submitted to step()."""
    task_id: Literal["task_easy", "task_medium", "task_hard"]
    decisions: list[AssetDecision] = Field(min_length=1)
    primary_signal: str = Field(
        default="",
        description="One-sentence geopolitical interpretation driving all decisions",
    )
    reasoning: str = Field(
        default="",
        description="Full chain-of-thought explanation (used for partial-credit scoring)",
    )


# ── Reward ────────────────────────────────────────────────────────────────────

class RewardComponents(BaseModel):
    """Decomposed reward — each component is [0, 1]."""
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0, description="Correct asset/direction identification")
    risk_management: float = Field(default=0.0, ge=0.0, le=1.0, description="Portfolio risk control")
    opportunity_capture: float = Field(default=0.0, ge=0.0, le=1.0, description="Geopolitical opportunity exploitation")
    constraint_satisfaction: float = Field(default=0.0, ge=0.0, le=1.0, description="Weights sum ≤ 1, per-asset limits respected")
    reasoning_quality: float = Field(default=0.0, ge=0.0, le=1.0, description="Keyword & causal chain quality in reasoning")


class GeoTradeReward(BaseModel):
    """Reward returned by step() — total is a weighted mix of components."""
    total: float = Field(ge=0.0, le=1.0, description="Episode score for this step (0.0–1.0)")
    components: RewardComponents
    partial_progress: float = Field(
        ge=0.0, le=1.0,
        description="Cumulative fraction of task completion (useful for sparse-reward debugging)",
    )
    explanation: str = Field(description="Human-readable breakdown of how total was computed")
    is_terminal: bool = False


# ── Step result (convenience wrapper) ────────────────────────────────────────

class StepResult(BaseModel):
    """Full return value of step()."""
    observation: GeoTradeObservation
    reward: GeoTradeReward
    done: bool
    info: dict[str, Any] = Field(default_factory=dict)


# ── Environment state ─────────────────────────────────────────────────────────

class EnvironmentState(BaseModel):
    """Returned by state() — internal bookkeeping snapshot."""
    task_id: str
    scenario_id: str
    step: int
    done: bool
    cumulative_reward: float
    history: list[dict[str, Any]] = Field(default_factory=list)
    seed: int = 42
