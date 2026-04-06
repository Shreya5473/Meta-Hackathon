"""Pydantic v2 schemas — Alerts and health."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class AlertSubscribeRequest(BaseModel):
    channel: Literal["discord", "slack", "generic"]
    webhook_url: HttpUrl
    region_filter: str | None = None
    gti_threshold: float | None = Field(default=None, ge=0.0, le=100.0)
    config: dict | None = None


class AlertSubscribeResponse(BaseModel):
    id: uuid.UUID
    channel: str
    region_filter: str | None
    gti_threshold: float | None
    is_active: bool
    created_at: datetime


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    db: bool
    redis: bool
    worker: bool
    ts: datetime


class ModelStatusResponse(BaseModel):
    gti_version: str
    pipeline_version: str
    active_models: list[dict]
    last_ingestion_at: datetime | None
    last_gti_computed_at: datetime | None
    data_as_of: str
