"""Stocks and Indices data service using Polygon or Twelve Data.
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

class StocksService:
    """Service to handle all Stocks and Indices market data requests."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.polygon_api_key or self.settings.twelvedata_api_key
        self.base_url = "https://api.polygon.io" if self.settings.polygon_api_key else "https://api.twelvedata.com"
        self.market_key_stocks = "stocks"
        self.market_key_indices = "indices"
        self.market_key_etfs = "etfs"
        self.discovery_svc = get_asset_discovery_service()

    async def get_all_prices(self) -> List[MarketTick]:
        """Fetch latest quotes for all dynamically discovered Stocks, Indices, and ETFs."""
        asset_universe = await self.discovery_svc.get_asset_universe()
        symbols_stocks = [a["symbol"] for a in asset_universe.get(self.market_key_stocks, [])]
        symbols_indices = [a["symbol"] for a in asset_universe.get(self.market_key_indices, [])]
        symbols_etfs = [a["symbol"] for a in asset_universe.get(self.market_key_etfs, [])]
        all_symbols = symbols_stocks + symbols_indices + symbols_etfs

        if not all_symbols:
            logger.warning("No stock/index/etf assets discovered, skipping price fetch.")
            return []
        
        # Try to get from cache first
        cache_key = "market_data:stocks_indices_etfs:all"
        cached_data = await RedisClient.get(cache_key)
        if cached_data:
            return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]

        if not self.api_key:
            logger.warning("No Stocks/Indices API key configured. Using fallbacks.")
            return self._get_fallbacks(all_symbols)

        results = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if "polygon" in self.base_url:
                    sym_str = ",".join(all_symbols)
                    resp = await client.get(f"{self.base_url}/v2/snapshot/locale/us/markets/stocks/tickers", params={
                        "tickers": sym_str,
                        "apiKey": self.api_key
                    })
                    resp.raise_for_status()
                    data = resp.json()
                    
                    for ticker in data.get("tickers", []):
                        sym = ticker["ticker"]
                        results.append(self._normalize_polygon(sym, ticker))
                else:
                    sym_str = ",".join(all_symbols)
                    resp = await client.get(f"{self.base_url}/quote", params={
                        "symbol": sym_str,
                        "apikey": self.api_key
                    })
                    resp.raise_for_status()
                    data = resp.json()
                    
                    if len(all_symbols) == 1:
                        data = {all_symbols[0]: data}
                    
                    for sym, quote in data.items():
                        if "price" in quote:
                            results.append(self._normalize_twelvedata(sym, quote))
            
            if results:
                await RedisClient.set(cache_key, [vars(r) for r in results], ttl=5)
                
        except Exception as e:
            logger.error(f"Error fetching Stocks/Indices quotes: {e}")
            if cached_data:
                return [MarketTick(**d) if isinstance(d, dict) else d for d in cached_data]
            return self._get_fallbacks(all_symbols)

        return results

    def _normalize_polygon(self, symbol: str, ticker: Dict[str, Any]) -> MarketTick:
        last_trade = ticker.get("lastTrade", {})
        day = ticker.get("day", {})
        
        asset_class = "equity"
        if symbol in [a["symbol"] for a in ASSETS["indices"]]:
            asset_class = "index"
        elif symbol in [a["symbol"] for a in ASSETS["etfs"]]:
            asset_class = "etf"
            
        return MarketTick(
            symbol=symbol,
            asset_class=asset_class,
            region="americas",
            ts=datetime.now(UTC),
            open=float(day.get("o") or 0),
            high=float(day.get("h") or 0),
            low=float(day.get("l") or 0),
            close=float(last_trade.get("p") or 0),
            volume=float(day.get("v") or 0),
            source="polygon"
        )

    def _normalize_twelvedata(self, symbol: str, quote: Dict[str, Any]) -> MarketTick:
        asset_class = "equity"
        if symbol in [a["symbol"] for a in ASSETS["indices"]]:
            asset_class = "index"
        elif symbol in [a["symbol"] for a in ASSETS["etfs"]]:
            asset_class = "etf"
            
        return MarketTick(
            symbol=symbol,
            asset_class=asset_class,
            region="americas",
            ts=datetime.now(UTC),
            open=float(quote.get("open") or 0),
            high=float(quote.get("high") or 0),
            low=float(quote.get("low") or 0),
            close=float(quote.get("close") or quote.get("price") or 0),
            volume=float(quote.get("volume") or 0),
            source="twelvedata"
        )

    def _get_fallbacks(self, symbols: List[str]) -> List[MarketTick]:
        return [
            MarketTick(
                symbol=sym,
                asset_class="equity",
                region="americas",
                ts=datetime.now(UTC),
                open=100.0,
                high=105.0,
                low=95.0,
                close=100.0,
                volume=100000.0,
                source="fallback"
            )
            for sym in symbols
        ]
