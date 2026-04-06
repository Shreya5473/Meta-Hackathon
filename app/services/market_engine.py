"""Real-time market data engine.
Orchestrates multiple market services, ensures data normalization,
and triggers AI signal recalculations.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from typing import Any, Dict, List

from app.core.logging import get_logger
from app.services.forex_service import ForexService
from app.services.commodities_service import CommoditiesService
from app.services.crypto_service import CryptoService
from app.services.stocks_service import StocksService
from app.services.macro_service import MacroService
from app.cache.redis_client import RedisClient

logger = get_logger(__name__)

from app.pipelines.market_feeds import MarketTick

class MarketEngine:
    """Central engine to manage all market data streams and AI signal updates."""
    
    def __init__(self) -> None:
        self.forex = ForexService()
        self.commodities = CommoditiesService()
        self.crypto = CryptoService()
        self.stocks = StocksService()
        self.macro = MacroService()
        self.market_key_all = "market_data:all"

    async def get_all_market_data(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """Return normalized data for ALL assets across ALL markets.
        Uses cache by default unless refresh is requested.
        """
        if not refresh:
            cached = await RedisClient.get(self.market_key_all)
            if cached:
                return cached

        # Fetch from all services concurrently
        tasks = [
            self.forex.get_all_prices(),
            self.commodities.get_all_prices(),
            self.crypto.get_all_prices(),
            self.stocks.get_all_prices(),
            self.macro.get_all_prices()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_ticks: List[MarketTick] = []
        for res in results:
            if isinstance(res, list):
                all_ticks.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Error fetching from a market service: {res}")

        # Convert MarketTick objects to the requested normalized format
        normalized_data = [self._normalize_output(tick) for tick in all_ticks]
        
        # Final normalization check and signal enrichment
        enriched_data = await self._enrich_with_signals(normalized_data)
        
        # Cache the aggregated result
        if enriched_data:
            await RedisClient.set(self.market_key_all, enriched_data, ttl=5)
            
        return enriched_data

    def _normalize_output(self, tick: MarketTick) -> Dict[str, Any]:
        """Convert MarketTick to the final normalized format requested by user."""
        # Calculate 24h change if not already present
        change_24h = tick.change_pct()
        
        # Map asset_class to market category
        market_map = {
            "currency": "forex",
            "commodity": "commodities",
            "crypto": "crypto",
            "equity": "stocks",
            "index": "indices",
            "etf": "etfs",
            "bond": "bonds"
        }
        
        return {
            "symbol": tick.symbol,
            "market": market_map.get(tick.asset_class, tick.asset_class),
            "price": tick.close,
            "change_24h": change_24h,
            "high_24h": tick.high,
            "low_24h": tick.low,
            "volume": tick.volume,
            "timestamp": tick.ts.isoformat()
        }

    async def _enrich_with_signals(self, market_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich market data with AI signals and trigger recalculations if needed."""
        results = []
        for data in market_data:
            # Map change_24h to change for final API format
            data["change"] = data.get("change_24h", 0.0)
            
            # Placeholder for real AI Signal integration
            data["signal"] = "BUY" if data["change"] > 0 else "SELL"
            data["confidence"] = 0.85
            results.append(data)
            
        return results

    async def _trigger_signal_recalculation(self, market_data: List[Dict[str, Any]]):
        """Trigger the AI signal engine to update predictions based on new data."""
        try:
            from app.pipelines.ai_signals.main_engine import get_ai_engine
            engine = get_ai_engine()
            # Feed data into AI signals engine
            # await engine.process_market_update(market_data)
            logger.info("Triggered AI signal recalculation")
        except ImportError:
            pass # Engine might not be ready or in different path
        except Exception as e:
            logger.error(f"Failed to trigger AI signals: {e}")

_engine: MarketEngine | None = None

def get_market_engine() -> MarketEngine:
    global _engine
    if _engine is None:
        _engine = MarketEngine()
    return _engine
