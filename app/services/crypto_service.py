"""Crypto data service using Binance API.
Ensures real-time updates and normalization.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from typing import Any, Dict, List

import httpx
from app.core.logging import get_logger
from app.services.asset_discovery_service import get_asset_discovery_service

logger = get_logger(__name__)

from app.pipelines.market_feeds import MarketTick

class CryptoService:
    """Service to handle all Crypto market data requests."""
    
    def __init__(self) -> None:
        self.rest_url = "https://api.binance.com/api/v3"
        self.market_key = "crypto"
        self.discovery_svc = get_asset_discovery_service()

    async def get_all_prices(self) -> List[MarketTick]:
        """Fetch latest quotes for all dynamically discovered crypto assets."""
        asset_universe = await self.discovery_svc.get_asset_universe()
        crypto_assets = asset_universe.get(self.market_key, [])
        symbols = [a["symbol"] for a in crypto_assets]
        
        if not symbols:
            logger.warning("No crypto assets discovered, skipping price fetch.")
            return []

        # Try to get from cache first
        cache_key = f"market_data:{self.market_key}:all"
        cached_data = await RedisClient.get(cache_key)
        if cached_data:
            # Convert back to MarketTick if it was cached as dict
            return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]

        results = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.rest_url}/ticker/24hr")
                resp.raise_for_status()
                data = resp.json()
                
                symbol_map = {f"{sym}USDT": sym for sym in symbols}
                for ticker in data:
                    binance_sym = ticker["symbol"]
                    if binance_sym in symbol_map:
                        internal_sym = symbol_map[binance_sym]
                        normalized = self._normalize(internal_sym, ticker)
                        results.append(normalized)
            
            if results:
                # Cache as dicts for msgpack compatibility
                await RedisClient.set(cache_key, [vars(r) for r in results], ttl=5)
                
        except Exception as e:
            logger.error(f"Error fetching Crypto quotes: {e}")
            if cached_data:
                return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]
            return self._get_fallbacks(symbols)

        return results

    def _normalize(self, symbol: str, ticker: Dict[str, Any]) -> MarketTick:
        """Normalize Binance data into MarketTick format."""
        return MarketTick(
            symbol=symbol,
            asset_class="crypto",
            region="global",
            ts=datetime.now(UTC),
            open=float(ticker.get("openPrice") or 0),
            high=float(ticker.get("highPrice") or 0),
            low=float(ticker.get("lowPrice") or 0),
            close=float(ticker.get("lastPrice") or 0),
            volume=float(ticker.get("volume") or 0),
            source="binance:rest"
        )

    def _get_fallbacks(self, symbols: List[str]) -> List[MarketTick]:
        """Return fallback data if API fails."""
        bases = {
            "BTC": 68000.0, "ETH": 3500.0, "BNB": 600.0, "SOL": 150.0, "XRP": 0.5,
            "ADA": 0.45, "DOGE": 0.15, "AVAX": 40.0, "MATIC": 0.7, "DOT": 7.0,
            "LTC": 85.0, "LINK": 15.0
        }
        return [
            MarketTick(
                symbol=sym,
                asset_class="crypto",
                region="global",
                ts=datetime.now(UTC),
                open=bases.get(sym, 1.0),
                high=bases.get(sym, 1.0) * 1.05,
                low=bases.get(sym, 1.0) * 0.95,
                close=bases.get(sym, 1.0),
                volume=1000000.0,
                source="fallback"
            )
            for sym in symbols
        ]
