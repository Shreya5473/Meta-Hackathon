"""Services for shared simulation snapshots and user portfolios."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.models.persistence import UserPortfolio, SimulationSnapshot
from app.repositories.persistence_repo import UserPortfolioRepository, SimulationSnapshotRepository

logger = get_logger(__name__)


class SharingService:
    def __init__(self, snapshot_repo: SimulationSnapshotRepository) -> None:
        self.snapshot_repo = snapshot_repo

    async def create_snapshot(
        self, snapshot_type: str, params: dict, results: dict
    ) -> SimulationSnapshot:
        summary = self._generate_share_summary(snapshot_type, results)
        snapshot = SimulationSnapshot(
            snapshot_type=snapshot_type,
            params=params,
            results=results,
            share_summary=summary,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        await self.snapshot_repo.create(snapshot)
        return snapshot

    def _generate_share_summary(self, snapshot_type: str, results: dict) -> str:
        if snapshot_type == "scenario":
            peak = results.get("aggregate_stress_peak", 0.0)
            return f"GeoTrade AI Scenario: Projected market stress peaked at {peak:.1f}% GTI impact. 🚨"
        elif snapshot_type == "portfolio":
            impact = results.get("expected_stress_impact", 0.0)
            return f"GeoTrade AI Portfolio: Current geopolitical stress impact estimated at {impact*100:.1f}%. 📊"
        return "GeoTrade AI market intelligence snapshot."

    async def evaluate_portfolio(self, portfolio: list[dict[str, Any]]) -> str:
        if portfolio:
            impact = sum(p.get("allocation", 0) * 0.05 for p in portfolio)
            return f"GeoTrade AI Portfolio: Current geopolitical stress impact estimated at {impact*100:.1f}%. 📊"
        return "GeoTrade AI market intelligence snapshot."


class PortfolioPersistenceService:
    def __init__(self, portfolio_repo: UserPortfolioRepository) -> None:
        self.portfolio_repo = portfolio_repo

    async def create(self, name: str, holdings: list[dict], description: str | None = None) -> UserPortfolio:
        pf = UserPortfolio(name=name, description=description, holdings=holdings)
        await self.portfolio_repo.create(pf)
        return pf

    async def get_all(self) -> list[UserPortfolio]:
        return await self.portfolio_repo.get_all()

    async def get_for_email(self, email: str) -> UserPortfolio | None:
        return await self.portfolio_repo.get_by_email(email)

    async def save_for_email(
        self, email: str, holdings: list[dict], name: str = "My Portfolio"
    ) -> UserPortfolio:
        """Upsert the portfolio for an email-identified user."""
        return await self.portfolio_repo.upsert_by_email(
            email=email, holdings=holdings, name=name
        )
