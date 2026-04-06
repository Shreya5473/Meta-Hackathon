"""Forex data service — fetches real-time FX rates.

Uses Twelve Data or Alpha Vantage for major/minor/cross pairs.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from typing import Any, Dict, List

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.config.asset_universe import ASSET_UNIVERSE

logger = get_logger(__name__)

class ForexService:
    """Service to handle all Forex market data requests."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.twelvedata_api_key or self.settings.alphavantage_api_key
        self.base_url = "https://api.twelvedata.com" if self.settings.twelvedata_api_key else "https://www.alphavantage.co/query"

    async def fetch_latest_quotes(self, symbols: List[str] | None = None) -> List[Dict[str, Any]]:
        """Fetch the latest quotes for the given Forex symbols."""
        if not symbols:
            symbols = [a["symbol"] for a in ASSET_UNIVERSE["forex"]]
        
        if not self.api_key:
            logger.warning("No Forex API key configured (TwelveData or AlphaVantage). Using fallback data.")
            return self._get_fallback_quotes(symbols)

        # Batching if supported by provider
        # Twelve Data supports comma-separated symbols
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
                    
                    # Handle single vs multiple symbol response
                    if len(symbols) == 1:
                        data = {symbols[0]: data}
                    
                    for sym, quote in data.items():
                        if "price" in quote:
                            results.append(self._normalize_twelvedata(sym, quote))
                else:
                    # Alpha Vantage - one by one for now (or use batch endpoint if available)
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
        except Exception as e:
            logger.error(f"Error fetching Forex quotes: {e}")
            return self._get_fallback_quotes(symbols)

        return results

    def _normalize_twelvedata(self, symbol: str, quote: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "market": "forex",
            "price": float(quote.get("close") or quote.get("price") or 0),
            "change_24h": float(quote.get("percent_change") or 0),
            "high_24h": float(quote.get("high") or 0),
            "low_24h": float(quote.get("low") or 0),
            "volume": float(quote.get("volume") or 0),
            "timestamp": datetime.now(UTC).isoformat()
        }

    def _normalize_alphavantage(self, symbol: str, quote: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "market": "forex",
            "price": float(quote.get("5. Exchange Rate") or 0),
            "change_24h": 0.0, # Alpha Vantage quote doesn't provide % change directly in basic rate call
            "high_24h": 0.0,
            "low_24h": 0.0,
            "volume": 0.0,
            "timestamp": datetime.now(UTC).isoformat()
        }

    def _get_fallback_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        # Hardcoded realistic base prices for fallback
        bases = {
            "EURUSD": 1.085, "GBPUSD": 1.265, "USDJPY": 151.5, "USDCHF": 0.885, "USDCAD": 1.355,
            "AUDUSD": 0.655, "NZDUSD": 0.605, "EURGBP": 0.855, "EURJPY": 164.5, "GBPJPY": 192.0
        }
        results = []
        now = datetime.now(UTC).isoformat()
        for sym in symbols:
            base = bases.get(sym, 1.0)
            results.append({
                "symbol": sym,
                "market": "forex",
                "price": base,
                "change_24h": 0.0,
                "high_24h": base * 1.005,
                "low_24h": base * 0.995,
                "volume": 0.0,
                "timestamp": now
            })
        return results

_forex_service: ForexService | None = None

def get_forex_service() -> ForexService:
    global _forex_service
    if _forex_service is None:
        _forex_service = ForexService()
    return _forex_service
