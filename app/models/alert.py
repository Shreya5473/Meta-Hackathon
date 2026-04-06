"""AlertSubscription ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AlertSubscription(Base):
    """Webhook subscription for GTI/signal alerts."""

    __tablename__ = "alert_subscriptions"
    __table_args__ = (Index("ix_alert_channel", "channel"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)  # discord/slack/generic
    webhook_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    region_filter: Mapped[str | None] = mapped_column(String(64))
    gti_threshold: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict | None] = mapped_column(JSONB)  # extra channel-specific config
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
