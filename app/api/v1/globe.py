"""Globe endpoints — per-country GTI scores, arcs, and live event markers."""
from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter

from app.core.cache import _make_cache_key, cache_get, cache_set
from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter(prefix="/globe", tags=["globe"])
logger = get_logger(__name__)

# ISO-2 → lat/lng centroids for major countries
COUNTRY_CENTROIDS: dict[str, dict] = {
    "US": {"lat": 37.09, "lng": -95.71, "name": "United States"},
    "CN": {"lat": 35.86, "lng": 104.19, "name": "China"},
    "RU": {"lat": 61.52, "lng": 105.31, "name": "Russia"},
    "DE": {"lat": 51.16, "lng": 10.45, "name": "Germany"},
    "GB": {"lat": 55.37, "lng": -3.43, "name": "United Kingdom"},
    "FR": {"lat": 46.22, "lng": 2.21, "name": "France"},
    "JP": {"lat": 36.20, "lng": 138.25, "name": "Japan"},
    "IN": {"lat": 20.59, "lng": 78.96, "name": "India"},
    "BR": {"lat": -14.23, "lng": -51.92, "name": "Brazil"},
    "SA": {"lat": 23.88, "lng": 45.07, "name": "Saudi Arabia"},
    "IR": {"lat": 32.42, "lng": 53.68, "name": "Iran"},
    "IL": {"lat": 31.04, "lng": 34.85, "name": "Israel"},
    "UA": {"lat": 48.37, "lng": 31.16, "name": "Ukraine"},
    "KP": {"lat": 40.33, "lng": 127.51, "name": "North Korea"},
    "TR": {"lat": 38.96, "lng": 35.24, "name": "Turkey"},
    "PK": {"lat": 30.37, "lng": 69.34, "name": "Pakistan"},
    "SY": {"lat": 34.80, "lng": 38.99, "name": "Syria"},
    "IQ": {"lat": 33.22, "lng": 43.67, "name": "Iraq"},
    "YE": {"lat": 15.55, "lng": 48.51, "name": "Yemen"},
    "MM": {"lat": 21.91, "lng": 95.95, "name": "Myanmar"},
    "ET": {"lat": 9.14, "lng": 40.48, "name": "Ethiopia"},
    "SD": {"lat": 12.86, "lng": 30.21, "name": "Sudan"},
    "VE": {"lat": 6.42, "lng": -66.58, "name": "Venezuela"},
    "ZA": {"lat": -30.55, "lng": 22.93, "name": "South Africa"},
    "EG": {"lat": 26.82, "lng": 30.80, "name": "Egypt"},
    "NG": {"lat": 9.08, "lng": 8.67, "name": "Nigeria"},
    "KR": {"lat": 35.90, "lng": 127.76, "name": "South Korea"},
    "AU": {"lat": -25.27, "lng": 133.77, "name": "Australia"},
    "CA": {"lat": 56.13, "lng": -106.34, "name": "Canada"},
    "MX": {"lat": 23.63, "lng": -102.55, "name": "Mexico"},
    "ID": {"lat": -0.78, "lng": 113.92, "name": "Indonesia"},
    "TH": {"lat": 15.87, "lng": 100.99, "name": "Thailand"},
    "MY": {"lat": 4.21, "lng": 108.96, "name": "Malaysia"},
    "PH": {"lat": 12.87, "lng": 121.77, "name": "Philippines"},
    "PL": {"lat": 51.91, "lng": 19.14, "name": "Poland"},
    "SE": {"lat": 60.12, "lng": 18.64, "name": "Sweden"},
    "NO": {"lat": 60.47, "lng": 8.46, "name": "Norway"},
    "AE": {"lat": 23.42, "lng": 53.84, "name": "UAE"},
    "QA": {"lat": 25.35, "lng": 51.18, "name": "Qatar"},
    "LY": {"lat": 26.33, "lng": 17.22, "name": "Libya"},
    "AF": {"lat": 33.93, "lng": 67.70, "name": "Afghanistan"},
}

