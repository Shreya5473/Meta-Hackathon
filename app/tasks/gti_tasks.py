"""Celery GTI computation tasks."""
from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.tasks.gti_tasks.compute_gti_all_regions",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def compute_gti_all_regions(self: object) -> dict:
    return asyncio.get_event_loop().run_until_complete(_async_compute_gti())


async def _async_compute_gti() -> dict:
    from app.core.database import get_db_session
    from app.repositories.event_repo import EventRepository
    from app.repositories.gti_repo import GTIRepository
    from app.services.gti_service import GTIService

    async with get_db_session() as session:
        gti_repo = GTIRepository(session)
        event_repo = EventRepository(session)
        svc = GTIService(gti_repo, event_repo)
        await svc.compute_all_regions()

    logger.info("gti_all_regions_computed")
    return {"status": "ok"}
