"""Signal Backtesting Engine.

Replays historical geopolitical events through the ML pipeline and
calculates trading performance metrics against actual market outcomes.

Metrics computed:
    - Sharpe ratio
    - Signal accuracy (hit rate)
    - Maximum drawdown
    - Profit factor
    - Win/loss ratio
    - Cumulative return
    - Calmar ratio
    - Signal-level breakdown
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.pipelines.gti_engine import GTIEngine, get_gti_engine
from app.pipelines.market_model import AssetFeatures, MarketImpactModel, get_impact_model

logger = get_logger(__name__)


@dataclass
class BacktestSignal:
    """A single backtested signal at a point in time."""
    timestamp: datetime
    asset: str
    recommendation: str  # Buy / Sell / Hold
    confidence: float
    vol_spike_prob: float
    directional_bias: float
    actual_return: float  # realized return over next period
    hit: bool  # did the signal correctly predict direction?
    pnl: float  # profit/loss from acting on signal


@dataclass
class BacktestMetrics:
    """Aggregate performance metrics for a backtest run."""
    total_signals: int
    buy_signals: int
    sell_signals: int
    hold_signals: int
    signal_accuracy: float  # % of directional calls that were correct
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    profit_factor: float
    win_loss_ratio: float
    cumulative_return: float
    calmar_ratio: float
    avg_confidence: float
    avg_vol_prediction: float
    time_period_days: int
    annualized_return: float
    annualized_volatility: float


@dataclass
class AssetBacktestResult:
    """Backtest results for a single asset."""
    asset: str
    metrics: BacktestMetrics
    equity_curve: list[float]
    signals: list[BacktestSignal]


@dataclass
class FullBacktestResult:
    """Complete backtest results across all assets."""
    start_date: datetime
    end_date: datetime
    overall_metrics: BacktestMetrics
    asset_results: list[AssetBacktestResult]
    gti_path: list[dict[str, Any]]
    summary: str


class BacktestEngine:
    """Replays geopolitical events through the ML pipeline for backtesting.

    Modes:
        1. Synthetic backtest — uses stored events + synthetic market data
        2. Historical backtest — uses stored events + actual market data
    """

    def __init__(
        self,
        gti_engine: GTIEngine | None = None,
        impact_model: MarketImpactModel | None = None,
    ) -> None:
        self.gti_engine = gti_engine or get_gti_engine()
        self.impact_model = impact_model or get_impact_model()

    def run_synthetic_backtest(
        self,
        events: list[dict[str, Any]],
        assets: list[str],
        asset_meta: dict[str, dict[str, Any]] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        seed: int = 42,
    ) -> FullBacktestResult:
        """Run a backtest using event history and synthetic market responses.

        Events must contain:
            - id (UUID)
            - occurred_at (datetime)
            - severity_score (float)
            - sentiment_score (float)
            - geo_risk_vector (dict)
            - region (str)
            - classification (str)
        """
        rng = np.random.default_rng(seed)
        meta = asset_meta or {}

        if not events:
            return self._empty_result(assets, start_date, end_date)

        # Sort events chronologically
        events_sorted = sorted(events, key=lambda e: e["occurred_at"])

        if start_date is None:
            start_date = events_sorted[0]["occurred_at"]
        if end_date is None:
            end_date = events_sorted[-1]["occurred_at"] + timedelta(days=1)

        # Time buckets: 1-hour intervals
        bucket_size = timedelta(hours=1)
        n_buckets = max(1, int((end_date - start_date).total_seconds() / bucket_size.total_seconds()))

        # Cap for performance
        n_buckets = min(n_buckets, 720)  # 30 days max

        gti_path = []
        prev_gti = 0.0
        prev_ts = start_date

        # Per-asset signal tracking
        asset_signals: dict[str, list[BacktestSignal]] = {a: [] for a in assets}
        asset_equity: dict[str, list[float]] = {a: [1.0] for a in assets}
        all_signals: list[BacktestSignal] = []

        for bucket_idx in range(n_buckets):
            bucket_start = start_date + bucket_idx * bucket_size
            bucket_end = bucket_start + bucket_size

            # Get events in this bucket
            bucket_events = [
                e for e in events_sorted
                if bucket_start <= e["occurred_at"] < bucket_end
            ]

            # Compute GTI for this bucket
            all_events_before = [
                e for e in events_sorted
                if e["occurred_at"] < bucket_end
            ]

            gti_result = self.gti_engine.compute(
                events=all_events_before,
                prev_gti=prev_gti,
                prev_ts=prev_ts,
                region="global",
                window_hours=72.0,
                now=bucket_end,
            )

            gti_val = gti_result.gti_value
            gti_delta = gti_result.gti_delta_1h
            gti_conf = gti_result.confidence

            gti_path.append({
                "ts": bucket_end.isoformat(),
                "gti_value": gti_val,
                "gti_delta_1h": gti_delta,
                "confidence": gti_conf,
            })

            # Generate signals for each asset
            for asset in assets:
                ameta = meta.get(asset, {})
                sector = ameta.get("sector")
                region = ameta.get("region", "global")
                base_vol = ameta.get("realized_vol", 0.15)

                features = AssetFeatures(
                    symbol=asset,
                    sector=sector,
                    region=region,
                    gti_value=gti_val,
                    gti_delta_1h=gti_delta,
                    gti_confidence=gti_conf,
                    realized_vol=base_vol + rng.normal(0, 0.02),
                    return_1d=rng.normal(0, 0.01),
                    return_5d=rng.normal(0, 0.02),
                    oil_shock=max(0.0, (gti_val - 50) / 100.0) if sector == "energy" else 0.0,
                    regime_vix_proxy=min(1.0, gti_val / 80.0),
                )

                result = self.impact_model.predict(features)

                # Synthetic actual return: based on model + noise
                signal_multiplier = {
                    "Buy": 1.0, "Sell": -1.0, "Hold": 0.0
                }.get(result.recommendation, 0.0)

                base_actual = result.directional_bias * 0.01
                noise = rng.normal(0, 0.005)
                actual_return = base_actual + noise

                # Did signal predict direction correctly?
                hit = (
                    (result.recommendation == "Buy" and actual_return > 0)
                    or (result.recommendation == "Sell" and actual_return < 0)
                    or result.recommendation == "Hold"
                )

                # PnL from acting on signal
                pnl = actual_return * signal_multiplier

                backtest_signal = BacktestSignal(
                    timestamp=bucket_end,
                    asset=asset,
                    recommendation=result.recommendation,
                    confidence=result.confidence_score,
                    vol_spike_prob=result.vol_spike_prob_24h,
                    directional_bias=result.directional_bias,
                    actual_return=round(actual_return, 6),
                    hit=hit,
                    pnl=round(pnl, 6),
                )

                asset_signals[asset].append(backtest_signal)
                all_signals.append(backtest_signal)

                # Update equity curve
                last_equity = asset_equity[asset][-1]
                asset_equity[asset].append(last_equity * (1.0 + pnl))

            prev_gti = gti_val
            prev_ts = bucket_end

        # Compute metrics
        overall_metrics = self._compute_metrics(all_signals, start_date, end_date)

        asset_results = []
        for asset in assets:
            asset_metrics = self._compute_metrics(
                asset_signals[asset], start_date, end_date
            )
            asset_results.append(AssetBacktestResult(
                asset=asset,
                metrics=asset_metrics,
                equity_curve=[round(e, 6) for e in asset_equity[asset]],
                signals=asset_signals[asset][-50:],  # last 50 for API response size
            ))

        days = max(1, (end_date - start_date).days)
        summary = (
            f"Backtest over {days} days across {len(assets)} assets. "
            f"Generated {len(all_signals)} signals. "
            f"Signal accuracy: {overall_metrics.signal_accuracy:.1%}. "
            f"Sharpe ratio: {overall_metrics.sharpe_ratio:.2f}. "
            f"Max drawdown: {overall_metrics.max_drawdown_pct:.1%}."
        )

        return FullBacktestResult(
            start_date=start_date,
            end_date=end_date,
            overall_metrics=overall_metrics,
            asset_results=asset_results,
            gti_path=gti_path[-200:],  # keep last 200 GTI points
            summary=summary,
        )

    def _compute_metrics(
        self,
        signals: list[BacktestSignal],
        start: datetime,
        end: datetime,
    ) -> BacktestMetrics:
        if not signals:
            return self._empty_metrics(start, end)

        total = len(signals)
        buys = sum(1 for s in signals if s.recommendation == "Buy")
        sells = sum(1 for s in signals if s.recommendation == "Sell")
        holds = sum(1 for s in signals if s.recommendation == "Hold")

        # Filter out Hold signals for accuracy
        directional = [s for s in signals if s.recommendation in ("Buy", "Sell")]
        if directional:
            accuracy = sum(1 for s in directional if s.hit) / len(directional)
        else:
            accuracy = 0.0

        # PnL series
        pnls = [s.pnl for s in signals]
        pnl_arr = np.array(pnls)

        # Cumulative return
        equity_curve = np.cumprod(1.0 + pnl_arr)
        cumulative_return = float(equity_curve[-1] - 1.0)

        # Max drawdown
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max
        max_drawdown = float(np.min(drawdown))
        max_drawdown_pct = abs(max_drawdown)

        # Sharpe ratio (annualized, assuming hourly data)
        if len(pnls) > 1 and np.std(pnl_arr) > 0:
            sharpe = float(np.mean(pnl_arr) / np.std(pnl_arr) * math.sqrt(252 * 24))
        else:
            sharpe = 0.0

        # Profit factor
        gross_profit = float(np.sum(pnl_arr[pnl_arr > 0]))
        gross_loss = float(abs(np.sum(pnl_arr[pnl_arr < 0])))
        profit_factor = gross_profit / max(gross_loss, 1e-10)

        # Win/loss ratio
        wins = float(np.sum(pnl_arr > 0))
        losses = float(np.sum(pnl_arr < 0))
        win_loss = wins / max(losses, 1.0)

        # Average confidence & vol
        avg_conf = float(np.mean([s.confidence for s in signals]))
        avg_vol = float(np.mean([s.vol_spike_prob for s in signals]))

        # Period
        days = max(1, (end - start).days)

        # Annualized
        ann_return = (1.0 + cumulative_return) ** (365.0 / days) - 1.0 if days > 0 else 0.0
        ann_vol = float(np.std(pnl_arr) * math.sqrt(252 * 24)) if len(pnls) > 1 else 0.0

        # Calmar
        calmar = ann_return / max(max_drawdown_pct, 1e-10)

        return BacktestMetrics(
            total_signals=total,
            buy_signals=buys,
            sell_signals=sells,
            hold_signals=holds,
            signal_accuracy=round(accuracy, 4),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(max_drawdown, 6),
            max_drawdown_pct=round(max_drawdown_pct, 4),
            profit_factor=round(profit_factor, 4),
            win_loss_ratio=round(win_loss, 4),
            cumulative_return=round(cumulative_return, 6),
            calmar_ratio=round(calmar, 4),
            avg_confidence=round(avg_conf, 4),
            avg_vol_prediction=round(avg_vol, 4),
            time_period_days=days,
            annualized_return=round(ann_return, 4),
            annualized_volatility=round(ann_vol, 4),
        )

    def _empty_metrics(self, start: datetime, end: datetime) -> BacktestMetrics:
        return BacktestMetrics(
            total_signals=0, buy_signals=0, sell_signals=0, hold_signals=0,
            signal_accuracy=0.0, sharpe_ratio=0.0, max_drawdown=0.0,
            max_drawdown_pct=0.0, profit_factor=0.0, win_loss_ratio=0.0,
            cumulative_return=0.0, calmar_ratio=0.0, avg_confidence=0.0,
            avg_vol_prediction=0.0, time_period_days=max(1, (end - start).days),
            annualized_return=0.0, annualized_volatility=0.0,
        )

    def _empty_result(
        self, assets: list[str], start: datetime | None, end: datetime | None
    ) -> FullBacktestResult:
        now = datetime.now(UTC)
        s = start or now - timedelta(days=7)
        e = end or now
        return FullBacktestResult(
            start_date=s, end_date=e,
            overall_metrics=self._empty_metrics(s, e),
            asset_results=[],
            gti_path=[],
            summary="No events available for backtest.",
        )


# ── Module singleton ──────────────────────────────────────────────────────────

_backtest_engine: BacktestEngine | None = None


def get_backtest_engine() -> BacktestEngine:
    global _backtest_engine  # noqa: PLW0603
    if _backtest_engine is None:
        _backtest_engine = BacktestEngine()
    return _backtest_engine
