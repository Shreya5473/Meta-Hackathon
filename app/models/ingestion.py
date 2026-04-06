"""IngestionSource and IngestionRun ORM models for pipeline health tracking."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class IngestionSource(Base):
    """Configured data source for the ingestion pipeline."""

    __tablename__ = "ingestion_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False)  # rss/api/file
    url: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="global")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict | None] = mapped_column(JSONB)
    success_rate_7d: Mapped[float | None] = mapped_column(Float)

    runs: Mapped[list[IngestionRun]] = relationship(back_populates="source")


class IngestionRun(Base):
    """Record of a single ingestion pipeline execution."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (Index("ix_run_source_started_at", "source_id", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        __import__("sqlalchemy").ForeignKey("ingestion_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    items_fetched: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    source: Mapped[IngestionSource] = relationship(back_populates="runs")
