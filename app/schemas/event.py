"""Pydantic v2 schemas — Events."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EventSchema(BaseModel):
    id: uuid.UUID
    title: str
    source: str
    region: str
    occurred_at: datetime
    classification: str | None = None
    sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    severity_score: float | None = Field(default=None, ge=0.0, le=1.0)
    entities: list[str] | None = None
    cluster_id: uuid.UUID | None = None


class EventTimelineResponse(BaseModel):
    start: datetime
    end: datetime
    events: list[EventSchema]
    count: int
    data_as_of: str
