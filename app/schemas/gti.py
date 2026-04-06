"""Pydantic v2 schemas — GTI."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class GTIDriverSchema(BaseModel):
    event_id: uuid.UUID
    contribution_weight: float = Field(ge=0.0, le=1.0)
    title: str | None = None
    region: str | None = None


class GTICurrentResponse(BaseModel):
    region: str
    gti_value: float = Field(ge=0.0, le=100.0)
    gti_delta_1h: float
    confidence: float = Field(ge=0.0, le=1.0)
    top_drivers: list[GTIDriverSchema]
    calculation_version: str
    ts: datetime
    # Audit
    model_version: str
    pipeline_version: str
    data_as_of: str
    not_financial_advice: bool = True


class GTIHistoryPoint(BaseModel):
    ts: datetime
    gti_value: float
    gti_delta_1h: float
    confidence: float
    region: str


class GTIHistoryResponse(BaseModel):
    region: str
    start: datetime
    end: datetime
    data: list[GTIHistoryPoint]
    model_version: str
    pipeline_version: str
    data_as_of: str
    not_financial_advice: bool = True
