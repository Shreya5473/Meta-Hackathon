"""GTI service — computes and persists GTI snapshots."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.audit import build_audit_meta
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.gti import GTISnapshot
from app.pipelines.gti_engine import get_gti_engine
from app.repositories.event_repo import EventRepository
from app.repositories.gti_repo import GTIRepository
from app.schemas.gti import GTICurrentResponse, GTIDriverSchema, GTIHistoryPoint, GTIHistoryResponse

logger = get_logger(__name__)

_SUPPORTED_REGIONS = ["global", "middle_east", "europe", "asia_pacific", "americas", "africa"]


class GTIService:
    def __init__(self, gti_repo: GTIRepository, event_repo: EventRepository) -> None:
        self.gti_repo = gti_repo
        self.event_repo = event_repo

    async def get_current(self, region: str = "global") -> GTICurrentResponse:
        snapshot = await self.gti_repo.get_latest(region)
        if snapshot is None:
            # Compute on-demand if no snapshot exists
            snapshot = await self._compute_and_persist(region)

        drivers = [
            GTIDriverSchema(
                event_id=d["event_id"],
                contribution_weight=d["contribution_weight"],
                region=d.get("region"),
            )
            for d in (snapshot.top_drivers or [])
        ]

        audit = build_audit_meta()
        return GTICurrentResponse(
            region=snapshot.region,
            gti_value=snapshot.gti_value,
            gti_delta_1h=snapshot.gti_delta_1h,
            confidence=snapshot.confidence,
            top_drivers=drivers,
            calculation_version=snapshot.calculation_version,
            ts=snapshot.ts,
            **audit,
        )

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        region: str = "global",
    ) -> GTIHistoryResponse:
        snapshots = await self.gti_repo.get_history(start, end, region)
        data = [
            GTIHistoryPoint(
                ts=s.ts,
                gti_value=s.gti_value,
                gti_delta_1h=s.gti_delta_1h,
                confidence=s.confidence,
                region=s.region,
            )
            for s in snapshots
        ]
        audit = build_audit_meta()
        return GTIHistoryResponse(
            region=region,
            start=start,
            end=end,
            data=data,
            **audit,
        )

    async def _compute_and_persist(self, region: str = "global") -> GTISnapshot:
        """Real-time GTI computation; used when no recent snapshot exists."""
        engine = get_gti_engine()
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=72)

        active_events = await self.event_repo.get_active_events(window_start)
        prev_snapshot = await self.gti_repo.get_latest(region)

        event_dicts = [
            {
                "id": e.id,
                "occurred_at": e.occurred_at,
                "severity_score": e.severity_score,
                "sentiment_score": e.sentiment_score,
                "region": e.region,
                "geo_risk_vector": e.geo_risk_vector or {"global": 1.0},
            }
            for e in active_events
        ]

        result = engine.compute(
            events=event_dicts,
            prev_gti=prev_snapshot.gti_value if prev_snapshot else None,
            prev_ts=prev_snapshot.ts if prev_snapshot else None,
            region=region,
            now=now,
        )

        snapshot = GTISnapshot(
            ts=result.ts,
            region=result.region,
            gti_value=result.gti_value,
            gti_delta_1h=result.gti_delta_1h,
            confidence=result.confidence,
            top_drivers=result.top_drivers,
            calculation_version=result.calculation_version,
        )
        await self.gti_repo.create(snapshot)
        logger.info(
            "gti_computed_and_persisted",
            region=region,
            gti_value=result.gti_value,
            confidence=result.confidence,
        )
        return snapshot

    async def compute_all_regions(self) -> None:
        """Compute GTI for all supported regions (called by Celery task)."""
        for region in _SUPPORTED_REGIONS:
            try:
                await self._compute_and_persist(region)
            except Exception as exc:
                logger.error("gti_region_failed", region=region, error=str(exc))
