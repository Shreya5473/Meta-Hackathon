"""Market data and alert repositories."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta, UTC
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert

from app.models.market import MarketData
from app.models.alert import AlertSubscription
from app.repositories.base import BaseRepository


class MarketDataRepository(BaseRepository[MarketData]):
    model = MarketData

    async def upsert(self, obj: MarketData) -> MarketData:
        """Idempotent upsert on (symbol, ts)."""
        stmt = (
            insert(MarketData)
            .values(
                id=obj.id,
                symbol=obj.symbol,
                asset_class=obj.asset_class,
                region=obj.region,
                ts=obj.ts,
                open=obj.open,
                high=obj.high,
                low=obj.low,
                close=obj.close,
                volume=obj.volume,
                realized_vol=obj.realized_vol,
                return_1d=obj.return_1d,
                return_5d=obj.return_5d,
            )
            .on_conflict_do_update(
                index_elements=["symbol", "ts"],
                set_={
                    "close": obj.close,
                    "realized_vol": obj.realized_vol,
                    "return_1d": obj.return_1d,
                    "return_5d": obj.return_5d,
                },
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return obj

    async def get_history(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> Sequence[MarketData]:
        result = await self.session.execute(
            select(MarketData)
            .where(
                and_(
                    MarketData.symbol == symbol,
                    MarketData.ts >= start,
                    MarketData.ts <= end,
                )
            )
            .order_by(MarketData.ts.asc())
        )
        return result.scalars().all()

    async def get_latest_per_symbol(self) -> Sequence[MarketData]:
        from sqlalchemy import func
        subq = (
            select(MarketData.symbol, func.max(MarketData.ts).label("max_ts"))
            .group_by(MarketData.symbol)
            .subquery()
        )
        result = await self.session.execute(
            select(MarketData).join(
                subq,
                and_(
                    MarketData.symbol == subq.c.symbol,
                    MarketData.ts == subq.c.max_ts,
                ),
            )
        )
        return result.scalars().all()


class AlertRepository(BaseRepository[AlertSubscription]):
    model = AlertSubscription

    async def get_active(self) -> Sequence[AlertSubscription]:
        result = await self.session.execute(
            select(AlertSubscription).where(AlertSubscription.is_active.is_(True))
        )
        return result.scalars().all()

    async def get_active_for_region(self, region: str) -> Sequence[AlertSubscription]:
        result = await self.session.execute(
            select(AlertSubscription).where(
                and_(
                    AlertSubscription.is_active.is_(True),
                    (AlertSubscription.region_filter == region)
                    | AlertSubscription.region_filter.is_(None),
                )
            )
        )
        return result.scalars().all()
