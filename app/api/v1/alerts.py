"""Alert subscription endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.market_repo import AlertRepository
from app.schemas.health import AlertSubscribeRequest, AlertSubscribeResponse
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/subscribe", response_model=AlertSubscribeResponse, status_code=201)
async def subscribe_alert(
    req: AlertSubscribeRequest,
    db: AsyncSession = Depends(get_db),
) -> AlertSubscribeResponse:
    alert_repo = AlertRepository(db)
    svc = AlertService(alert_repo)
    return await svc.subscribe(req)
