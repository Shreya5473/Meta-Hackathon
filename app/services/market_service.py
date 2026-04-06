"""Market data ingestion service — fetches and persists market data.

Uses the MarketFeedManager cache (Finnhub primary → Synthetic fallback)
so that already-fetched live prices are reused rather than re-requested.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.models.market import MarketData
from app.pipelines.market_feeds import (
    MarketFeedAdapter, DEFAULT_TRACKED_ASSETS,
    get_feed_manager, get_market_feed,
)
from app.repositories.market_repo import MarketDataRepository

logger = get_logger(__name__)


class MarketDataService:
    """Fetches market data from feed adapters and persists to DB.

    Prefers live data from the MarketFeedManager cache; falls back to
    an on-demand adapter fetch for symbols not yet in cache.
    """

    def __init__(
        self,
        market_repo: MarketDataRepository,
        feed: MarketFeedAdapter | None = None,
    ) -> None:
        self.market_repo = market_repo
        self.feed = feed or get_market_feed()

    async def ingest_latest(
        self, symbols: list[str] | None = None
    ) -> int:
        """Fetch latest market data and persist. Returns count of upserted records.

        Uses the MarketFeedManager in-memory cache first (already fetched
        from Finnhub), then falls back to on-demand adapter fetch for any
        symbols not yet cached.
        """
        symbols = symbols or DEFAULT_TRACKED_ASSETS

        # Prefer already-fetched live data from the feed manager
        feed_mgr   = get_feed_manager()
        cached     = {t.symbol: t for t in feed_mgr.get_all()}
        need_fetch = [s for s in symbols if s not in cached]

        ticks = [cached[s] for s in symbols if s in cached]
        if need_fetch:
            fresh = await self.feed.fetch_latest(need_fetch)
            ticks.extend(fresh)

        count = 0
        for tick in ticks:
            md = MarketData(
                id=uuid.uuid4(),
                symbol=tick.symbol,
                asset_class=tick.asset_class,
                region=tick.region,
                ts=tick.ts,
                open=tick.open,
                high=tick.high,
                low=tick.low,
                close=tick.close,
                volume=tick.volume,
                realized_vol=tick.realized_vol,
                return_1d=tick.return_1d,
                return_5d=tick.return_5d,
            )
            await self.market_repo.upsert(md)
            count += 1

        logger.info("market_data_ingested", count=count)
        return count

    async def ingest_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> int:
        """Fetch + persist historical data for one symbol."""
        ticks = await self.feed.fetch_history(symbol, start, end)

        count = 0
        for tick in ticks:
            md = MarketData(
                id=uuid.uuid4(),
                symbol=tick.symbol,
                asset_class=tick.asset_class,
                region=tick.region,
                ts=tick.ts,
                open=tick.open,
                high=tick.high,
                low=tick.low,
                close=tick.close,
                volume=tick.volume,
                realized_vol=tick.realized_vol,
                return_1d=tick.return_1d,
                return_5d=tick.return_5d,
            )
            await self.market_repo.upsert(md)
            count += 1

        logger.info(
            "market_history_ingested",
            symbol=symbol,
            count=count,
        )
        return count
