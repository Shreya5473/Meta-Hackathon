"""Celery ingestion tasks."""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from uuid import uuid4

from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.tasks.ingestion_tasks.run_news_ingestion",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
)
def run_news_ingestion(self: object) -> dict:
    """Ingest news from all configured adapters."""
    return asyncio.get_event_loop().run_until_complete(_async_run_news_ingestion())


async def _async_run_news_ingestion() -> dict:
    from app.core.database import get_db_session
    from app.pipelines.ingestion_adapters import get_adapters
    from app.repositories.event_repo import EventRepository
    from app.repositories.market_repo import AlertRepository
    from app.models.ingestion import IngestionSource, IngestionRun
    from app.services.ingestion_service import IngestionService

    adapters = get_adapters()
    total_new = 0
    total_dup = 0

    for adapter in adapters:
        start = time.monotonic()
        try:
            articles = await adapter.fetch()
            async with get_db_session() as session:
                event_repo = EventRepository(session)
                svc = IngestionService(event_repo)
                new, dup = await svc.process_articles(articles)
                total_new += new
                total_dup += dup
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "ingestion_run_complete",
                source=adapter.name,
                new=new,
                dup=dup,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.error("ingestion_run_failed", source=adapter.name, error=str(exc))

    return {"total_new": total_new, "total_duplicate": total_dup}
