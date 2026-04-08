#!/usr/bin/env python
"""Standalone OpenEnv API server for GeoTrade.

Usage:
    python openenv_server.py --port 8000

This server provides the OpenEnv HTTP API for testing and deployment.
"""
import argparse
import asyncio
import sys
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    print("Install with: pip install fastapi uvicorn pydantic")
    sys.exit(1)

from openenv.environment import GeoTradeEnv
from openenv.models import GeoTradeAction

# ── Data Models ────────────────────────────────────────────────────────────

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


# ── Global State ───────────────────────────────────────────────────────────

_environments: dict[str, Any] = {}
_session_counter = 0


# ── API Routes ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="GeoTrade OpenEnv API",
    description="OpenEnv-compliant API for GeoTrade environment",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.
    
    Returns:
        Status message
    """
    return {"status": "healthy", "service": "openenv-api"}


@app.get("/")
async def root() -> dict[str, object]:
    """Root endpoint for browser sanity check."""
    return {
        "service": "GeoTrade OpenEnv API",
        "status": "ok",
        "docs": "/docs",
        "endpoints": {
            "health": "GET /health",
            "reset": "POST /reset",
            "step": "POST /step",
            "state": "GET /state?session_id=<id>",
            "close": "POST /close?session_id=<id>",
        },
    }


@app.post("/reset", response_model=ResetResponse)
async def reset_environment(request: ResetRequest) -> ResetResponse:
    """Reset the environment and return initial observation.
    
    Args:
        request: ResetRequest with task_id, seed, scenario_idx
        
    Returns:
        ResetResponse with session_id and initial observation
    """
    global _session_counter
    
    try:
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


@app.get("/reset", response_model=ResetResponse)
async def reset_environment_get(
    task_id: str = "task_easy",
    seed: int = 42,
    scenario_idx: int = 0,
) -> ResetResponse:
    """Compatibility reset endpoint for clients that call GET /reset."""
    request = ResetRequest(task_id=task_id, seed=seed, scenario_idx=scenario_idx)
    return await reset_environment(request)


@app.post("/step", response_model=StepResponse)
async def step_environment(request: StepRequest) -> StepResponse:
    """Take a step in the environment.
    
    Args:
        request: StepRequest with session_id and action dict
        
    Returns:
        StepResponse with observation, reward, done, info
    """
    try:
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


@app.post("/close")
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


@app.get("/state")
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GeoTrade OpenEnv API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on file changes")
    
    args = parser.parse_args()
    
    print(f"Starting GeoTrade OpenEnv API server on {args.host}:{args.port}")
    print(f"Docs available at http://{args.host}:{args.port}/docs")
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
