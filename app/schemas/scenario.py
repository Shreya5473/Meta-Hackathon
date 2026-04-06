"""Pydantic v2 schemas — Scenario simulation."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScenarioParams(BaseModel):
    conflict_intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    sanctions_level: float = Field(default=0.0, ge=0.0, le=1.0)
    oil_supply_disruption: float = Field(default=0.0, ge=0.0, le=1.0)
    cyber_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    duration_hours: int = Field(default=24, ge=1, le=720)
    region: str = Field(default="global")
    assets: list[str] = Field(default_factory=lambda: ["SPY", "GLD", "USO", "TLT"])


class GTITrajectoryPoint(BaseModel):
    hour: int
    gti_value: float
    confidence: float


class AssetStressTrajectory(BaseModel):
    symbol: str
    vol_spike_prob_path: list[float]
    directional_bias_path: list[float]
    stress_peak: float
    stress_mean: float


class ScenarioResponse(BaseModel):
    scenario: ScenarioParams
    gti_path: list[GTITrajectoryPoint]
    asset_trajectories: list[AssetStressTrajectory]
    aggregate_stress_peak: float
    aggregate_stress_mean: float
    simulation_duration_hours: int
    model_version: str
    pipeline_version: str
    data_as_of: str
    not_financial_advice: bool = True
