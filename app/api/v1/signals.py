"""Signal endpoints — standard + enhanced with reasoning chains."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import _make_cache_key, cache_get, cache_set
from app.core.database import get_db
from app.repositories.gti_repo import GTIRepository
from app.repositories.market_repo import MarketDataRepository
from app.repositories.signal_repo import MarketSignalRepository
from app.schemas.signal import SignalAssetsResponse
from app.services.signal_service import MarketSignalService

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/assets", response_model=SignalAssetsResponse)
async def get_asset_signals(
    region: str | None = Query(default=None, description="Filter by region"),
    timeframe: Literal["1h", "4h", "24h", "7d", "30d"] = Query(default="24h"),
    db: AsyncSession = Depends(get_db),
) -> SignalAssetsResponse:
    cache_key = _make_cache_key("signals_assets", region or "all", timeframe)
    cached = await cache_get(cache_key)
    if cached:
        return SignalAssetsResponse(**cached)

    signal_repo = MarketSignalRepository(db)
    gti_repo = GTIRepository(db)
    market_repo = MarketDataRepository(db)
    svc = MarketSignalService(signal_repo, gti_repo, market_repo)
    result = await svc.get_signals(region=region, timeframe=timeframe)

    await cache_set(cache_key, result.model_dump(mode="json"), ttl=45)
    return result


@router.get("/enhanced")
async def get_enhanced_signals(
    region: str | None = Query(default=None, description="Filter by region"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get enhanced AI trading signals with full reasoning chains,
    impact graph paths, and explainable recommendations."""
    cache_key = _make_cache_key("signals_enhanced", region or "all")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    signal_repo = MarketSignalRepository(db)
    gti_repo = GTIRepository(db)
    market_repo = MarketDataRepository(db)
    svc = MarketSignalService(signal_repo, gti_repo, market_repo)
    result = await svc.get_enhanced_signals(region=region)

    await cache_set(cache_key, result, ttl=60)
    return result
