"""Backtesting endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import build_audit_meta
from app.core.database import get_db
from app.repositories.event_repo import EventRepository
from app.schemas.backtest import (
    AssetBacktestResultSchema,
    BacktestMetricsSchema,
    BacktestRequest,
    BacktestResponse,
    BacktestSignalSchema,
)
from app.services.backtest_service import BacktestService

router = APIRouter(prefix="/backtest", tags=["backtesting"])


@router.post("", response_model=BacktestResponse)
async def run_backtest(
    req: BacktestRequest,
    db: AsyncSession = Depends(get_db),
) -> BacktestResponse:
    """Replay historical events through the ML pipeline and compute performance."""
    event_repo = EventRepository(db)
    svc = BacktestService(event_repo)
    result = await svc.run_backtest(
        assets=req.assets,
        lookback_days=req.lookback_days,
        asset_meta=req.asset_meta,
    )

    return BacktestResponse(
        start_date=result.start_date,
        end_date=result.end_date,
        overall_metrics=BacktestMetricsSchema(**_metrics_dict(result.overall_metrics)),
        asset_results=[
            AssetBacktestResultSchema(
                asset=ar.asset,
                metrics=BacktestMetricsSchema(**_metrics_dict(ar.metrics)),
                equity_curve=ar.equity_curve,
                signals=[
                    BacktestSignalSchema(
                        timestamp=s.timestamp,
                        asset=s.asset,
                        recommendation=s.recommendation,
                        confidence=s.confidence,
                        vol_spike_prob=s.vol_spike_prob,
                        directional_bias=s.directional_bias,
                        actual_return=s.actual_return,
                        hit=s.hit,
                        pnl=s.pnl,
                    )
                    for s in ar.signals
                ],
            )
            for ar in result.asset_results
        ],
        gti_path=result.gti_path,
        summary=result.summary,
    )


def _metrics_dict(m: object) -> dict:
    """Convert BacktestMetrics dataclass to dict."""
    return {
        "total_signals": m.total_signals,
        "buy_signals": m.buy_signals,
        "sell_signals": m.sell_signals,
        "hold_signals": m.hold_signals,
        "signal_accuracy": m.signal_accuracy,
        "sharpe_ratio": m.sharpe_ratio,
        "max_drawdown": m.max_drawdown,
        "max_drawdown_pct": m.max_drawdown_pct,
        "profit_factor": m.profit_factor,
        "win_loss_ratio": m.win_loss_ratio,
        "cumulative_return": m.cumulative_return,
        "calmar_ratio": m.calmar_ratio,
        "avg_confidence": m.avg_confidence,
        "avg_vol_prediction": m.avg_vol_prediction,
        "time_period_days": m.time_period_days,
        "annualized_return": m.annualized_return,
        "annualized_volatility": m.annualized_volatility,
    }
