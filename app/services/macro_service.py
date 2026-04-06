"""Macro data service using FRED API for Bonds and Yields.
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

class MacroService:
    """Service to handle all Macro (Bonds/Yields) market data requests."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.fred_api_key
        self.base_url = "https://api.stlouisfed.org/fred"
        self.market_key = "bonds"
        self.discovery_svc = get_asset_discovery_service()
        
        # FRED series mapping is now for normalization, not discovery
        self.fred_map = {
            "US02Y": "DGS2",
            "US05Y": "DGS5",
            "US10Y": "DGS10",
            "US30Y": "DGS30",
            "DE10Y": "IRLTLT01DEM156N",
            "GB10Y": "IRLTLT01GBM156N",
            "IN10Y": "IRLTLT01INM156N",
        }

    async def get_all_prices(self) -> List[MarketTick]:
        """Fetch latest yields for all dynamically discovered Bond assets."""
        asset_universe = await self.discovery_svc.get_asset_universe()
        bond_assets = asset_universe.get(self.market_key, [])
        symbols = [a["symbol"] for a in bond_assets]

        if not symbols:
            logger.warning("No bond assets discovered, skipping price fetch.")
            return []
        
        # Try to get from cache first
        cache_key = f"market_data:{self.market_key}:all"
        cached_data = await RedisClient.get(cache_key)
        if cached_data:
            return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]

        if not self.api_key:
            logger.warning("No FRED API key configured. Using fallbacks.")
            return self._get_fallbacks(symbols)

        results = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for sym_info in bond_assets:
                    sym = sym_info["symbol"]
                    fred_id = self.fred_map.get(sym, sym) # Use symbol as ID if not in map
                    
                    resp = await client.get(f"{self.base_url}/series/observations", params={
                        "series_id": fred_id,
                        "api_key": self.api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 2
                    })
                    resp.raise_for_status()
                    data = resp.json()
                    observations = data.get("observations", [])
                    
                    if observations:
                        results.append(self._normalize_fred(sym, observations))
            
            if results:
                await RedisClient.set(cache_key, [vars(r) for r in results], ttl=300)
                
        except Exception as e:
            logger.error(f"Error fetching Macro data: {e}")
            if cached_data:
                return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]
            return self._get_fallbacks(symbols)

        return results

    def _normalize_fred(self, symbol: str, observations: List[Dict[str, Any]]) -> MarketTick:
        latest = observations[0]
        prev = observations[1] if len(observations) > 1 else latest
        
        try:
            price = float(latest.get("value") or 0)
            prev_price = float(prev.get("value") or price)
        except ValueError:
            price = 0.0
            prev_price = 0.0
            
        return MarketTick(
            symbol=symbol,
            asset_class="bond",
            region="global",
            ts=datetime.now(UTC),
            open=prev_price,
            high=max(price, prev_price),
            low=min(price, prev_price),
            close=price,
            volume=0.0,
            source="fred"
        )

    def _get_fallbacks(self, symbols: List[str]) -> List[MarketTick]:
        bases = {
            "US02Y": 4.5, "US05Y": 4.2, "US10Y": 4.1, "US30Y": 4.3,
            "DE10Y": 2.4, "GB10Y": 4.0, "IN10Y": 7.0
        }
        return [
            MarketTick(
                symbol=sym,
                asset_class="bond",
                region="global",
                ts=datetime.now(UTC),
                open=bases.get(sym, 4.0),
                high=bases.get(sym, 4.0) * 1.01,
                low=bases.get(sym, 4.0) * 0.99,
                close=bases.get(sym, 4.0),
                volume=0.0,
                source="fallback"
            )
            for sym in symbols
        ]
