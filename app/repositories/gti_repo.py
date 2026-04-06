"""GTI snapshot repository."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, select

from app.models.gti import GTISnapshot
from app.repositories.base import BaseRepository


class GTIRepository(BaseRepository[GTISnapshot]):
    model = GTISnapshot

    async def get_latest(self, region: str = "global") -> GTISnapshot | None:
        result = await self.session.execute(
            select(GTISnapshot)
            .where(GTISnapshot.region == region)
            .order_by(GTISnapshot.ts.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        region: str = "global",
        limit: int = 1000,
    ) -> Sequence[GTISnapshot]:
        result = await self.session.execute(
            select(GTISnapshot)
            .where(
                and_(
                    GTISnapshot.region == region,
                    GTISnapshot.ts >= start,
                    GTISnapshot.ts <= end,
                )
            )
            .order_by(GTISnapshot.ts.asc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_previous(self, region: str, ts: datetime) -> GTISnapshot | None:
        result = await self.session.execute(
            select(GTISnapshot)
            .where(and_(GTISnapshot.region == region, GTISnapshot.ts < ts))
            .order_by(GTISnapshot.ts.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_latest(self) -> Sequence[GTISnapshot]:
        """Fetch the latest snapshot for every region."""
        from sqlalchemy import func
        
        subq = (
            select(
                GTISnapshot.region,
                func.max(GTISnapshot.ts).label("max_ts")
            )
            .group_by(GTISnapshot.region)
            .subquery()
        )
        
        result = await self.session.execute(
            select(GTISnapshot)
            .join(
                subq,
                and_(
                    GTISnapshot.region == subq.c.region,
                    GTISnapshot.ts == subq.c.max_ts
                )
            )
        )
        return result.scalars().all()
