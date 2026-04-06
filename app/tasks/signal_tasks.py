"""Celery signal computation tasks — with WebSocket broadcast support."""
from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.tasks.signal_tasks.compute_all_signals",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def compute_all_signals(self: object) -> dict:
    return asyncio.get_event_loop().run_until_complete(_async_compute_signals())


async def _async_compute_signals() -> dict:
    from app.core.database import get_db_session
    from app.repositories.gti_repo import GTIRepository
    from app.repositories.market_repo import MarketDataRepository
    from app.repositories.signal_repo import MarketSignalRepository
    from app.services.signal_service import MarketSignalService

    async with get_db_session() as session:
        signal_repo = MarketSignalRepository(session)
        gti_repo = GTIRepository(session)
        market_repo = MarketDataRepository(session)
        svc = MarketSignalService(signal_repo, gti_repo, market_repo)
        await svc._compute_signals()

    logger.info("signals_computed")
    return {"status": "ok"}


@celery_app.task(
    name="app.tasks.signal_tasks.broadcast_ws_updates",
    bind=True,
    max_retries=1,
)
def broadcast_ws_updates(self: object) -> dict:
    """Broadcast latest GTI and signal data to WebSocket clients."""
    return asyncio.get_event_loop().run_until_complete(_async_broadcast())


async def _async_broadcast() -> dict:
    from app.core.database import get_db_session
    from app.core.websocket import get_ws_manager
    from app.repositories.gti_repo import GTIRepository

    manager = get_ws_manager()

    # Only broadcast if there are connected clients
    if manager.total_connections == 0:
        return {"status": "no_clients"}

    async with get_db_session() as session:
        gti_repo = GTIRepository(session)

        # Broadcast GTI for all regions
        regions = ["global", "middle_east", "europe", "asia_pacific", "americas", "africa"]
        for region in regions:
            snap = await gti_repo.get_latest(region)
            if snap:
                await manager.broadcast_gti_update(
                    region=snap.region,
                    gti_value=snap.gti_value,
                    gti_delta=snap.gti_delta_1h,
                    confidence=snap.confidence,
                )

    logger.debug("ws_broadcast_complete", connections=manager.total_connections)
    return {"status": "ok", "connections": manager.total_connections}
