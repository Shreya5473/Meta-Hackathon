"""Macro data ingestion layer.

Fetches interest rates, inflation (CPI), GDP growth, and other macro proxies
using the FRED (Federal Reserve Economic Data) API.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class MacroIndicator(BaseModel):
    symbol: str
    name: str
    value: float
    unit: str
    updated_at: datetime
    region: str = "global"

# FRED Series IDs for key macro indicators
FRED_SERIES_MAP = {
    "FEDFUNDS": {"name": "Federal Funds Effective Rate", "unit": "percent", "region": "americas"},
    "CPIAUCSL": {"name": "Consumer Price Index for All Urban Consumers", "unit": "index", "region": "americas"},
    "DGS10":    {"name": "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity", "unit": "percent", "region": "americas"},
    "UNRATE":   {"name": "Unemployment Rate", "unit": "percent", "region": "americas"},
    "WALCL":    {"name": "Assets: Total Assets: Total Assets (Less Eliminations from Consolidation): Wednesday Level", "unit": "millions of dollars", "region": "americas"},
    "T10Y2Y":   {"name": "10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity", "unit": "percent", "region": "americas"},
}

class MacroDataService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.fred_api_key.get_secret_value() if self.settings.fred_api_key else ""
        self.base_url = "https://api.stlouisfed.org/fred/series/observations"

    async def fetch_indicator(self, series_id: str) -> MacroIndicator | None:
        """Fetch the latest observation for a FRED series."""
        if not self.api_key:
            logger.warning("FRED API key not configured. Skipping macro fetch.")
            return self._get_fallback_macro(series_id)

        cache_key = f"macro_fred_{series_id}"
        cached = await cache_get(cache_key)
        if cached:
            return MacroIndicator(**cached)

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                if not data.get("observations"):
                    return None
                
                latest = data["observations"][0]
                meta = FRED_SERIES_MAP.get(series_id, {"name": series_id, "unit": "N/A", "region": "global"})
                
                indicator = MacroIndicator(
                    symbol=series_id,
                    name=meta["name"],
                    value=float(latest["value"]),
                    unit=meta["unit"],
                    updated_at=datetime.fromisoformat(latest["date"]),
                    region=meta["region"]
                )
                
                await cache_set(cache_key, indicator.model_dump(mode="json"), ttl=3600 * 12)  # 12h cache
                return indicator

        except Exception as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            return self._get_fallback_macro(series_id)

    async def get_all_macro_indicators(self) -> list[MacroIndicator]:
        """Fetch all configured macro indicators."""
        tasks = [self.fetch_indicator(sid) for sid in FRED_SERIES_MAP.keys()]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    def _get_fallback_macro(self, series_id: str) -> MacroIndicator | None:
        """Provide reasonable fallback values if API is down or key missing."""
        fallbacks = {
            "FEDFUNDS": 5.33,
            "CPIAUCSL": 310.0,
            "DGS10": 4.5,
            "UNRATE": 3.9,
            "WALCL": 7500000.0,
            "T10Y2Y": -0.35,
        }
        if series_id in fallbacks:
            meta = FRED_SERIES_MAP[series_id]
            return MacroIndicator(
                symbol=series_id,
                name=meta["name"],
                value=fallbacks[series_id],
                unit=meta["unit"],
                updated_at=datetime.now(),
                region=meta["region"]
            )
        return None

_macro_service: MacroDataService | None = None

def get_macro_service() -> MacroDataService:
    global _macro_service
    if _macro_service is None:
        _macro_service = MacroDataService()
    return _macro_service
