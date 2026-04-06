"""Repositories for User Portfolios and Shared Snapshots."""
from __future__ import annotations

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persistence import UserPortfolio, SimulationSnapshot
from app.repositories.base import BaseRepository


class UserPortfolioRepository(BaseRepository[UserPortfolio]):
    model = UserPortfolio

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self) -> list[UserPortfolio]:
        result = await self.session.execute(select(UserPortfolio))
        return list(result.scalars().all())

    async def get_by_email(self, email: str) -> UserPortfolio | None:
        result = await self.session.execute(
            select(UserPortfolio)
            .where(UserPortfolio.user_email == email.lower().strip())
            .order_by(UserPortfolio.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert_by_email(
        self,
        email: str,
        holdings: list[dict],
        name: str = "My Portfolio",
    ) -> UserPortfolio:
        """Create or update the single portfolio for this email."""
        from datetime import UTC, datetime
        email = email.lower().strip()
        existing = await self.get_by_email(email)
        if existing is not None:
            existing.holdings = holdings
            existing.name = name
            existing.updated_at = datetime.now(UTC)
            await self.session.flush()
            return existing
        pf = UserPortfolio(user_email=email, name=name, holdings=holdings)
        self.session.add(pf)
        await self.session.flush()
        return pf


class SimulationSnapshotRepository(BaseRepository[SimulationSnapshot]):
    model = SimulationSnapshot

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, snapshot_id: UUID) -> SimulationSnapshot | None:
        result = await self.session.execute(
            select(SimulationSnapshot).where(SimulationSnapshot.id == snapshot_id)
        )
        return result.scalar_one_or_none()
