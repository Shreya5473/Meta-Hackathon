"""Event repository — deduplication and timeline queries."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select

from app.models.event import Event, EventCluster
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    model = Event

    async def get_by_content_hash(self, content_hash: str) -> Event | None:
        result = await self.session.execute(
            select(Event).where(Event.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def get_timeline(
        self,
        start: datetime,
        end: datetime,
        region: str | None = None,
        limit: int = 500,
    ) -> Sequence[Event]:
        conditions = [Event.occurred_at >= start, Event.occurred_at <= end]
        if region:
            conditions.append(Event.region == region)
        result = await self.session.execute(
            select(Event)
            .where(and_(*conditions))
            .order_by(Event.occurred_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_recent_unprocessed(self, limit: int = 100) -> Sequence[Event]:
        result = await self.session.execute(
            select(Event)
            .where(Event.classification.is_(None))
            .order_by(Event.ingested_at.asc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_active_events(self, since: datetime) -> Sequence[Event]:
        """Events since a cutoff — used by GTI engine for active driver calculation."""
        result = await self.session.execute(
            select(Event)
            .where(
                and_(
                    Event.occurred_at >= since,
                    Event.severity_score.is_not(None),
                )
            )
            .order_by(Event.occurred_at.desc())
        )
        return result.scalars().all()


class EventClusterRepository(BaseRepository[EventCluster]):
    model = EventCluster

    async def get_by_region(self, region: str, limit: int = 50) -> Sequence[EventCluster]:
        result = await self.session.execute(
            select(EventCluster)
            .where(EventCluster.region == region)
            .order_by(EventCluster.updated_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
