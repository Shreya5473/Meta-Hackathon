"""GTI endpoints."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, _make_cache_key
from app.core.config import get_settings
from app.core.database import get_db
from app.repositories.event_repo import EventRepository
from app.repositories.gti_repo import GTIRepository
from app.schemas.gti import GTICurrentResponse, GTIHistoryResponse
from app.services.gti_service import GTIService

router = APIRouter(prefix="/gti", tags=["gti"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/current", response_model=GTICurrentResponse)
async def get_current_gti(
    region: str = Query(default="global", description="Region code"),
    db: AsyncSession = Depends(get_db),
) -> GTICurrentResponse:
    settings = get_settings()
    cache_key = _make_cache_key("gti_current", region)
    cached = await cache_get(cache_key)
    if cached:
        return GTICurrentResponse(**cached)

    gti_repo = GTIRepository(db)
    event_repo = EventRepository(db)
    svc = GTIService(gti_repo, event_repo)
    result = await svc.get_current(region=region)

    await cache_set(cache_key, result.model_dump(mode="json"), ttl=60)
    return result


@router.get("/history", response_model=GTIHistoryResponse)
async def get_gti_history(
    start: datetime = Query(
        default_factory=lambda: datetime.now(UTC) - timedelta(days=7),
        description="Start datetime (ISO 8601)",
    ),
    end: datetime = Query(
        default_factory=lambda: datetime.now(UTC),
        description="End datetime (ISO 8601)",
    ),
    region: str = Query(default="global"),
    db: AsyncSession = Depends(get_db),
) -> GTIHistoryResponse:
    # Ensure timezone-aware
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)

    cache_key = _make_cache_key("gti_history", region, str(start.date()), str(end.date()))
    cached = await cache_get(cache_key)
    if cached:
        return GTIHistoryResponse(**cached)

    gti_repo = GTIRepository(db)
    event_repo = EventRepository(db)
    svc = GTIService(gti_repo, event_repo)
    result = await svc.get_history(start=start, end=end, region=region)

    await cache_set(cache_key, result.model_dump(mode="json"), ttl=300)
    return result
