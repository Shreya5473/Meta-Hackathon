"""Scenario simulation endpoint."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import build_audit_meta
from app.core.database import get_db
from app.pipelines.gti_engine import get_gti_engine
from app.pipelines.market_model import get_impact_model
from app.pipelines.simulators import ScenarioShock, ScenarioSimulator
from app.repositories.gti_repo import GTIRepository
from app.repositories.persistence_repo import SimulationSnapshotRepository
from app.services.persistence_service import SharingService
from app.schemas.portfolio import SimulationSnapshotShare
from app.schemas.scenario import (
    AssetStressTrajectory,
    GTITrajectoryPoint,
    ScenarioParams,
    ScenarioResponse,
)

router = APIRouter(prefix="/simulate", tags=["simulation"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/scenario", response_model=ScenarioResponse)
async def simulate_scenario(
    params: ScenarioParams,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    t0 = time.monotonic()

    # Fetch current GTI as baseline
    gti_repo = GTIRepository(db)
    gti_snap = await gti_repo.get_latest(params.region)
    base_gti = gti_snap.gti_value if gti_snap else 25.0

    shock = ScenarioShock(
        conflict_intensity=params.conflict_intensity,
        sanctions_level=params.sanctions_level,
        oil_supply_disruption=params.oil_supply_disruption,
        cyber_risk=params.cyber_risk,
        duration_hours=params.duration_hours,
        region=params.region,
    )

    sim = ScenarioSimulator(get_gti_engine(), get_impact_model())
    result = sim.simulate(shock, base_gti=base_gti, assets=params.assets)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    audit = build_audit_meta()

    return ScenarioResponse(
        scenario=params,
        gti_path=[
            GTITrajectoryPoint(
                hour=p.hour, gti_value=p.gti_value, confidence=p.confidence
            )
            for p in result.gti_path
        ],
        asset_trajectories=[
            AssetStressTrajectory(
                symbol=t.symbol,
                vol_spike_prob_path=t.vol_spike_prob_path,
                directional_bias_path=t.directional_bias_path,
                stress_peak=t.stress_peak,
                stress_mean=t.stress_mean,
            )
            for t in result.asset_trajectories
        ],
        aggregate_stress_peak=result.aggregate_stress_peak,
        aggregate_stress_mean=result.aggregate_stress_mean,
        simulation_duration_hours=params.duration_hours,
        **audit,
    )


@router.post("/share", response_model=SimulationSnapshotShare, status_code=201)
async def share_simulation(
    snapshot_type: str,
    params: dict,
    results: dict,
    db: AsyncSession = Depends(get_db)
):
    """Save a scenario/portfolio result to the database for sharing."""
    repo = SimulationSnapshotRepository(db)
    svc = SharingService(repo)
    snap = await svc.create_snapshot(snapshot_type, params, results)
    
    return SimulationSnapshotShare(
        id=snap.id,
        share_url=f"https://geotrade.ai/share/{snap.id}",
        summary=snap.share_summary,
        created_at=snap.created_at
    )
