"""Persistence models for User Portfolios and Shared Snapshots."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Float, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class UserPortfolio(Base):
    """A user's saved list of holdings, keyed by email address."""
    __tablename__ = "user_portfolios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Email used as the anonymous identity key (from waitlist registration)
    user_email = Column(String(255), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    # List of holdings: [{"symbol": "SPY", "weight": 0.6, "sector": "equity", "region": "americas"}]
    holdings = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(UTC))


class SimulationSnapshot(Base):
    """A shared link/snapshot of a scenario or portfolio evaluation."""
    __tablename__ = "simulation_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Type: 'scenario' or 'portfolio'
    snapshot_type = Column(String(20), nullable=False)
    # The original request params
    params = Column(JSONB, nullable=False)
    # The output results
    results = Column(JSONB, nullable=False)
    # Metadata for social sharing (generated summary)
    share_summary = Column(String(500))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # Expiry for old snapshots (optional)
    expires_at = Column(DateTime(timezone=True))