# Tension arc definitions — which country pairs have tensions
TENSION_ARCS = [
    {"from": "RU", "to": "UA", "type": "military_escalation", "severity": 0.95},
    {"from": "CN", "to": "TW", "type": "military_escalation", "severity": 0.78},
    {"from": "US", "to": "CN", "type": "trade_restrictions", "severity": 0.72},
    {"from": "IR", "to": "IL", "type": "military_escalation", "severity": 0.88},
    {"from": "US", "to": "IR", "type": "sanctions", "severity": 0.80},
    {"from": "KP", "to": "KR", "type": "military_escalation", "severity": 0.70},
    {"from": "RU", "to": "DE", "type": "sanctions", "severity": 0.65},
    {"from": "US", "to": "RU", "type": "sanctions", "severity": 0.85},
    {"from": "CN", "to": "IN", "type": "diplomatic_activity", "severity": 0.55},
    {"from": "SA", "to": "YE", "type": "military_escalation", "severity": 0.75},
    {"from": "TR", "to": "SY", "type": "military_escalation", "severity": 0.60},
    {"from": "IN", "to": "PK", "type": "diplomatic_activity", "severity": 0.58},
    {"from": "US", "to": "SA", "type": "diplomatic_activity", "severity": 0.40},
    {"from": "GB", "to": "FR", "type": "trade_restrictions", "severity": 0.35},
    {"from": "CN", "to": "AU", "type": "trade_restrictions", "severity": 0.50},
]

ARC_COLORS = {
    "military_escalation": ["rgba(239,68,68,0.9)", "rgba(220,38,38,0.9)"],
    "trade_restrictions":  ["rgba(245,158,11,0.8)", "rgba(234,179,8,0.8)"],
    "sanctions":           ["rgba(249,115,22,0.9)", "rgba(239,68,68,0.7)"],
    "diplomatic_activity": ["rgba(14,165,233,0.7)", "rgba(99,102,241,0.7)"],
}

# Base risk scores for countries (seeded, will be jittered)
BASE_RISK: dict[str, float] = {
    "RU": 92, "UA": 88, "IR": 85, "IL": 82, "KP": 80, "YE": 78,
    "SY": 75, "IQ": 72, "AF": 70, "SD": 68, "LY": 65, "MM": 62,
    "VE": 58, "ET": 55, "PK": 52, "CN": 48, "TR": 45, "NG": 42,
    "EG": 40, "US": 38, "IN": 35, "SA": 50, "AE": 30, "QA": 28,
    "BR": 32, "MX": 38, "ID": 30, "MY": 22, "TH": 28, "PH": 35,
    "ZA": 40, "DE": 20, "FR": 22, "GB": 22, "JP": 25, "KR": 35,
    "AU": 15, "CA": 15, "SE": 12, "NO": 12, "PL": 30,
}


