"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1 import (
    alerts,
    backtest,
    events,
    globe,
    graph,
    gti,
    health,
    market,
    portfolio,
    risk,
    signals,
    signals_v2,
    simulate,
    waitlist,
)
from app.api.v1 import ws as ws_routes
from app.core.audit import AuditMiddleware
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    settings = get_settings()
    logger.info(
        "starting_geotrade",
        version=settings.app_version,
        env=settings.app_env,
    )

    # Optionally configure OTel
    if settings.enable_otel:
        _setup_otel(app, settings)

    # Redis connectivity check — warn early if REDIS_URL still points to localhost
    try:
        from app.core.cache import check_redis_health
        redis_ok = await check_redis_health()
        if redis_ok:
            logger.info("redis_connected", url=settings.redis_url)
        else:
            logger.error(
                "redis_unreachable",
                url=settings.redis_url,
                hint="Set REDIS_URL env var to your Redis host. "
                     "API will work but all caching is DISABLED.",
            )
    except Exception as exc:
        logger.error("redis_health_check_error", error=str(exc))

    # Pre-build impact graph
    try:
        from app.pipelines.impact_graph import get_impact_graph
        get_impact_graph()
        logger.info("impact_graph_ready")
    except Exception as exc:
        logger.warning("impact_graph_init_failed", error=str(exc))

    # Start real-time market feed (Finnhub primary → Synthetic fallback)
    feed_manager = None
    try:
        from app.pipelines.market_feeds import get_feed_manager
        from app.core.websocket import get_ws_manager
        feed_manager = get_feed_manager()
        feed_manager.set_ws_manager(get_ws_manager())
        await feed_manager.start()
        logger.info("market_feed_manager_started", adapter=feed_manager.adapter.name)
    except Exception as exc:
        logger.warning("market_feed_manager_start_failed", error=str(exc))

    yield

    # Graceful shutdown
    if feed_manager is not None:
        try:
            await feed_manager.stop()
        except Exception:
            pass
    logger.info("shutting_down")
    await dispose_engine()


def _setup_otel(app: FastAPI, settings: "Settings") -> None:  # type: ignore[name-defined]
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource(attributes={"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("otel_configured")
    except Exception as exc:
        logger.warning("otel_setup_failed", error=str(exc))


def create_app() -> FastAPI:
    settings = get_settings()

    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default])

    app = FastAPI(
        title="GeoTrade API",
        description=(
            "AI-powered geopolitical market stress intelligence platform. "
            "Monitors real-time events, generates BUY/SELL signals via ML, "
            "and provides full backtesting capabilities. "
            "⚠️ Not financial advice."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Middleware (order matters — outermost first)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(AuditMiddleware)
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "https://geotrade-8pe.vercel.app",
        "https://geotrade-web.vercel.app",
    ]
    if settings.frontend_url:
        for url in settings.frontend_url.split(","):
            origins.append(url.strip())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    register_exception_handlers(app)

    # Routes (support both legacy root and versioned paths)
    api_routers = [
        health.router,
        gti.router,
        signals.router,
        events.router,
        simulate.router,
        portfolio.router,
        risk.router,
        alerts.router,
        backtest.router,
        graph.router,
        market.router,
        globe.router,
        signals_v2.router,
        waitlist.router,
    ]
    for router in api_routers:
        app.include_router(router)
        app.include_router(router, prefix=settings.api_v1_str)

    # WebSocket routes (no prefix duplication needed)
    app.include_router(ws_routes.router)
    app.include_router(ws_routes.router, prefix=settings.api_v1_str)

    # Serve static frontend files from dist folder
    # Mount at the end so API routes take precedence
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
    else:
        logger.warning("frontend_dist_not_found", path=str(frontend_dist))

    return app


app = create_app()
