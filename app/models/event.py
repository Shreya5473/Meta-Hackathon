"""Event and EventCluster ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Event(Base):
    """A single ingested and processed news event."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_event_content_hash"),
        Index("ix_event_occurred_at", "occurred_at"),
        Index("ix_event_region", "region"),
        Index("ix_event_cluster_id", "cluster_id"),
        Index("ix_event_source", "source"),
        {"timescaledb_hypertable": {"time_column_name": "occurred_at"}},  # noqa: PIE800
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="global")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # NLP outputs
    classification: Mapped[str | None] = mapped_column(String(32))  # normal/tension/escalation
    sentiment_score: Mapped[float | None] = mapped_column(Float)  # -1 to 1
    severity_score: Mapped[float | None] = mapped_column(Float)  # 0 to 1
    entities: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    geo_risk_vector: Mapped[dict | None] = mapped_column(JSONB)  # {region: weight}
    embedding: Mapped[list | None] = mapped_column(JSONB)  # sentence embedding (stored as list)

    # Cluster reference
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event_clusters.id", ondelete="SET NULL")
    )
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    cluster: Mapped[EventCluster | None] = relationship(back_populates="events")


class EventCluster(Base):
    """Canonical cluster grouping semantically similar events."""

    __tablename__ = "event_clusters"
    __table_args__ = (Index("ix_cluster_created_at", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="global")

    # Aggregate NLP features
    severity_mean: Mapped[float] = mapped_column(Float, default=0.0)
    sentiment_mean: Mapped[float] = mapped_column(Float, default=0.0)
    entity_count: Mapped[int] = mapped_column(Integer, default=0)
    event_count: Mapped[int] = mapped_column(Integer, default=1)
    geo_risk_vector: Mapped[dict | None] = mapped_column(JSONB)

    canonical_title: Mapped[str | None] = mapped_column(Text)

    # Relationships
    events: Mapped[list[Event]] = relationship(back_populates="cluster")
