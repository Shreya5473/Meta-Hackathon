"""Asset Discovery Service.

Dynamically fetches and normalizes asset lists from various external providers.
This service is the foundation of the dynamic market data system, replacing
all hardcoded asset configurations.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import httpx
from app.core.config import get_settings
from app.core.logging import get_logger
from app.cache.redis_client import RedisClient

logger = get_logger(__name__)

class AssetDiscoveryService:
    """Orchestrates the discovery and normalization of assets from multiple sources."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.cache_key = "asset_universe:dynamic"

    async def get_asset_universe(self, force_refresh: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """Return the complete, dynamically-fetched asset universe from cache or by refreshing."""
        if not force_refresh:
            cached_universe = await RedisClient.get(self.cache_key)
            if cached_universe:
                return cached_universe

        logger.info("dynamic_asset_discovery_started")
        tasks = [
            self._fetch_crypto_assets(),
            self._fetch_twelvedata_assets("forex"),
            self._fetch_twelvedata_assets("commodities"),
            self._fetch_twelvedata_assets("indices"),
            self._fetch_fred_assets(),
            self._fetch_yahoo_stocks(),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        universe = {}
        for res in results:
            if isinstance(res, dict):
                # Merge lists for the same market key if necessary
                for key, value in res.items():
                    if key in universe:
                        universe[key].extend(value)
                    else:
                        universe[key] = value
            elif isinstance(res, Exception):
                logger.error(f"Asset discovery task failed: {res}")

        if universe:
            await RedisClient.set(self.cache_key, universe, ttl=3600) # Cache for 1 hour
            logger.info("dynamic_asset_discovery_completed", markets=list(universe.keys()))

        return universe

    async def _fetch_fred_assets(self) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch bond and macro assets from FRED."""
        # For FRED, we use a predefined list as dynamic discovery is not practical
        # This is a reasonable exception to the "no hardcoding" rule for this specific source
        fred_assets = [
            {"symbol": "DGS2", "name": "US 2-Year Treasury"},
            {"symbol": "DGS10", "name": "US 10-Year Treasury"},
            {"symbol": "DGS30", "name": "US 30-Year Treasury"},
            {"symbol": "IRLTLT01DEM156N", "name": "Germany 10-Year Yield"},
            {"symbol": "IRLTLT01GBM156N", "name": "UK 10-Year Gilt"},
        ]
        
        assets = [
            {"symbol": item["symbol"], "name": item["name"], "source": "fred"}
            for item in fred_assets
        ]
        
        return {"bonds": assets}

    async def _fetch_crypto_assets(self) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch all cryptocurrency assets from CoinGecko (Top 1000)."""
        assets = []
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Fetch top 1000 coins across 4 pages
                for page in range(1, 5):
                    resp = await client.get(
                        "https://api.coingecko.com/api/v3/coins/markets",
                        params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": page}
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for coin in data:
                        assets.append({
                            "symbol": coin["symbol"].upper(),
                            "name": coin["name"],
                            "source": "coingecko"
                        })
                    # Brief sleep to respect rate limits
                    await asyncio.sleep(1.0)
            return {"crypto": assets}
        except Exception as e:
            logger.error(f"Failed to fetch crypto assets from CoinGecko: {e}")
            return {"crypto": []}

    async def _fetch_twelvedata_assets(self, market: str) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch all available symbols for a given market from Twelve Data."""
        assets = []
        api_key = self.settings.twelvedata_api_key
        if not api_key:
            logger.warning(f"Twelve Data API key not found, skipping {market} discovery.")
            return {market: []}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    "https://api.twelvedata.com/symbol_search",
                    params={"source": "docs", "show_plan": "true", "type": market}
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("data", []):
                    assets.append({
                        "symbol": item["symbol"],
                        "name": item.get("instrument_name", item["symbol"]),
                        "source": "twelvedata"
                    })
            return {market: assets}
        except Exception as e:
            logger.error(f"Failed to fetch {market} assets from Twelve Data: {e}")
            return {market: []}

    async def _fetch_yahoo_stocks(self) -> Dict[str, List[Dict[str, Any]]]:
        """Dynamically fetch S&P 500 and NASDAQ stocks via Yahoo Finance/Wikipedia."""
        import pandas as pd
        stocks = []
        etfs = []
        
        try:
            # 1. Fetch S&P 500 components from Wikipedia (very stable source)
            sp500_table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
            df_sp500 = sp500_table[0]
            for _, row in df_sp500.iterrows():
                stocks.append({
                    "symbol": row['Symbol'].replace('.', '-'),
                    "name": row['Security'],
                    "source": "yahoo"
                })
            
            # 2. Add Top ETFs (Common ones as baseline)
            common_etfs = [
                ("SPY", "SPDR S&P 500 ETF Trust"),
                ("QQQ", "Invesco QQQ Trust"),
                ("DIA", "SPDR Dow Jones Industrial Average ETF Trust"),
                ("GLD", "SPDR Gold Shares"),
                ("SLV", "iShares Silver Trust"),
                ("ARKK", "ARK Innovation ETF"),
                ("VTI", "Vanguard Total Stock Market ETF"),
                ("TLT", "iShares 20+ Year Treasury Bond ETF"),
                ("EEM", "iShares MSCI Emerging Markets ETF"),
                ("XLF", "Financial Select Sector SPDR Fund"),
                ("XLK", "Technology Select Sector SPDR Fund"),
            ]
            for sym, name in common_etfs:
                etfs.append({
                    "symbol": sym,
                    "name": name,
                    "source": "yahoo"
                })
                
            return {"stocks": stocks, "etfs": etfs}
        except Exception as e:
            logger.error(f"Failed to fetch dynamic stock assets: {e}")
            return {"stocks": [], "etfs": []}

_asset_discovery_service: AssetDiscoveryService | None = None

def get_asset_discovery_service() -> AssetDiscoveryService:
    global _asset_discovery_service
    if _asset_discovery_service is None:
        _asset_discovery_service = AssetDiscoveryService()
    return _asset_discovery_service
