"""SQLAlchemy model for the trade_log table."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class TradeLog(Base):
    """One row per trade decision (buy / sell / hold logged for transparency)."""

    __tablename__ = "trade_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    # Portfolio owner
    email = Column(String(255), nullable=False, index=True)
    # Instrument
    symbol = Column(String(32), nullable=False)
    # "buy" | "sell" | "hold"
    action = Column(String(8), nullable=False)
    quantity = Column(Float, nullable=True)          # units traded (None for hold)
    price = Column(Float, nullable=True)             # fill price (None for hold)
    # ML signal metadata
    signal_vol_spike = Column(Float, nullable=True)
    signal_bias = Column(Float, nullable=True)
    recommendation = Column(String(32), nullable=True)
    # Broker response
    order_id = Column(String(100), nullable=True)
    status = Column(String(20), nullable=True)       # accepted|rejected|hold|error
    broker = Column(String(20), nullable=True)       # "oanda" | "paper"
    # Realised P&L (filled in when position is closed/updated)
    pnl = Column(Float, nullable=True)
    # Human-readable note (e.g. why hold, error message, etc.)
    note = Column(String(500), nullable=True)
