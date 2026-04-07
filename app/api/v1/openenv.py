"""OpenEnv API endpoints for the hackathon submission."""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from openenv.environment import GeoTradeEnv, TaskID
from openenv.models import (
    EnvironmentState,
    GeoTradeAction,
    GeoTradeObservation,
    StepResult,
)
from openenv.scenarios import ALL_SCENARIOS
from pydantic import BaseModel

router = APIRouter(prefix="/openenv", tags=["openenv"])

# ── Session registry ──────────────────────────────────────────────────────────

_sessions: dict[str, GeoTradeEnv] = {}
MAX_SESSIONS = 100  # guard against memory exhaustion


def _get_or_create_session(
    session_id: str,
    task_id: TaskID = "task_easy",
    scenario_idx: int = 0,
) -> GeoTradeEnv:
    if session_id not in _sessions:
        if len(_sessions) >= MAX_SESSIONS:
            # Evict oldest session (first key in dict)
            oldest = next(iter(_sessions))
            del _sessions[oldest]
        _sessions[session_id] = GeoTradeEnv(task_id=task_id, scenario_idx=scenario_idx)
    return _sessions[session_id]


# ── Request / response schemas ────────────────────────────────────────────────

class ResetRequest(BaseModel):
    task_id: Literal["task_easy", "task_medium", "task_hard"] = "task_easy"
    scenario_idx: int = 0
    seed: int = 42


class ResetResponse(BaseModel):
    session_id: str
    observation: GeoTradeObservation


class TaskInfo(BaseModel):
    task_id: str
    description: str
    difficulty: str
    max_steps: int
    num_scenarios: int
    observation_space: str
    action_space: str
    scoring: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "env": "GeoTradeEnv"}


@router.get("/tasks", response_model=list[TaskInfo])
async def list_tasks() -> list[TaskInfo]:
    """List available tasks."""
    return [
        TaskInfo(
            task_id="task_easy",
            description="Identify top-3 most impacted assets and their direction (BUY/SELL/HOLD) given a geopolitical event.",
            difficulty="easy",
            max_steps=1,
            num_scenarios=len(ALL_SCENARIOS.get("task_easy", [])),
            observation_space="GeopoliticalContext + 5-asset MarketSnapshot",
            action_space="List of (symbol, direction, weight, confidence) + reasoning",
            scoring="0.45*asset_F1 + 0.45*direction_accuracy + 0.10*reasoning_quality",
        ),
        TaskInfo(
            task_id="task_medium",
            description="Rebalance a 6-asset portfolio to hedge geopolitical risk while capturing opportunities.",
            difficulty="medium",
            max_steps=1,
            num_scenarios=len(ALL_SCENARIOS.get("task_medium", [])),
            observation_space="GeopoliticalContext + 6-asset MarketSnapshot + PortfolioState",
            action_space="Target weights for each asset (sum ≤ 1.0, max 45% per asset) + reasoning",
            scoring="0.40*opportunity + 0.25*risk_mgmt + 0.20*constraints + 0.15*reasoning",
        ),
        TaskInfo(
            task_id="task_hard",
            description="Manage a portfolio through a 5-step evolving geopolitical crisis, maximising risk-adjusted returns.",
            difficulty="hard",
            max_steps=5,
            num_scenarios=len(ALL_SCENARIOS.get("task_hard", [])),
            observation_space="Evolving GeopoliticalContext + 6-asset MarketSnapshot + PortfolioState (per step)",
            action_space="Per-step: target weights + direction signals + reasoning chain",
            scoring="0.35*prediction_accuracy + 0.40*pnl_vs_benchmark + 0.25*drawdown_control",
        ),
    ]


@router.post("/reset", response_model=ResetResponse)
async def reset(body: ResetRequest) -> ResetResponse:
    """Reset the environment and start a new episode."""
    session_id = str(uuid.uuid4())
    env = _get_or_create_session(session_id, task_id=body.task_id, scenario_idx=body.scenario_idx)
    obs = env.reset(seed=body.seed)
    return ResetResponse(session_id=session_id, observation=obs)


@router.post("/step", response_model=StepResult)
async def step(
    action: GeoTradeAction,
    session_id: str = Query(..., description="Session ID returned by /reset"),
) -> StepResult:
    """Submit an action and advance the environment by one step."""
    if session_id not in _sessions:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Call /reset first.",
        )
    env = _sessions[session_id]
    try:
        result = env.step(action)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/state", response_model=EnvironmentState)
async def get_state(
    session_id: str = Query(..., description="Session ID returned by /reset"),
) -> EnvironmentState:
    """Return the current internal state of the environment."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return _sessions[session_id].state()


@router.delete("/session")
async def delete_session(
    session_id: str = Query(..., description="Session to delete"),
) -> dict[str, str]:
    """Clean up a session."""
    _sessions.pop(session_id, None)
    return {"status": "deleted", "session_id": session_id}
