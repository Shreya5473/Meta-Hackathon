"""MarketData OHLCV time-series ORM model."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class MarketData(Base):
    """OHLCV + volatility snapshot for a single asset at a point in time.

    Stored in a TimescaleDB hypertable partitioned by `ts`.
    """

    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint("symbol", "ts", name="uq_market_symbol_ts"),
        Index("ix_market_symbol", "symbol"),
        Index("ix_market_ts", "ts"),
        {"timescaledb_hypertable": {"time_column_name": "ts"}},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)  # equity/fx/commodity
    region: Mapped[str] = mapped_column(String(64), nullable=False, default="global")
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)

    # Derived
    realized_vol: Mapped[float | None] = mapped_column(Float)  # Parkinson's estimator
    return_1d: Mapped[float | None] = mapped_column(Float)
    return_5d: Mapped[float | None] = mapped_column(Float)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
