"""Market signal service — generates and persists asset-level impact signals.

Enhanced to use the TradingSignalGenerator for richer signal output
with reasoning chains and impact graph integration.

Real market prices are sourced from the MarketFeedManager (Finnhub live adapter).
Live Finnhub technical indicators (RSI-14, MACD signal diff, Bollinger %B) are
fetched per-symbol and injected into the ML feature vector before prediction.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.core.audit import build_audit_meta
from app.core.logging import get_logger
from app.models.signal import MarketSignal
from app.pipelines.ai_signals.main_engine import get_ai_signals_engine
from app.pipelines.live_indicators import FinnhubLiveIndicators
from app.pipelines.signal_generator import get_signal_generator
from app.repositories.gti_repo import GTIRepository
from app.repositories.market_repo import MarketDataRepository
from app.repositories.signal_repo import MarketSignalRepository
from app.schemas.signal import AssetSignalSchema, SignalAssetsResponse

logger = get_logger(__name__)


class MarketSignalService:
    def __init__(
        self,
        signal_repo: MarketSignalRepository,
        gti_repo: GTIRepository,
        market_repo: MarketDataRepository,
    ) -> None:
        self.signal_repo = signal_repo
        self.gti_repo = gti_repo
        self.market_repo = market_repo
        self.ai_engine = get_ai_signals_engine()

    async def get_signals(
        self,
        region: str | None = None,
        timeframe: str = "24h",
    ) -> SignalAssetsResponse:
        timeframe_hours = self._parse_timeframe(timeframe)
        signals = await self.signal_repo.get_latest_per_symbol(
            region=region, timeframe_hours=timeframe_hours
        )

        # If no persisted signals, compute on-demand
        if not signals:
            await self._compute_signals(region=region or "global")
            signals = await self.signal_repo.get_latest_per_symbol(
                region=region, timeframe_hours=timeframe_hours
            )

        signal_schemas = [
            AssetSignalSchema(
                symbol=s.symbol,
                asset=s.symbol,
                region=s.region,
                sector=s.sector,
                vol_spike_prob_24h=s.vol_spike_prob_24h,
                directional_bias=s.directional_bias,
                sector_stress=s.sector_stress,
                uncertainty=s.uncertainty,
                recommendation=s.recommendation,
                signal=s.recommendation.upper(),
                confidence=s.confidence,
                bullish_strength=s.bullish_strength,
                bearish_strength=s.bearish_strength,
                volatility=s.volatility,
                triggering_event=s.triggering_event,
                entry=s.entry,
                stop_loss=s.stop_loss,
                target=s.target,
                risk_reward=s.risk_reward,
                atr=s.atr,
                max_position=s.max_position,
                reasoning=s.reasoning,
                confidence_score=s.confidence / 100.0 if s.confidence else 0.0,
                model_version=s.model_version,
                ts=s.ts,
            )
            for s in signals
        ]

        audit = build_audit_meta()
        return SignalAssetsResponse(
            region=region,
            timeframe=timeframe,
            signals=signal_schemas,
            count=len(signal_schemas),
            model_version="AI_ENGINE_V1",
            pipeline_version="1.0.0",
            data_as_of=datetime.now(UTC).isoformat(),
            **audit,
        )

    async def _compute_signals(self, region: str = "global") -> None:
        """Compute signals for all tracked assets using the new AI Signals Engine."""
        # Use the new AI Signals Engine
        new_signals = await self.ai_engine.generate_all_signals(region=region)
        
        # Persist to DB
        db_signals = []
        for s in new_signals:
            db_signal = MarketSignal(
                symbol=s.symbol,
                region=s.region,
                sector=s.sector,
                vol_spike_prob_24h=s.vol_spike_prob_24h,
                directional_bias=s.directional_bias,
                sector_stress=s.sector_stress,
                uncertainty=s.uncertainty,
                recommendation=s.recommendation,
                confidence=s.confidence,
                bullish_strength=s.bullish_strength,
                bearish_strength=s.bearish_strength,
                volatility=s.volatility,
                triggering_event=s.triggering_event,
                entry=s.entry,
                stop_loss=s.stop_loss,
                target=s.target,
                risk_reward=s.risk_reward,
                atr=s.atr,
                max_position=s.max_position,
                reasoning=s.reasoning,
                model_version=s.model_version,
                ts=s.ts
            )
            db_signals.append(db_signal)
        
        if db_signals:
            await self.signal_repo.create_many(db_signals)
            logger.info(f"Computed and persisted {len(db_signals)} signals for region: {region}")

    async def get_enhanced_signals(
        self,
        region: str | None = None,
    ) -> dict:
        """Generate enhanced signals with full reasoning chains using the
        TradingSignalGenerator + ImpactGraph."""

        gti_snap = await self.gti_repo.get_latest(region or "global")
        gti_val = gti_snap.gti_value if gti_snap else 25.0
        gti_delta = gti_snap.gti_delta_1h if gti_snap else 0.0
        gti_conf = gti_snap.confidence if gti_snap else 0.5

        # Use the signal generator
        generator = get_signal_generator()

        # Focus universe: 5 commodities + 6 defense stocks (all tracked + polled)
        default_assets = [
            "XAUUSD", "XAGUSD", "WTI", "NATGAS", "BTCUSD",
            "LMT", "RTX", "NOC", "GD", "BA", "ITA",
        ]
        _indicator_svc = FinnhubLiveIndicators(api_key="")  # auto-rotates both keys
        import asyncio
        indicator_results = await asyncio.gather(
            *[_indicator_svc.fetch(sym) for sym in default_assets],
            return_exceptions=True,
        )
        live_indicators: dict[str, dict[str, float]] = {}
        for sym, result in zip(default_assets, indicator_results):
            if isinstance(result, dict):
                live_indicators[sym] = result

        # Generate signals with live technical indicators injected
        batch = generator.generate_signals_for_event(
            event_title="Ongoing geopolitical tensions",
            event_category="political_instability",
            source_country="USA",
            severity=gti_val / 100.0,
            gti_value=gti_val,
            gti_delta=gti_delta,
            gti_confidence=gti_conf,
            live_indicators=live_indicators,
        )

        return {
            "signals": [
                {
                    "asset": s.asset,
                    "asset_class": s.asset_class,
                    "action": s.action,
                    "confidence_pct": s.confidence_pct,
                    "uncertainty_pct": s.uncertainty_pct,
                    "reasoning_summary": s.reasoning_summary,
                    "reasoning_chain": [
                        {
                            "step_number": rs.step_number,
                            "description": rs.description,
                            "evidence": rs.evidence,
                            "confidence_contribution": rs.confidence_contribution,
                        }
                        for rs in s.reasoning_chain
                    ],
                    "triggering_event": s.triggering_event,
                    "event_category": s.event_category,
                    "impact_path": s.impact_path,
                    "vol_spike_prob": s.vol_spike_prob,
                    "directional_bias": s.directional_bias,
                    "sector_stress": s.sector_stress,
                    "price_direction": s.price_direction,
                    "expected_magnitude": s.expected_magnitude,
                    "time_horizon": s.time_horizon,
                    "related_assets": s.related_assets,
                    "bullish_strength": s.bullish_strength,
                    "bearish_strength": s.bearish_strength,
                    "volatility": s.volatility,
                    "entry": s.entry,
                    "stop_loss": s.stop_loss,
                    "target": s.target,
                    "risk_reward": s.risk_reward,
                    "atr": s.atr,
                    "max_position": s.max_position,
                    "generated_at": s.generated_at.isoformat(),
                }
                for s in batch.signals
            ],
            "global_tension_index": batch.global_tension_index,
            "event_count": batch.event_count,
            "timestamp": batch.timestamp.isoformat(),
        }

    @staticmethod
    def _parse_timeframe(timeframe: str) -> int:
        mapping = {"1h": 1, "4h": 4, "24h": 24, "7d": 168, "30d": 720}
        return mapping.get(timeframe, 24)
