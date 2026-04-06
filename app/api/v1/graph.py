"""Impact Graph endpoints — shock propagation and graph data."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.backtest import (
    AssetExposureResponse,
    GraphDataResponse,
    ImpactNodeSchema,
    ShockPropagationRequest,
    ShockPropagationResponse,
)
from app.services.graph_service import ImpactGraphService

router = APIRouter(prefix="/graph", tags=["impact-graph"])

_svc = ImpactGraphService()


@router.get("/data", response_model=GraphDataResponse)
async def get_graph_data() -> GraphDataResponse:
    """Return full graph structure for visualization."""
    data = _svc.get_graph_data()
    return GraphDataResponse(nodes=data["nodes"], edges=data["edges"])


@router.post("/propagate", response_model=ShockPropagationResponse)
async def propagate_shock(req: ShockPropagationRequest) -> ShockPropagationResponse:
    """Propagate a geopolitical shock through the impact graph."""
    result = _svc.propagate_shock(
        source_country=req.source_country,
        event_type=req.event_type,
        severity=req.severity,
    )
    return ShockPropagationResponse(
        source_country=result["source_country"],
        event_type=result["event_type"],
        severity=result["severity"],
        total_nodes_affected=result["total_nodes_affected"],
        commodity_impacts=[ImpactNodeSchema(**ci) for ci in result["commodity_impacts"]],
        sector_impacts=[ImpactNodeSchema(**si) for si in result["sector_impacts"]],
        asset_impacts=[ImpactNodeSchema(**ai) for ai in result["asset_impacts"]],
        country_spillover=[ImpactNodeSchema(**cs) for cs in result["country_spillover"]],
    )


@router.get("/exposure/{asset_id}", response_model=AssetExposureResponse)
async def get_asset_exposure(asset_id: str) -> AssetExposureResponse:
    """Get country/commodity exposure for a given asset."""
    exposures = _svc.get_asset_exposure(asset_id)
    return AssetExposureResponse(asset=asset_id, exposures=exposures)
