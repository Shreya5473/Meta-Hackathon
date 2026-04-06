"""Market signal repository."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, UTC

from sqlalchemy import and_, select

from app.models.signal import MarketSignal, ModelVersion
from app.repositories.base import BaseRepository


class MarketSignalRepository(BaseRepository[MarketSignal]):
    model = MarketSignal

    async def get_latest_by_region(
        self,
        region: str | None = None,
        timeframe_hours: int = 24,
        limit: int = 200,
    ) -> Sequence[MarketSignal]:
        since = datetime.now(UTC) - timedelta(hours=timeframe_hours)
        conditions = [MarketSignal.ts >= since]
        if region:
            conditions.append(MarketSignal.region == region)
        result = await self.session.execute(
            select(MarketSignal)
            .where(and_(*conditions))
            .order_by(MarketSignal.ts.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_latest_per_symbol(
        self,
        region: str | None = None,
        timeframe_hours: int = 24,
    ) -> Sequence[MarketSignal]:
        """Return single most recent signal per symbol."""
        from sqlalchemy import func
        since = datetime.now(UTC) - timedelta(hours=timeframe_hours)
        subq = (
            select(
                MarketSignal.symbol,
                func.max(MarketSignal.ts).label("max_ts"),
            )
            .where(MarketSignal.ts >= since)
            .group_by(MarketSignal.symbol)
            .subquery()
        )
        conditions = [
            MarketSignal.symbol == subq.c.symbol,
            MarketSignal.ts == subq.c.max_ts,
        ]
        if region:
            conditions.append(MarketSignal.region == region)
        result = await self.session.execute(
            select(MarketSignal).join(subq, and_(*conditions))
        )
        return result.scalars().all()


class ModelVersionRepository(BaseRepository[ModelVersion]):
    model = ModelVersion

    async def get_active_versions(self) -> Sequence[ModelVersion]:
        result = await self.session.execute(
            select(ModelVersion).where(ModelVersion.is_active.is_(True))
        )
        return result.scalars().all()
