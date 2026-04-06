"""Celery app configuration and task definitions.

Beat schedule:
    - News ingestion every 1 minute (was 15 min)
    - Market data ingestion every 30 seconds
    - GTI computation every 5 minutes (was hourly)
    - Signal computation every 5 minutes (was hourly)
    - WebSocket broadcast every minute
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "geotrade_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.ingestion_tasks",
        "app.tasks.gti_tasks",
        "app.tasks.signal_tasks",
        "app.tasks.market_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    task_queue_max_priority=10,
    worker_max_tasks_per_child=100,
    # Routing
    task_routes={
        "app.tasks.ingestion_tasks.*": {"queue": "ingestion"},
        "app.tasks.market_tasks.*": {"queue": "market"},
        "app.tasks.gti_tasks.*": {"queue": "gti"},
        "app.tasks.signal_tasks.*": {"queue": "default"},
    },
    # Beat schedule — high-frequency
    beat_schedule={
        "ingest-news-every-minute": {
            "task": "app.tasks.ingestion_tasks.run_news_ingestion",
            "schedule": 60.0,  # every 60 seconds
        },
        "ingest-market-data-every-30s": {
            "task": "app.tasks.market_tasks.ingest_market_data",
            "schedule": 30.0,  # every 30 seconds
        },
        "paper-trading-feed-every-30s": {
            "task": "app.tasks.market_tasks.ingest_paper_trading_prices",
            "schedule": 30.0,  # OANDA + CCXT live ticks → live_price_ticks
        },
        "compute-gti-every-5min": {
            "task": "app.tasks.gti_tasks.compute_gti_all_regions",
            "schedule": 300.0,  # every 5 minutes
        },
        "compute-signals-every-5min": {
            "task": "app.tasks.signal_tasks.compute_all_signals",
            "schedule": 300.0,  # every 5 minutes
        },
        "broadcast-ws-updates-every-minute": {
            "task": "app.tasks.signal_tasks.broadcast_ws_updates",
            "schedule": 60.0,  # every 60 seconds
        },
    },
)
