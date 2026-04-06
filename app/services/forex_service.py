"""Forex data service using Twelve Data or Alpha Vantage.
Ensures real-time updates and normalization.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from typing import Any, Dict, List

import httpx
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.asset_discovery_service import get_asset_discovery_service

logger = get_logger(__name__)

from app.pipelines.market_feeds import MarketTick

class ForexService:
    """Service to handle all Forex market data requests."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.twelvedata_api_key or self.settings.alphavantage_api_key
        self.base_url = "https://api.twelvedata.com" if self.settings.twelvedata_api_key else "https://www.alphavantage.co/query"
        self.market_key = "forex"
        self.discovery_svc = get_asset_discovery_service()

    async def get_all_prices(self) -> List[MarketTick]:
        """Fetch latest quotes for all dynamically discovered Forex pairs."""
        asset_universe = await self.discovery_svc.get_asset_universe()
        forex_assets = asset_universe.get(self.market_key, [])
        symbols = [a["symbol"] for a in forex_assets]
        
        if not symbols:
            logger.warning("No forex assets discovered, skipping price fetch.")
            return []

        # Try to get from cache first
        cache_key = f"market_data:{self.market_key}:all"
        cached_data = await RedisClient.get(cache_key)
        if cached_data:
            return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]

        if not self.api_key:
            logger.warning("No Forex API key configured. Using fallbacks.")
            return self._get_fallbacks(symbols)

        results = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if "twelvedata" in self.base_url:
                    sym_str = ",".join(symbols)
                    resp = await client.get(f"{self.base_url}/quote", params={
                        "symbol": sym_str,
                        "apikey": self.api_key
                    })
                    resp.raise_for_status()
                    data = resp.json()
                    
                    if len(symbols) == 1:
                        data = {symbols[0]: data}
                    
                    for sym, quote in data.items():
                        if "price" in quote:
                            results.append(self._normalize_twelvedata(sym, quote))
                else:
                    for sym in symbols:
                        resp = await client.get(self.base_url, params={
                            "function": "CURRENCY_EXCHANGE_RATE",
                            "from_currency": sym[:3],
                            "to_currency": sym[3:],
                            "apikey": self.api_key
                        })
                        resp.raise_for_status()
                        data = resp.json()
                        if "Realtime Currency Exchange Rate" in data:
                            results.append(self._normalize_alphavantage(sym, data["Realtime Currency Exchange Rate"]))
            
            if results:
                await RedisClient.set(cache_key, [vars(r) for r in results], ttl=5)
                
        except Exception as e:
            logger.error(f"Error fetching Forex quotes: {e}")
            if cached_data:
                return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]
            return self._get_fallbacks(symbols)

        return results

    def _normalize_twelvedata(self, symbol: str, quote: Dict[str, Any]) -> MarketTick:
        return MarketTick(
            symbol=symbol,
            asset_class="currency",
            region="global",
            ts=datetime.now(UTC),
            open=float(quote.get("open") or 0),
            high=float(quote.get("high") or 0),
            low=float(quote.get("low") or 0),
            close=float(quote.get("close") or quote.get("price") or 0),
            volume=float(quote.get("volume") or 0),
            source="twelvedata"
        )

    def _normalize_alphavantage(self, symbol: str, quote: Dict[str, Any]) -> MarketTick:
        price = float(quote.get("5. Exchange Rate") or 0)
        return MarketTick(
            symbol=symbol,
            asset_class="currency",
            region="global",
            ts=datetime.now(UTC),
            open=price,
            high=price,
            low=price,
            close=price,
            volume=0.0,
            source="alphavantage"
        )

    def _get_fallbacks(self, symbols: List[str]) -> List[MarketTick]:
        bases = {
            "EURUSD": 1.085, "GBPUSD": 1.27, "USDJPY": 150.5, "USDCHF": 0.895,
            "USDCAD": 1.365, "AUDUSD": 0.665, "NZDUSD": 0.615
        }
        return [
            MarketTick(
                symbol=sym,
                asset_class="currency",
                region="global",
                ts=datetime.now(UTC),
                open=bases.get(sym, 1.0),
                high=bases.get(sym, 1.0) * 1.01,
                low=bases.get(sym, 1.0) * 0.99,
                close=bases.get(sym, 1.0),
                volume=1000000.0,
                source="fallback"
            )
            for sym in symbols
        ]
