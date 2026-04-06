"""Health and model-status endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import build_audit_meta
from app.core.cache import check_redis_health
from app.core.config import get_settings
from app.core.database import check_db_health, get_db
from app.repositories.gti_repo import GTIRepository
from app.repositories.signal_repo import ModelVersionRepository
from app.schemas.health import HealthResponse, ModelStatusResponse

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse, summary="System health check")
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()
    # Worker liveness: check if celery heartbeat key exists in Redis
    worker_ok = True  # simplified; could inspect via celery inspect.ping()
    overall = "healthy" if (db_ok and redis_ok) else "degraded" if db_ok else "unhealthy"
    settings = get_settings()
    return HealthResponse(
        status=overall,
        version=settings.app_version,
        db=db_ok,
        redis=redis_ok,
        worker=worker_ok,
        ts=datetime.now(UTC),
    )


@router.get("/meta/model-status", response_model=ModelStatusResponse)
async def model_status(db: AsyncSession = Depends(get_db)) -> ModelStatusResponse:
    settings = get_settings()
    mv_repo = ModelVersionRepository(db)
    gti_repo = GTIRepository(db)

    active_models = await mv_repo.get_active_versions()
    latest_gti = await gti_repo.get_latest("global")

    from app.repositories.event_repo import EventRepository
    event_repo = EventRepository(db)
    from sqlalchemy import select, func
    from app.models.ingestion import IngestionRun
    from sqlalchemy import desc
    result = await db.execute(
        select(IngestionRun.finished_at)
        .where(IngestionRun.status == "complete")
        .order_by(desc(IngestionRun.finished_at))
        .limit(1)
    )
    last_ingest = result.scalar_one_or_none()

    audit = build_audit_meta()
    return ModelStatusResponse(
        gti_version=settings.gti_version,
        pipeline_version=settings.pipeline_version,
        active_models=[
            {
                "name": m.model_name,
                "version": m.version,
                "feature_schema_hash": m.feature_schema_hash,
                "brier_score": m.brier_score,
                "deployed_at": m.deployed_at.isoformat(),
            }
            for m in active_models
        ],
        last_ingestion_at=last_ingest,
        last_gti_computed_at=latest_gti.ts if latest_gti else None,
        data_as_of=audit["data_as_of"],
    )
