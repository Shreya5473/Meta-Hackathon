"""GTISnapshot time-series ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class GTISnapshot(Base):
    """Point-in-time Geopolitical Tension Index snapshot.

    Stored in a TimescaleDB hypertable for efficient range queries.
    """

    __tablename__ = "gti_snapshots"
    __table_args__ = (
        Index("ix_gti_region_ts", "region", "ts"),
        {"timescaledb_hypertable": {"time_column_name": "ts"}},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="global")

    gti_value: Mapped[float] = mapped_column(Float, nullable=False)
    gti_delta_1h: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # JSON array of {event_id, contribution_weight}
    top_drivers: Mapped[list | None] = mapped_column(JSONB)
    calculation_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
