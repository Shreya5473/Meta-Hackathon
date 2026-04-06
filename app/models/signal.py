"""MarketSignal and ModelVersion ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MarketSignal(Base):
    """Market impact signal for a single asset, computed by the impact model."""

    __tablename__ = "market_signals"
    __table_args__ = (
        Index("ix_signal_symbol_ts", "symbol", "ts"),
        Index("ix_signal_ts", "ts"),
        {"timescaledb_hypertable": {"time_column_name": "ts"}},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="global")
    sector: Mapped[str | None] = mapped_column(String(64))

    vol_spike_prob_24h: Mapped[float] = mapped_column(Float, nullable=False)
    directional_bias: Mapped[float] = mapped_column(Float, nullable=False)
    sector_stress: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty: Mapped[float] = mapped_column(Float, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(8), nullable=False)  # Buy/Sell/Hold

    # New fields for enhanced AI Signals Engine
    confidence: Mapped[float | None] = mapped_column(Float)
    bullish_strength: Mapped[float | None] = mapped_column(Float)
    bearish_strength: Mapped[float | None] = mapped_column(Float)
    volatility: Mapped[str | None] = mapped_column(String(16))
    triggering_event: Mapped[str | None] = mapped_column(Text)

    # Trade setup
    entry: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    target: Mapped[float | None] = mapped_column(Float)
    risk_reward: Mapped[float | None] = mapped_column(Float)
    atr: Mapped[float | None] = mapped_column(Float)
    max_position: Mapped[float | None] = mapped_column(Float)

    reasoning: Mapped[str | None] = mapped_column(Text)

    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_hash: Mapped[str | None] = mapped_column(String(64))

    # Calibration
    brier_score_tracker: Mapped[dict | None] = mapped_column(JSONB)


class ModelVersion(Base):
    """Registry of deployed model versions with feature schema hashes."""

    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    brier_score: Mapped[float | None] = mapped_column(Float)
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
