"""Events timeline endpoint."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import build_audit_meta
from app.core.database import get_db
from app.repositories.event_repo import EventRepository
from app.schemas.event import EventSchema, EventTimelineResponse

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/timeline", response_model=EventTimelineResponse)
async def get_events_timeline(
    start: datetime = Query(
        default_factory=lambda: datetime.now(UTC) - timedelta(days=3),
    ),
    end: datetime = Query(default_factory=lambda: datetime.now(UTC)),
    region: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    db: AsyncSession = Depends(get_db),
) -> EventTimelineResponse:
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)

    event_repo = EventRepository(db)
    events = await event_repo.get_timeline(start=start, end=end, region=region, limit=limit)

    audit = build_audit_meta()
    return EventTimelineResponse(
        start=start,
        end=end,
        events=[
            EventSchema(
                id=e.id,
                title=e.title,
                source=e.source,
                region=e.region,
                occurred_at=e.occurred_at,
                classification=e.classification,
                sentiment_score=e.sentiment_score,
                severity_score=e.severity_score,
                entities=e.entities,
                cluster_id=e.cluster_id,
            )
            for e in events
        ],
        count=len(events),
        data_as_of=audit["data_as_of"],
    )
