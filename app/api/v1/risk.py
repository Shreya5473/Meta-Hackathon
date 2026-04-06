"""Risk and heatmap endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.gti_repo import GTIRepository
from app.schemas.signal import HeatmapResponse, HeatmapPoint
from app.services.risk_service import RiskService

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/heatmap", response_model=HeatmapResponse)
async def get_risk_heatmap(db: AsyncSession = Depends(get_db)) -> HeatmapResponse:
    gti_repo = GTIRepository(db)
    svc = RiskService(gti_repo)
    result = await svc.get_heatmap()
    
    return HeatmapResponse(
        points=[HeatmapPoint(**p) for p in result["points"]],
        data_as_of=result["data_as_of"]
    )
