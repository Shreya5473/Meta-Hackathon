"""Centralized asset list for GeoTrade.
Contains all mandatory assets across all markets as a fallback baseline.
"""
from typing import Any, Dict, List

ASSETS: Dict[str, List[Dict[str, Any]]] = {
    "forex": [
        # MAJORS
        {"symbol": "EURUSD", "name": "Euro / US Dollar", "type": "major"},
        {"symbol": "GBPUSD", "name": "British Pound / US Dollar", "type": "major"},
        {"symbol": "USDJPY", "name": "US Dollar / Japanese Yen", "type": "major"},
        {"symbol": "USDCHF", "name": "US Dollar / Swiss Franc", "type": "major"},
        {"symbol": "USDCAD", "name": "US Dollar / Canadian Dollar", "type": "major"},
        {"symbol": "AUDUSD", "name": "Australian Dollar / US Dollar", "type": "major"},
        {"symbol": "NZDUSD", "name": "New Zealand Dollar / US Dollar", "type": "major"},
        # MINORS
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
        # METALS
        {"symbol": "XAUUSD", "name": "Gold Spot", "type": "metal"},
        {"symbol": "XAGUSD", "name": "Silver Spot", "type": "metal"},
        {"symbol": "PLATINUM", "name": "Platinum", "type": "metal"},
        {"symbol": "PALLADIUM", "name": "Palladium", "type": "metal"},
        {"symbol": "COPPER", "name": "Copper", "type": "metal"},
        # ENERGY
        {"symbol": "WTI", "name": "WTI Crude Oil", "type": "energy"},
        {"symbol": "BRENT", "name": "Brent Crude Oil", "type": "energy"},
        {"symbol": "NATGAS", "name": "Natural Gas", "type": "energy"},
        {"symbol": "HEATINGOIL", "name": "Heating Oil", "type": "energy"},
        # AGRICULTURE
        {"symbol": "CORN", "name": "Corn", "type": "agriculture"},
        {"symbol": "WHEAT", "name": "Wheat", "type": "agriculture"},
        {"symbol": "SOYBEANS", "name": "Soybeans", "type": "agriculture"},
        {"symbol": "COFFEE", "name": "Coffee", "type": "agriculture"},
        {"symbol": "SUGAR", "name": "Sugar", "type": "agriculture"},
        {"symbol": "COTTON", "name": "Cotton", "type": "agriculture"},
    ],
    "indices": [
        # US
        {"symbol": "SPX", "name": "S&P 500", "region": "US"},
        {"symbol": "NDX", "name": "NASDAQ 100", "region": "US"},
        {"symbol": "DJI", "name": "Dow Jones Industrial Average", "region": "US"},
        {"symbol": "RUT", "name": "Russell 2000", "region": "US"},
        # EUROPE
        {"symbol": "DAX", "name": "DAX 40", "region": "Europe"},
        {"symbol": "FTSE", "name": "FTSE 100", "region": "Europe"},
        {"symbol": "CAC", "name": "CAC 40", "region": "Europe"},
        {"symbol": "STOXX50", "name": "Euro Stoxx 50", "region": "Europe"},
        # ASIA
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
        # US BIG TECH
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "MSFT", "name": "Microsoft Corporation"},
        {"symbol": "NVDA", "name": "NVIDIA Corporation"},
        {"symbol": "TSLA", "name": "Tesla, Inc."},
        {"symbol": "AMZN", "name": "Amazon.com, Inc."},
        {"symbol": "META", "name": "Meta Platforms, Inc."},
        {"symbol": "GOOGL", "name": "Alphabet Inc."},
        # FINANCE
        {"symbol": "JPM", "name": "JPMorgan Chase & Co."},
        {"symbol": "GS", "name": "Goldman Sachs Group, Inc."},
        {"symbol": "BAC", "name": "Bank of America Corp."},
        # INDUSTRIAL
        {"symbol": "BA", "name": "The Boeing Company"},
        {"symbol": "CAT", "name": "Caterpillar Inc."},
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

def get_all_assets() -> List[Dict[str, Any]]:
    """Return a flat list of all assets with their market category."""
    all_assets = []
    for market, assets in ASSETS.items():
        for asset in assets:
            asset_copy = asset.copy()
            asset_copy["market"] = market
            all_assets.append(asset_copy)
    return all_assets
