"""Centralized asset universe for GeoTrade.

Groups all supported assets by market class for consistent polling and display.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ASSET_UNIVERSE: Dict[str, List[Dict[str, Any]]] = {
    "forex": [
        # Majors
        {"symbol": "EURUSD", "name": "Euro / US Dollar", "type": "major"},
        {"symbol": "GBPUSD", "name": "British Pound / US Dollar", "type": "major"},
        {"symbol": "USDJPY", "name": "US Dollar / Japanese Yen", "type": "major"},
        {"symbol": "USDCHF", "name": "US Dollar / Swiss Franc", "type": "major"},
        {"symbol": "USDCAD", "name": "US Dollar / Canadian Dollar", "type": "major"},
        {"symbol": "AUDUSD", "name": "Australian Dollar / US Dollar", "type": "major"},
        {"symbol": "NZDUSD", "name": "New Zealand Dollar / US Dollar", "type": "major"},
        # Minors
        {"symbol": "EURGBP", "name": "Euro / British Pound", "type": "minor"},
        {"symbol": "EURJPY", "name": "Euro / Japanese Yen", "type": "minor"},
        {"symbol": "EURAUD", "name": "Euro / Australian Dollar", "type": "minor"},
        {"symbol": "EURCHF", "name": "Euro / Swiss Franc", "type": "minor"},
        {"symbol": "EURCAD", "name": "Euro / Canadian Dollar", "type": "minor"},
        {"symbol": "GBPJPY", "name": "British Pound / Japanese Yen", "type": "minor"},
        {"symbol": "GBPCHF", "name": "British Pound / Swiss Franc", "type": "minor"},
        {"symbol": "GBPAUD", "name": "British Pound / Australian Dollar", "type": "minor"},
        {"symbol": "GBPCAD", "name": "British Pound / Canadian Dollar", "type": "minor"},
        {"symbol": "AUDJPY", "name": "Australian Dollar / Japanese Yen", "type": "minor"},
        {"symbol": "AUDNZD", "name": "Australian Dollar / New Zealand Dollar", "type": "minor"},
        {"symbol": "AUDCAD", "name": "Australian Dollar / Canadian Dollar", "type": "minor"},
        {"symbol": "NZDJPY", "name": "New Zealand Dollar / Japanese Yen", "type": "minor"},
        {"symbol": "NZDCAD", "name": "New Zealand Dollar / Canadian Dollar", "type": "minor"},
        {"symbol": "CADJPY", "name": "Canadian Dollar / Japanese Yen", "type": "minor"},
        {"symbol": "CHFJPY", "name": "Swiss Franc / Japanese Yen", "type": "minor"},
    ],
    "commodities": [
        # Metals
        {"symbol": "XAUUSD", "name": "Gold Spot / US Dollar", "type": "metal"},
        {"symbol": "XAGUSD", "name": "Silver Spot / US Dollar", "type": "metal"},
        {"symbol": "PLATINUM", "name": "Platinum Spot", "type": "metal"},
        {"symbol": "PALLADIUM", "name": "Palladium Spot", "type": "metal"},
        {"symbol": "COPPER", "name": "Copper Spot", "type": "metal"},
        # Energy
        {"symbol": "WTI", "name": "WTI Crude Oil", "type": "energy"},
        {"symbol": "BRENT", "name": "Brent Crude Oil", "type": "energy"},
        {"symbol": "NATGAS", "name": "Natural Gas", "type": "energy"},
        {"symbol": "HEATINGOIL", "name": "Heating Oil", "type": "energy"},
        # Agriculture
        {"symbol": "CORN", "name": "Corn", "type": "agri"},
        {"symbol": "WHEAT", "name": "Wheat", "type": "agri"},
        {"symbol": "SOYBEANS", "name": "Soybeans", "type": "agri"},
        {"symbol": "COFFEE", "name": "Coffee", "type": "agri"},
        {"symbol": "SUGAR", "name": "Sugar", "type": "agri"},
        {"symbol": "COTTON", "name": "Cotton", "type": "agri"},
    ],
    "indices": [
        # US
        {"symbol": "SPX", "name": "S&P 500", "region": "US"},
        {"symbol": "NDX", "name": "NASDAQ 100", "region": "US"},
        {"symbol": "DJI", "name": "Dow Jones Industrial Average", "region": "US"},
        {"symbol": "RUT", "name": "Russell 2000", "region": "US"},
        # Europe
        {"symbol": "DAX", "name": "DAX 40", "region": "Europe"},
        {"symbol": "FTSE", "name": "FTSE 100", "region": "Europe"},
        {"symbol": "CAC", "name": "CAC 40", "region": "Europe"},
        {"symbol": "STOXX50", "name": "Euro Stoxx 50", "region": "Europe"},
        # Asia
        {"symbol": "NKY", "name": "Nikkei 225", "region": "Asia"},
        {"symbol": "HSI", "name": "Hang Seng Index", "region": "Asia"},
        {"symbol": "SSEC", "name": "Shanghai Composite", "region": "Asia"},
        {"symbol": "SENSEX", "name": "BSE Sensex", "region": "Asia"},
        {"symbol": "NIFTY", "name": "Nifty 50", "region": "Asia"},
    ],
    "crypto": [
        {"symbol": "BTC", "name": "Bitcoin"},
        {"symbol": "ETH", "name": "Ethereum"},
        {"symbol": "BNB", "name": "Binance Coin"},
        {"symbol": "SOL", "name": "Solana"},
        {"symbol": "XRP", "name": "XRP"},
        {"symbol": "ADA", "name": "Cardano"},
        {"symbol": "DOGE", "name": "Dogecoin"},
        {"symbol": "AVAX", "name": "Avalanche"},
        {"symbol": "MATIC", "name": "Polygon"},
        {"symbol": "DOT", "name": "Polkadot"},
        {"symbol": "LTC", "name": "Litecoin"},
        {"symbol": "LINK", "name": "Chainlink"},
    ],
    "stocks": [
        # US Big Tech
        {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Tech"},
        {"symbol": "MSFT", "name": "Microsoft Corporation", "sector": "Tech"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation", "sector": "Tech"},
        {"symbol": "TSLA", "name": "Tesla, Inc.", "sector": "Auto/Tech"},
        {"symbol": "AMZN", "name": "Amazon.com, Inc.", "sector": "Consumer/Tech"},
        {"symbol": "META", "name": "Meta Platforms, Inc.", "sector": "Tech"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Tech"},
        # Finance
        {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "sector": "Finance"},
        {"symbol": "GS", "name": "Goldman Sachs Group, Inc.", "sector": "Finance"},
        {"symbol": "BAC", "name": "Bank of America Corp.", "sector": "Finance"},
        # Industrial
        {"symbol": "BA", "name": "The Boeing Company", "sector": "Industrial"},
        {"symbol": "CAT", "name": "Caterpillar Inc.", "sector": "Industrial"},
    ],
    "etfs": [
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust"},
        {"symbol": "QQQ", "name": "Invesco QQQ Trust"},
        {"symbol": "DIA", "name": "SPDR Dow Jones Industrial Average ETF Trust"},
        {"symbol": "GLD", "name": "SPDR Gold Shares"},
        {"symbol": "SLV", "name": "iShares Silver Trust"},
        {"symbol": "ARKK", "name": "ARK Innovation ETF"},
        {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF"},
    ],
    "bonds": [
        {"symbol": "US02Y", "name": "US 2-Year Treasury Yield"},
        {"symbol": "US05Y", "name": "US 5-Year Treasury Yield"},
        {"symbol": "US10Y", "name": "US 10-Year Treasury Yield"},
        {"symbol": "US30Y", "name": "US 30-Year Treasury Yield"},
        {"symbol": "DE10Y", "name": "Germany 10-Year Bond Yield"},
        {"symbol": "GB10Y", "name": "UK Gilt 10-Year Yield"},
        {"symbol": "IN10Y", "name": "India 10-Year Bond Yield"},
    ]
}

def get_all_symbols() -> List[str]:
    """Return a flat list of all symbols in the universe."""
    symbols = []
    for market in ASSET_UNIVERSE.values():
        for asset in market:
            symbols.append(asset["symbol"])
    return list(set(symbols))

def get_assets_by_market(market: str) -> List[Dict[str, Any]]:
    """Return all assets for a given market."""
    return ASSET_UNIVERSE.get(market, [])


# ── Typed asset definition (used by signals_v2) ───────────────────────────────

@dataclass
class AssetDefinition:
    symbol: str
    name: str
    asset_class: str        # forex / commodity / equity / bond / crypto / etf
    subtype: str = ""       # e.g. major, metal, energy, agri
    sector: str = ""
    region: str = ""
    geo_sensitivity: float = 0.5
    description: str = ""


@dataclass
class AssetUniverse:
    assets: List[AssetDefinition] = field(default_factory=list)

    def get(self, symbol: str) -> Optional[AssetDefinition]:
        for a in self.assets:
            if a.symbol == symbol:
                return a
        return None

    def all_symbols(self) -> List[str]:
        return [a.symbol for a in self.assets]

    def by_class(self, asset_class: str) -> List[AssetDefinition]:
        return [a for a in self.assets if a.asset_class == asset_class]


def get_asset_universe() -> AssetUniverse:
    """Build and return a typed AssetUniverse from ASSET_UNIVERSE dict."""
    assets: List[AssetDefinition] = []
    class_map = {
        "forex": "forex", "commodities": "commodity", "indices": "equity",
        "crypto": "crypto", "stocks": "equity", "etfs": "etf", "bonds": "bond",
    }
    for market_key, items in ASSET_UNIVERSE.items():
        asset_class = class_map.get(market_key, market_key)
        for item in items:
            assets.append(AssetDefinition(
                symbol=item["symbol"],
                name=item["name"],
                asset_class=asset_class,
                subtype=item.get("type", ""),
                sector=item.get("sector", ""),
                region=item.get("region", ""),
            ))
    return AssetUniverse(assets=assets)
