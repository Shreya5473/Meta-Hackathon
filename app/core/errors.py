"""RFC 7807 Problem Details error responses + exception handlers."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base application error."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail or {}


class NotFoundError(AppError):
    def __init__(self, resource: str, identifier: Any = None) -> None:
        super().__init__(
            message=f"{resource} not found" + (f": {identifier}" if identifier else ""),
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ValidationError(AppError):
    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class ServiceUnavailableError(AppError):
    def __init__(self, service: str) -> None:
        super().__init__(
            message=f"Service temporarily unavailable: {service}",
            code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def _problem_detail(
    status_code: int,
    code: str,
    message: str,
    request: Request,
    detail: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://geotrade.dev/errors/{code.lower()}",
        "title": code,
        "status": status_code,
        "detail": message,
        "instance": str(request.url),
    }
    if detail:
        body["extensions"] = detail
    return JSONResponse(content=body, status_code=status_code)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app_error",
            code=exc.code,
            message=exc.message,
            path=str(request.url),
        )
        return _problem_detail(exc.status_code, exc.code, exc.message, request, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem_detail(
            exc.status_code,
            "HTTP_ERROR",
            str(exc.detail),
            request,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled_exception",
            error=str(exc),
            path=str(request.url),
            exc_info=True,
        )
        return _problem_detail(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
            request,
        )
