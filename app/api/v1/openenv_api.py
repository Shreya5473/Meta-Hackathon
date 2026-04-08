"""OpenEnv API routes for GeoTrade environment.

Provides HTTP endpoints for the OpenEnv standard:
  POST /reset      → Reset the environment and return initial observation
  POST /step       → Take an action step and return observation + reward
  POST /close      → Close the current episode (cleanup)
  GET  /state      → Get current environment state
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(tags=["openenv"])

# Lazy imports to avoid dependency issues
def _get_env_classes():
    from openenv.environment import GeoTradeEnv
    from openenv.models import GeoTradeAction, GeoTradeObservation, StepResult
    return GeoTradeEnv, GeoTradeAction, GeoTradeObservation, StepResult

# Global environment instances (session management)
_environments: dict[str, Any] = {}
_session_counter = 0


class ResetRequest(BaseModel):
    """Request body for /reset endpoint."""
    task_id: str = "task_easy"
    seed: int = 42
    scenario_idx: int = 0


class ResetResponse(BaseModel):
    """Response body for /reset endpoint."""
    session_id: str
    observation: dict[str, Any]


class StepRequest(BaseModel):
    """Request body for /step endpoint."""
    session_id: str
    action: dict[str, Any]


class StepResponse(BaseModel):
    """Response body for /step endpoint."""
    observation: dict[str, Any]
    reward: dict[str, Any]
    done: bool
    info: dict[str, Any] = {}


class StateResponse(BaseModel):
    """Response body for /state endpoint."""
    session_id: str
    observation: dict[str, Any]
    done: bool


@router.post("/reset", response_model=ResetResponse)
async def reset_environment(request: ResetRequest) -> ResetResponse:
    """Reset the environment and return initial observation.
    
    Args:
        request: ResetRequest with task_id, seed, scenario_idx
        
    Returns:
        ResetResponse with session_id and initial observation
    """
    global _session_counter
    
    try:
        GeoTradeEnv, _, _, _ = _get_env_classes()
        
        # Create new environment instance
        task_id = request.task_id
        if task_id not in ("task_easy", "task_medium", "task_hard"):
            raise ValueError(f"Invalid task_id: {task_id}")
        
        env = GeoTradeEnv(task_id=task_id, scenario_idx=request.scenario_idx)
        obs = env.reset(seed=request.seed)
        
        # Store environment with session ID
        session_id = f"session_{_session_counter}"
        _session_counter += 1
        _environments[session_id] = env
        
        return ResetResponse(
            session_id=session_id,
            observation=obs.model_dump()
        )
    
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Reset failed: {str(exc)}")


@router.get("/reset", response_model=ResetResponse)
async def reset_environment_get(
    task_id: str = "task_easy",
    seed: int = 42,
    scenario_idx: int = 0,
) -> ResetResponse:
    """Compatibility reset endpoint for clients that call GET /reset.

    This mirrors POST /reset behavior with query parameters.
    """
    request = ResetRequest(task_id=task_id, seed=seed, scenario_idx=scenario_idx)
    return await reset_environment(request)


@router.post("/step", response_model=StepResponse)
async def step_environment(request: StepRequest) -> StepResponse:
    """Take a step in the environment.
    
    Args:
        request: StepRequest with session_id and action dict
        
    Returns:
        StepResponse with observation, reward, done, info
    """
    try:
        _, GeoTradeAction, _, _ = _get_env_classes()
        
        # Get environment from session
        if request.session_id not in _environments:
            raise HTTPException(status_code=404, detail=f"Session not found: {request.session_id}")
        
        env = _environments[request.session_id]
        
        # Parse and validate action
        try:
            action = GeoTradeAction(**request.action)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid action: {str(e)}")
        
        # Execute step
        result = env.step(action)
        
        return StepResponse(
            observation=result.observation.model_dump(),
            reward=result.reward.model_dump() if result.reward else {},
            done=result.done,
            info=result.info or {}
        )
    
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Step failed: {str(exc)}")


@router.post("/close")
async def close_environment(session_id: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Close an environment session.
    
    Args:
        session_id: The session ID to close
        
    Returns:
        Success message
    """
    if session_id not in _environments:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    # Clean up environment (remove from dict)
    def cleanup():
        if session_id in _environments:
            del _environments[session_id]
    
    background_tasks.add_task(cleanup)
    
    return {"status": "closed", "session_id": session_id}


@router.get("/state")
async def get_environment_state(session_id: str) -> StateResponse:
    """Get the current state of an environment.
    
    Args:
        session_id: The session ID
        
    Returns:
        StateResponse with current observation and done flag
    """
    if session_id not in _environments:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    env = _environments[session_id]
    
    # Rebuild observation from current state
    obs = env._build_observation() if hasattr(env, '_build_observation') else None
    
    if obs is None:
        raise HTTPException(status_code=500, detail="Could not retrieve current observation")
    
    return StateResponse(
        session_id=session_id,
        observation=obs.model_dump(),
        done=env._done
    )


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for the OpenEnv API.
    
    Returns:
        Status message
    """
    return {"status": "healthy", "service": "openenv-api"}

