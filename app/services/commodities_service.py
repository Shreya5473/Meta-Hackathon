"""Commodities data service using Twelve Data or Alpha Vantage.
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

class CommoditiesService:
    """Service to handle all Commodities market data requests."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.twelvedata_api_key or self.settings.alphavantage_api_key
        self.base_url = "https://api.twelvedata.com" if self.settings.twelvedata_api_key else "https://www.alphavantage.co/query"
        self.market_key = "commodities"
        self.discovery_svc = get_asset_discovery_service()

    async def get_all_prices(self) -> List[MarketTick]:
        """Fetch latest quotes for all dynamically discovered Commodity assets."""
        asset_universe = await self.discovery_svc.get_asset_universe()
        comm_assets = asset_universe.get(self.market_key, [])
        symbols = [a["symbol"] for a in comm_assets]
        
        if not symbols:
            logger.warning("No commodity assets discovered, skipping price fetch.")
            return []

        # Try to get from cache first
        cache_key = f"market_data:{self.market_key}:all"
        cached_data = await RedisClient.get(cache_key)
        if cached_data:
            return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]

        if not self.api_key:
            logger.warning("No Commodities API key configured. Using fallbacks.")
            return self._get_fallbacks(symbols)

        results = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if "twelvedata" in self.base_url:
                    api_symbols = []
                    for s in symbols:
                        if s in ["XAUUSD", "XAGUSD"]:
                            api_symbols.append(f"{s[:3]}/{s[3:]}")
                        else:
                            api_symbols.append(s)
                            
                    sym_str = ",".join(api_symbols)
                    resp = await client.get(f"{self.base_url}/quote", params={
                        "symbol": sym_str,
                        "apikey": self.api_key
                    })
                    resp.raise_for_status()
                    data = resp.json()
                    
                    if len(api_symbols) == 1:
                        data = {api_symbols[0]: data}
                    
                    rev_map = {f"{s[:3]}/{s[3:]}": s for s in symbols if s in ["XAUUSD", "XAGUSD"]}
                    
                    for api_sym, quote in data.items():
                        internal_sym = rev_map.get(api_sym, api_sym)
                        if "price" in quote:
                            results.append(self._normalize_twelvedata(internal_sym, quote))
                else:
                    for sym in symbols:
                        resp = await client.get(self.base_url, params={
                            "function": "GLOBAL_QUOTE",
                            "symbol": sym,
                            "apikey": self.api_key
                        })
                        resp.raise_for_status()
                        data = resp.json()
                        if "Global Quote" in data:
                            results.append(self._normalize_alphavantage(sym, data["Global Quote"]))
            
            if results:
                await RedisClient.set(cache_key, [vars(r) for r in results], ttl=5)
                
        except Exception as e:
            logger.error(f"Error fetching Commodities quotes: {e}")
            if cached_data:
                return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]
            return self._get_fallbacks(symbols)

        return results

    def _normalize_twelvedata(self, symbol: str, quote: Dict[str, Any]) -> MarketTick:
        return MarketTick(
            symbol=symbol,
            asset_class="commodity",
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
        price = float(quote.get("05. price") or 0)
        return MarketTick(
            symbol=symbol,
            asset_class="commodity",
            region="global",
            ts=datetime.now(UTC),
            open=float(quote.get("02. open") or price),
            high=float(quote.get("03. high") or price),
            low=float(quote.get("04. low") or price),
            close=price,
            volume=float(quote.get("06. volume") or 0),
            source="alphavantage"
        )

    def _get_fallbacks(self, symbols: List[str]) -> List[MarketTick]:
        bases = {
            "XAUUSD": 2340.0, "XAGUSD": 29.5, "WTI": 82.0, "BRENT": 86.5, "NATGAS": 2.2,
            "PLATINUM": 950.0, "PALLADIUM": 1000.0, "COPPER": 4.5, "CORN": 430.0,
            "WHEAT": 580.0, "SOYBEANS": 1150.0, "COFFEE": 220.0, "SUGAR": 20.0, "COTTON": 80.0
        }
        return [
            MarketTick(
                symbol=sym,
                asset_class="commodity",
                region="global",
                ts=datetime.now(UTC),
                open=bases.get(sym, 1.0),
                high=bases.get(sym, 1.0) * 1.05,
                low=bases.get(sym, 1.0) * 0.95,
                close=bases.get(sym, 1.0),
                volume=100000.0,
                source="fallback"
            )
            for sym in symbols
        ]
