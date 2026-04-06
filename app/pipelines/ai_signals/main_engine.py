"""Main orchestration engine for AI Signals.

Integrates all layers: data ingestion, feature engineering, multi-model engine,
trade construction, confidence engine, and AI reasoning.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.pipelines.market_feeds import get_feed_manager
from app.pipelines.macro_data import get_macro_service
from app.pipelines.geopolitical_news import get_geopolitical_news_service
from app.pipelines.feature_engineering import get_feature_service, EnhancedAssetFeatures
from app.pipelines.ai_signals.multi_model_engine import get_model_engine
from app.pipelines.ai_signals.trade_engine import get_trade_engine
from app.pipelines.ai_signals.reasoning_engine import get_reasoning_engine
from app.schemas.signal import AssetSignalSchema

logger = get_logger(__name__)

class AISignalsEngine:
    def __init__(self) -> None:
        self.feed_mgr = get_feed_manager()
        self.macro_svc = get_macro_service()
        self.news_svc = get_geopolitical_news_service()
        self.feature_svc = get_feature_service()
        self.model_engine = get_model_engine()
        self.trade_engine = get_trade_engine()
        self.reasoning_engine = get_reasoning_engine()

    async def generate_all_signals(self, region: str = "global") -> list[AssetSignalSchema]:
        """Orchestrate the full signal generation pipeline for all tracked assets."""
        # 1. Fetch live market data (OHLC, price, volume)
        live_ticks = self.feed_mgr.get_all()
        if not live_ticks:
            logger.warning("No live market data available for signal generation.")
            return []

        # 2. Fetch Macro and News data (parallel)
        macro_task = self.macro_svc.get_all_macro_indicators()
        news_task = self.news_svc.fetch_geopolitical_news()
        macro_indicators, news_articles = await asyncio.gather(macro_task, news_task)

        # 3. Compute aggregate sentiment and macro strength
        sentiment_score = self.feature_svc.compute_sentiment_score(news_articles, region)
        macro_strength = self.feature_svc.compute_macro_strength(macro_indicators, region)
        
        # 4. Process each asset
        signals: list[AssetSignalSchema] = []
        for tick in live_ticks:
            try:
                # Use tick.close if tick.price is missing
                price = getattr(tick, "price", getattr(tick, "close", 0.0))
                if price == 0.0:
                    continue

                # 4a. Build features
                # In real implementation, we'd fetch high/low/close history for ATR
                # Using dummy history for now based on current price
                history = [price * (1 + (i/1000.0)) for i in range(-20, 1)]
                atr = self.feature_svc.calculate_atr(history, history, history)
                vol_regime = self.feature_svc.calculate_volatility_regime([price])
                
                features = EnhancedAssetFeatures(
                    symbol=tick.symbol,
                    asset_class=tick.asset_class,
                    price=price,
                    returns_short_term=0.01, # dummy 1d return
                    returns_long_term=0.05,  # dummy 5d return
                    atr=atr if atr > 0 else tick.price * 0.02,
                    volatility_regime=vol_regime,
                    sentiment_score=sentiment_score,
                    geopolitical_tension_index=25.0, # fallback GTI
                    macro_strength_score=macro_strength,
                    rsi=0.5,
                    macd=0.0,
                    bb_pct_b=0.5
                )

                # 4b. Run models
                model_output = self.model_engine.ensemble_signals(features)

                # 4c. Construct trade and calculate confidence
                trade_setup = self.trade_engine.construct_trade(features, model_output)

                # 4d. Generate AI reasoning
                trigger_event = news_articles[0].title if news_articles else "Market volatility"
                reasoning = self.reasoning_engine.generate_reasoning(features, model_output, trigger_event)

                # 4e. Build final schema
                signal_schema = AssetSignalSchema(
                    symbol=tick.symbol,
                    asset=tick.symbol,
                    region=region,
                    sector=getattr(tick, "sector", "General"),
                    vol_spike_prob_24h=model_output.volatility_score,
                    directional_bias=model_output.direction_prob if model_output.direction == "BUY" else -model_output.direction_prob,
                    sector_stress=0.2,
                    uncertainty=1.0 - model_output.direction_prob,
                    recommendation=model_output.direction,
                    signal=model_output.direction,
                    confidence=trade_setup.confidence,
                    bullish_strength=model_output.bullish_strength,
                    bearish_strength=model_output.bearish_strength,
                    volatility=model_output.volatility,
                    triggering_event=trigger_event,
                    entry=trade_setup.entry,
                    stop_loss=trade_setup.stop_loss,
                    target=trade_setup.target,
                    risk_reward=trade_setup.risk_reward,
                    atr=trade_setup.atr,
                    max_position=trade_setup.max_position,
                    reasoning=reasoning,
                    confidence_score=trade_setup.confidence / 100.0,
                    model_version="AI_ENGINE_V1",
                    ts=datetime.now(UTC)
                )
                signals.append(signal_schema)

            except Exception as e:
                logger.error(f"Error generating signal for {tick.symbol}: {e}")
                continue

        return signals

_ai_signals_engine: AISignalsEngine | None = None

def get_ai_signals_engine() -> AISignalsEngine:
    global _ai_signals_engine
    if _ai_signals_engine is None:
        _ai_signals_engine = AISignalsEngine()
    return _ai_signals_engine