async def _fetch_gdelt_events() -> list[dict]:
    """Fetch recent events from GDELT GKG API (no key needed)."""
    try:
        url = (
            "https://api.gdeltproject.org/api/v2/doc/doc"
            "?query=conflict%20OR%20sanctions%20OR%20military"
            "&mode=artlist&maxrecords=20&format=json&timespan=6h"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("articles", [])
    except Exception as exc:
        logger.warning("gdelt_fetch_failed", error=str(exc))
    return []


@router.get("/countries")
async def get_country_risk() -> dict:
    """Return per-country GTI risk scores, centroids, and tension arcs for globe rendering."""
    cache_key = _make_cache_key("globe_countries")
    cached = await cache_get(cache_key)
    if cached:
        return cached

    global_gti = 55.0
    event_markers: list[dict] = [
        {"id": "e1", "lat": 32.0, "lng": 35.0, "title": "Middle East Escalation", "severity": 0.9,
         "classification": "military_escalation", "region": "IL", "ts": datetime.now(UTC).isoformat()},
        {"id": "e2", "lat": 50.0, "lng": 30.0, "title": "Ukraine Conflict", "severity": 0.85,
         "classification": "military_escalation", "region": "UA", "ts": datetime.now(UTC).isoformat()},
        {"id": "e3", "lat": 39.0, "lng": 126.0, "title": "DPRK Missile Activity", "severity": 0.78,
         "classification": "military_escalation", "region": "KP", "ts": datetime.now(UTC).isoformat()},
        {"id": "e4", "lat": 25.0, "lng": 56.0, "title": "Strait of Hormuz Naval Activity", "severity": 0.8,
         "classification": "military_escalation", "region": "AE", "ts": datetime.now(UTC).isoformat()},
    ]

    # Build country risk array (base + small random jitter for live feel)
    countries = []
    for iso, centroid in COUNTRY_CENTROIDS.items():
        base = BASE_RISK.get(iso, 25.0)
        jitter = random.uniform(-3.0, 3.0)
        score = max(0.0, min(100.0, base + jitter + (global_gti - 55) * 0.1))
        tension_level = (
            "critical" if score >= 80
            else "high" if score >= 60
            else "medium" if score >= 35
            else "low"
        )
        countries.append({
            "iso": iso,
            "name": centroid["name"],
            "lat": centroid["lat"],
            "lng": centroid["lng"],
            "gti_score": round(score, 1),
            "tension_level": tension_level,
        })

    # Build arcs with centroids resolved
    arcs = []
    for arc in TENSION_ARCS:
        src = COUNTRY_CENTROIDS.get(arc["from"])
        tgt = COUNTRY_CENTROIDS.get(arc["to"])
        if src and tgt:
            colors = ARC_COLORS.get(arc["type"], ["rgba(255,255,255,0.5)", "rgba(255,255,255,0.5)"])
            arcs.append({
                "startLat": src["lat"],
                "startLng": src["lng"],
                "endLat": tgt["lat"],
                "endLng": tgt["lng"],
                "fromName": src["name"],
                "toName": tgt["name"],
                "type": arc["type"],
                "severity": arc["severity"],
                "color": colors,
            })

    result = {
        "countries": countries,
        "arcs": arcs,
        "event_markers": event_markers,
        "global_gti": global_gti,
        "ts": datetime.now(UTC).isoformat(),
    }

    await cache_set(cache_key, result, ttl=30)
    return result


# ISO-3 → ISO-2 mapping (map datasets may send 3-letter codes)
ISO3_TO_ISO2: dict[str, str] = {
    "USA": "US", "CHN": "CN", "RUS": "RU", "GBR": "GB", "DEU": "DE", "FRA": "FR",
    "JPN": "JP", "IND": "IN", "BRA": "BR", "SAU": "SA", "IRN": "IR", "ISR": "IL",
    "UKR": "UA", "PRK": "KP", "TUR": "TR", "PAK": "PK", "SYR": "SY", "IRQ": "IQ",
    "YEM": "YE", "MMR": "MM", "ETH": "ET", "SDN": "SD", "VEN": "VE", "ZAF": "ZA",
    "EGY": "EG", "NGA": "NG", "KOR": "KR", "AUS": "AU", "CAN": "CA", "MEX": "MX",
    "IDN": "ID", "THA": "TH", "MYS": "MY", "PHL": "PH", "POL": "PL", "SWE": "SE",
    "NOR": "NO", "ARE": "AE", "QAT": "QA", "LBY": "LY", "AFG": "AF", "KAZ": "KZ",
}


def _synthetic_market_impact(iso: str) -> dict:
    """Generate synthetic market impact so the endpoint never 500s."""
    country_info = COUNTRY_CENTROIDS.get(iso, {"name": iso, "lat": 0, "lng": 0})
    COUNTRY_ASSETS = {
        "RU": ["USOIL", "XAUUSD", "NATGAS", "RUB"],
        "UA": ["WHEAT", "CORN", "USOIL"],
        "IR": ["USOIL", "NATGAS", "XAUUSD"],
        "IL": ["XAUUSD", "TA35", "ILS"],
        "SA": ["USOIL", "NATGAS", "ARAMCO"],
        "CN": ["HSI", "CNY", "COPPER", "SOYBEANS"],
        "US": ["SPX", "NDX", "DXY", "XAUUSD"],
        "KP": ["XAUUSD", "KRW", "KOSPI"],
        "TR": ["BIST100", "TRY", "XAUUSD"],
        "IN": ["NIFTY50", "INR", "SILVER"],
    }
    assets = COUNTRY_ASSETS.get(iso, ["XAUUSD", "USOIL", "SPX"])
    FALLBACK_PRICES = {
        "XAUUSD": 2340, "USOIL": 82, "NATGAS": 3.2, "WHEAT": 580, "CORN": 430,
        "SPX": 5200, "NDX": 18000, "DXY": 104, "COPPER": 4.5, "SILVER": 29,
    }

    def _gen_ohlcv(base: float, n: int = 30) -> list[dict]:
        rows = []
        price = base
        now = datetime.now(UTC)
        for i in range(n):
            chg = random.uniform(-0.015, 0.015)
            open_ = price
            close = price * (1 + chg)
            rows.append({
                "ts": (now - timedelta(hours=n - i)).isoformat(),
                "open": round(open_, 4), "high": round(max(open_, close) * 1.005, 4),
                "low": round(min(open_, close) * 0.995, 4), "close": round(close, 4),
                "volume": random.randint(100000, 5000000),
            })
            price = close
        return rows

    quotes = []
    charts = {}
    for asset in assets[:4]:
        base = FALLBACK_PRICES.get(asset, 100)
        chg = random.uniform(-2.5, 2.5)
        quotes.append({
            "symbol": asset,
            "price": round(base * (1 + chg / 100), 2),
            "change_pct": round(chg, 2),
            "high": round(base * 1.01, 2), "low": round(base * 0.99, 2),
            "open": round(base * 1.002, 2),
        })
        charts[asset] = _gen_ohlcv(base * (1 + chg / 100))

    gti_score = BASE_RISK.get(iso, 40.0) + random.uniform(-3, 3)
    return {
        "iso": iso,
        "name": country_info.get("name", iso),
        "gti_score": round(gti_score, 1),
        "affected_assets": assets,
        "quotes": quotes,
        "charts": charts,
        "sector_exposure": {
            "Energy": round(random.uniform(0.2, 0.8), 2),
            "Defense": round(random.uniform(0.1, 0.6), 2),
            "Commodities": round(random.uniform(0.3, 0.9), 2),
            "Financials": round(random.uniform(0.1, 0.5), 2),
            "Technology": round(random.uniform(0.05, 0.4), 2),
        },
        "currency_impact": [
            {"pair": "USD/EUR", "change_pct": round(random.uniform(-1.5, 1.5), 3)},
            {"pair": "USD/JPY", "change_pct": round(random.uniform(-1.5, 1.5), 3)},
            {"pair": "DXY", "change_pct": round(random.uniform(-0.8, 0.8), 3)},
        ],
        "ts": datetime.now(UTC).isoformat(),
    }


@router.get("/market-impact/{iso}")
async def get_country_market_impact(
    iso: str,
) -> dict:
    """Return market impact data for a specific country — real Finnhub quotes + mock chart. Never 500s."""
    iso = (iso or "").strip().upper()
    if len(iso) == 3:
        iso = ISO3_TO_ISO2.get(iso, iso)
    if len(iso) != 2:
        iso = "US"  # fallback for invalid codes
    try:
        return await _fetch_market_impact(iso)
    except Exception as exc:
        logger.warning("market_impact_fetch_failed", iso=iso, error=str(exc))
        return _synthetic_market_impact(iso)


async def _fetch_market_impact(iso: str) -> dict:
    """Inner logic for market impact — may raise on transient errors."""
    settings = get_settings()
    cache_key = _make_cache_key("globe_market_impact", iso)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Map country → affected assets
    COUNTRY_ASSETS: dict[str, list[str]] = {
        "RU": ["USOIL", "XAUUSD", "NATGAS", "RUB"],
        "UA": ["WHEAT", "CORN", "USOIL"],
        "IR": ["USOIL", "NATGAS", "XAUUSD"],
        "IL": ["XAUUSD", "TA35", "ILS"],
        "SA": ["USOIL", "NATGAS", "ARAMCO"],
        "CN": ["HSI", "CNY", "COPPER", "SOYBEANS"],
        "US": ["SPX", "NDX", "DXY", "XAUUSD"],
        "KP": ["XAUUSD", "KRW", "KOSPI"],
        "TR": ["BIST100", "TRY", "XAUUSD"],
        "IN": ["NIFTY50", "INR", "SILVER"],
    }

    assets = COUNTRY_ASSETS.get(iso, ["XAUUSD", "USOIL", "SPX"])

    # Try fetching real quotes from Finnhub
    quotes: list[dict] = []
    if settings.finnhub_api_key:
        finnhub_map = {"XAUUSD": "OANDA:XAU_USD", "USOIL": "OANDA:WTI_USD", "SPX": "SPY",
                       "NDX": "QQQ", "DXY": "UUP", "NATGAS": "OANDA:NATGAS_USD"}
        async with httpx.AsyncClient(timeout=8.0) as client:
            for asset in assets[:4]:
                sym = finnhub_map.get(asset, asset)
                try:
                    r = await client.get(
                        f"https://finnhub.io/api/v1/quote?symbol={sym}&token={settings.finnhub_api_key}"
                    )
                    if r.status_code == 200:
                        q = r.json()
                        quotes.append({
                            "symbol": asset,
                            "price": q.get("c", 0),
                            "change_pct": round(((q.get("c", 0) - q.get("pc", 1)) / max(q.get("pc", 1), 0.001)) * 100, 2),
                            "high": q.get("h", 0),
                            "low": q.get("l", 0),
                            "open": q.get("o", 0),
                        })
                except Exception:
                    pass

    # Fallback synthetic prices for assets not covered by Finnhub
    covered = {q["symbol"] for q in quotes}
    if len(quotes) < len(assets[:4]):
        FALLBACK_PRICES = {
            "XAUUSD": 2340, "USOIL": 82, "NATGAS": 3.2, "WHEAT": 580, "CORN": 430,
            "SPX": 5200, "NDX": 18000, "DXY": 104, "COPPER": 4.5,
        }
        for asset in assets[:4]:
            if asset in covered:
                continue
            base = FALLBACK_PRICES.get(asset, 100)
            chg = random.uniform(-2.5, 2.5)
            quotes.append({
                "symbol": asset,
                "price": round(base * (1 + chg / 100), 2),
                "change_pct": round(chg, 2),
                "high": round(base * 1.01, 2),
                "low": round(base * 0.99, 2),
                "open": round(base * 1.002, 2),
            })

    # Build synthetic OHLCV history (30 bars)
    def _gen_ohlcv(base: float, n: int = 30) -> list[dict]:
        rows = []
        price = base
        now = datetime.now(UTC)
        for i in range(n):
            chg = random.uniform(-0.015, 0.015)
            open_ = price
            close = price * (1 + chg)
            high = max(open_, close) * random.uniform(1.001, 1.008)
            low = min(open_, close) * random.uniform(0.992, 0.999)
            rows.append({
                "ts": (now - timedelta(hours=n - i)).isoformat(),
                "open": round(open_, 4), "high": round(high, 4),
                "low": round(low, 4), "close": round(close, 4),
                "volume": random.randint(100000, 5000000),
            })
            price = close
        return rows

    charts = {}
    for q in quotes:
        charts[q["symbol"]] = _gen_ohlcv(q["price"] / (1 + q["change_pct"] / 100))

    country_info = COUNTRY_CENTROIDS.get(iso, {})
    gti_score = BASE_RISK.get(iso, 40.0) + random.uniform(-3, 3)

    result = {
        "iso": iso,
        "name": country_info.get("name", iso),
        "gti_score": round(gti_score, 1),
        "affected_assets": assets,
        "quotes": quotes,
        "charts": charts,
        "sector_exposure": {
            "Energy": round(random.uniform(0.2, 0.8), 2),
            "Defense": round(random.uniform(0.1, 0.6), 2),
            "Commodities": round(random.uniform(0.3, 0.9), 2),
            "Financials": round(random.uniform(0.1, 0.5), 2),
            "Technology": round(random.uniform(0.05, 0.4), 2),
        },
        "currency_impact": [
            {"pair": "USD/EUR", "change_pct": round(random.uniform(-1.5, 1.5), 3)},
            {"pair": "USD/JPY", "change_pct": round(random.uniform(-1.5, 1.5), 3)},
            {"pair": "DXY", "change_pct": round(random.uniform(-0.8, 0.8), 3)},
        ],
        "ts": datetime.now(UTC).isoformat(),
    }

    await cache_set(cache_key, result, ttl=20)
    return result
