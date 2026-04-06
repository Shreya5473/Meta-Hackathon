"""Celery market data ingestion tasks."""
from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    name="app.tasks.market_tasks.ingest_market_data",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def ingest_market_data(self: object) -> dict:
    """Ingest latest market data for all tracked assets."""
    return asyncio.get_event_loop().run_until_complete(_async_ingest_market())


async def _async_ingest_market() -> dict:
    from app.core.database import get_db_session
    from app.repositories.market_repo import MarketDataRepository
    from app.services.market_service import MarketDataService

    async with get_db_session() as session:
        repo = MarketDataRepository(session)
        svc = MarketDataService(repo)
        count = await svc.ingest_latest()

    logger.info("market_data_ingested", count=count)
    return {"count": count}


@celery_app.task(
    name="app.tasks.market_tasks.ingest_paper_trading_prices",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def ingest_paper_trading_prices(self: object) -> dict:
    """Fetch live prices from OANDA and CCXT and persist to live_price_ticks."""
    return asyncio.get_event_loop().run_until_complete(_async_paper_trading_feed())


async def _async_paper_trading_feed() -> dict:
    from app.pipelines.market_data import PaperTradingFeed

    feed = PaperTradingFeed()
    result = await feed.run_once()
    logger.info("paper_trading_feed_done", **result)
    return result
