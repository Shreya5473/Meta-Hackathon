"""Audit metadata injected into all API responses."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import get_settings


class AuditMiddleware(BaseHTTPMiddleware):
    """Injects X-* audit headers into every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        response = await call_next(request)
        response.headers["X-Model-Version"] = settings.gti_version
        response.headers["X-Pipeline-Version"] = settings.pipeline_version
        response.headers["X-App-Version"] = settings.app_version
        response.headers["X-Data-As-Of"] = datetime.now(UTC).isoformat()
        return response


def build_audit_meta() -> dict[str, Any]:
    """Return audit dict to embed in response bodies."""
    settings = get_settings()
    return {
        "model_version": settings.gti_version,
        "pipeline_version": settings.pipeline_version,
        "data_as_of": datetime.now(UTC).isoformat(),
        "not_financial_advice": True,
    }
