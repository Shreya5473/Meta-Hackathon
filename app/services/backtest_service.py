"""Backtesting service — orchestrates historical signal replay."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.pipelines.backtesting import BacktestEngine, FullBacktestResult, get_backtest_engine
from app.repositories.event_repo import EventRepository

logger = get_logger(__name__)


class BacktestService:
    """Service layer for running backtests against historical event data."""

    def __init__(self, event_repo: EventRepository) -> None:
        self.event_repo = event_repo
        self.engine = get_backtest_engine()

    async def run_backtest(
        self,
        assets: list[str] | None = None,
        lookback_days: int = 7,
        asset_meta: dict[str, dict[str, Any]] | None = None,
    ) -> FullBacktestResult:
        """Run a backtest using stored events from the database."""
        end = datetime.now(UTC)
        start = end - timedelta(days=lookback_days)

        # Fetch historical events
        events_orm = await self.event_repo.get_active_events(start)

        events = [
            {
                "id": e.id,
                "occurred_at": e.occurred_at,
                "severity_score": e.severity_score or 0.3,
                "sentiment_score": e.sentiment_score or 0.0,
                "geo_risk_vector": e.geo_risk_vector or {"global": 1.0},
                "region": e.region,
                "classification": e.classification or "normal",
                "title": e.title,
            }
            for e in events_orm
        ]

        if not assets:
            assets = ["SPY", "GLD", "USO", "TLT", "XLE", "QQQ", "ITA", "JETS"]

        logger.info(
            "backtest_starting",
            assets=len(assets),
            events=len(events),
            lookback_days=lookback_days,
        )

        result = self.engine.run_synthetic_backtest(
            events=events,
            assets=assets,
            asset_meta=asset_meta,
            start_date=start,
            end_date=end,
        )

        logger.info(
            "backtest_complete",
            signals=result.overall_metrics.total_signals,
            accuracy=result.overall_metrics.signal_accuracy,
            sharpe=result.overall_metrics.sharpe_ratio,
        )

        return result
