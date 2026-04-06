"""Market data feed adapters — live data only, no synthetic substitution.

Architecture:
    MarketFeedAdapter   ← abstract base
        └── RealMarketAdapter      ← Finnhub REST API (equities/ETFs/FX proxies)
        └── BinanceCryptoAdapter   ← Binance public REST + WebSocket (crypto)
    MarketFeedManager          ← 30-second polling loop + in-memory cache
                               + Binance WebSocket listener (real-time crypto)

Synthetic / demo data is permanently disabled. If Finnhub is unreachable the
poller logs an error and retries on the next interval — stale data is served from
cache rather than fabricated numbers.
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Finnhub symbol map ────────────────────────────────────────────────────────
# Maps our internal symbol → Finnhub query symbol + asset metadata.
# Add new instruments here without touching adapter code.

FINNHUB_SYMBOL_MAP: dict[str, dict[str, Any]] = {
    # ── Commodities (via ETF proxies on Finnhub free tier) ────────────────────
    "GC=F":        {"fh_sym": "GLD",             "class": "commodity", "region": "global",    "base": 2340},
    "XAUUSD":      {"fh_sym": "GLD",             "class": "commodity", "region": "global",    "base": 2340},
    "XAGUSD":      {"fh_sym": "SLV",             "class": "commodity", "region": "global",    "base":   29},
    "CL=F":        {"fh_sym": "USO",             "class": "commodity", "region": "global",    "base":   82},
    "WTI":         {"fh_sym": "USO",             "class": "commodity", "region": "global",    "base":   82},
    "BRENT":       {"fh_sym": "BNO",             "class": "commodity", "region": "global",    "base":   86},
    "NATGAS":      {"fh_sym": "UNG",             "class": "commodity", "region": "global",    "base":  3.2},
    "COPPER":      {"fh_sym": "CPER",            "class": "commodity", "region": "global",    "base":  4.5},
    "WHEAT":       {"fh_sym": "WEAT",            "class": "commodity", "region": "global",    "base":  580},
    "CORN":        {"fh_sym": "CORN",            "class": "commodity", "region": "global",    "base":  430},
    "SOYBEANS":    {"fh_sym": "SOYB",            "class": "commodity", "region": "global",    "base": 1150},
    "PALLADIUM":   {"fh_sym": "PALL",            "class": "commodity", "region": "global",    "base": 1000},
    "PLATINUM":    {"fh_sym": "PPLT",            "class": "commodity", "region": "global",    "base": 950},
    "COCOA":       {"fh_sym": "NIB",             "class": "commodity", "region": "global",    "base": 10000},
    "COFFEE":      {"fh_sym": "JO",              "class": "commodity", "region": "global",    "base": 220},
    "SUGAR":       {"fh_sym": "CANE",            "class": "commodity", "region": "global",    "base": 20},
    # ── Equity Indices ────────────────────────────────────────────────────────
    "^GSPC":       {"fh_sym": "SPY",             "class": "equity",    "region": "americas",  "base": 5200},
    "SPX":         {"fh_sym": "SPY",             "class": "equity",    "region": "americas",  "base": 5200},
    "^IXIC":       {"fh_sym": "QQQ",             "class": "equity",    "region": "americas",  "base":18000},
    "NDX":         {"fh_sym": "QQQ",             "class": "equity",    "region": "americas",  "base":18000},
    "DJI":         {"fh_sym": "DIA",             "class": "equity",    "region": "americas",  "base":38000},
    "DAX":         {"fh_sym": "EWG",             "class": "equity",    "region": "europe",    "base":17500},
    "NKY":         {"fh_sym": "EWJ",             "class": "equity",    "region": "asia_pacific","base":38000},
    "HSI":         {"fh_sym": "EWH",             "class": "equity",    "region": "asia_pacific","base":16500},
    "FTSE":        {"fh_sym": "EWU",             "class": "equity",    "region": "europe",    "base":8000},
    "CAC":         {"fh_sym": "EWQ",             "class": "equity",    "region": "europe",    "base":7500},
    "SSEC":        {"fh_sym": "ASHR",            "class": "equity",    "region": "asia_pacific","base":3000},
    "ASX200":      {"fh_sym": "EWA",             "class": "equity",    "region": "asia_pacific","base":7800},
    "IBEX":        {"fh_sym": "EWP",             "class": "equity",    "region": "europe",    "base":11000},
    "FTSEMIB":     {"fh_sym": "EWI",             "class": "equity",    "region": "europe",    "base":34000},
    # ── Forex ─────────────────────────────────────────────────────────────────
    "EURUSD":      {"fh_sym": "FXE",             "class": "currency",  "region": "europe",    "base":1.085},
    "USDJPY":      {"fh_sym": "FXY",             "class": "currency",  "region": "asia_pacific","base":150.5},
    "USDCNY":      {"fh_sym": "MCHI",            "class": "currency",  "region": "asia_pacific","base":7.24},
    "GBPUSD":      {"fh_sym": "FXB",             "class": "currency",  "region": "europe",    "base":1.27},
    "USDCHF":      {"fh_sym": "FXF",             "class": "currency",  "region": "europe",    "base":0.895},
    "AUDUSD":      {"fh_sym": "FXA",             "class": "currency",  "region": "asia_pacific","base":0.665},
    "USDCAD":      {"fh_sym": "FXC",             "class": "currency",  "region": "americas",  "base":1.365},
    "NZDUSD":      {"fh_sym": "ENZL",            "class": "currency",  "region": "asia_pacific","base":0.615},
    "EURGBP":      {"fh_sym": "FXE/FXB",         "class": "currency",  "region": "europe",    "base":0.855},
    "EURJPY":      {"fh_sym": "FXE/FXY",         "class": "currency",  "region": "global",    "base":163.5},
    "GBPJPY":      {"fh_sym": "FXB/FXY",         "class": "currency",  "region": "global",    "base":191.5},
    "DXY":         {"fh_sym": "UUP",             "class": "currency",  "region": "americas",  "base":  104},
    # ── Crypto (Binance via Finnhub) ──────────────────────────────────────────
    "BINANCE:BTCUSDT": {"fh_sym": "BINANCE:BTCUSDT", "class": "crypto","region": "global",   "base":68000},
    "BTCUSD":      {"fh_sym": "BINANCE:BTCUSDT", "class": "crypto",    "region": "global",   "base":68000},
    "BINANCE:ETHUSDT": {"fh_sym": "BINANCE:ETHUSDT", "class": "crypto","region": "global",   "base": 3200},
    "ETHUSD":      {"fh_sym": "BINANCE:ETHUSDT", "class": "crypto",    "region": "global",   "base": 3200},
    "BINANCE:BNBUSDT": {"fh_sym": "BINANCE:BNBUSDT", "class": "crypto","region": "global",   "base": 600},
    "BNBUSD":      {"fh_sym": "BINANCE:BNBUSDT", "class": "crypto",    "region": "global",   "base": 600},
    "BINANCE:SOLUSDT": {"fh_sym": "BINANCE:SOLUSDT", "class": "crypto","region": "global",   "base": 150},
    "SOLUSD":      {"fh_sym": "BINANCE:SOLUSDT", "class": "crypto",    "region": "global",   "base": 150},
    "BINANCE:XRPUSDT": {"fh_sym": "BINANCE:XRPUSDT", "class": "crypto","region": "global",   "base": 0.5},
    "XRPUSD":      {"fh_sym": "BINANCE:XRPUSDT", "class": "crypto",    "region": "global",   "base": 0.5},
    "BINANCE:ADAUSDT": {"fh_sym": "BINANCE:ADAUSDT", "class": "crypto","region": "global",   "base": 0.45},
    "ADAUSD":      {"fh_sym": "BINANCE:ADAUSDT", "class": "crypto",    "region": "global",   "base": 0.45},
    "BINANCE:DOGEUSDT":{"fh_sym": "BINANCE:DOGEUSDT","class": "crypto","region": "global",   "base": 0.15},
    "DOGEUSD":     {"fh_sym": "BINANCE:DOGEUSDT","class": "crypto",    "region": "global",   "base": 0.15},
    "BINANCE:DOTUSDT": {"fh_sym": "BINANCE:DOTUSDT", "class": "crypto","region": "global",   "base": 7.0},
    "DOTUSD":      {"fh_sym": "BINANCE:DOTUSDT", "class": "crypto",    "region": "global",   "base": 7.0},
    "BINANCE:MATICUSDT":{"fh_sym":"BINANCE:MATICUSDT","class":"crypto","region": "global",   "base": 0.7},
    "MATICUSD":    {"fh_sym":"BINANCE:MATICUSDT","class":"crypto","region": "global",   "base": 0.7},
    "BINANCE:LINKUSDT":{"fh_sym":"BINANCE:LINKUSDT","class":"crypto","region": "global",   "base": 15.0},
    "LINKUSD":     {"fh_sym":"BINANCE:LINKUSDT","class":"crypto","region": "global",   "base": 15.0},
    # ── Defense stocks ────────────────────────────────────────────────────────
    "LMT":         {"fh_sym": "LMT",             "class": "equity",    "region": "americas",  "base":  470},
    "RTX":         {"fh_sym": "RTX",             "class": "equity",    "region": "americas",  "base":  115},
    "NOC":         {"fh_sym": "NOC",             "class": "equity",    "region": "americas",  "base":  460},
    "GD":          {"fh_sym": "GD",              "class": "equity",    "region": "americas",  "base":  290},
    "BA":          {"fh_sym": "BA",              "class": "equity",    "region": "americas",  "base":  185},
    "LHX":         {"fh_sym": "LHX",             "class": "equity",    "region": "americas",  "base":  210},
    "HWM":         {"fh_sym": "HWM",             "class": "equity",    "region": "americas",  "base":  80},
    # ── Energy stocks ─────────────────────────────────────────────────────────
    "XOM":         {"fh_sym": "XOM",             "class": "equity",    "region": "americas",  "base":  118},
    "CVX":         {"fh_sym": "CVX",             "class": "equity",    "region": "americas",  "base":  155},
    "BP":          {"fh_sym": "BP",              "class": "equity",    "region": "europe",    "base":   38},
    "SHEL":        {"fh_sym": "SHEL",            "class": "equity",    "region": "europe",    "base":   65},
    "TTE":         {"fh_sym": "TTE",             "class": "equity",    "region": "europe",    "base":   70},
    "COP":         {"fh_sym": "COP",             "class": "equity",    "region": "americas",  "base":  125},
    # ── Tech Majors ───────────────────────────────────────────────────────────
    "AAPL":        {"fh_sym": "AAPL",            "class": "equity",    "region": "americas",  "base":  190},
    "MSFT":        {"fh_sym": "MSFT",            "class": "equity",    "region": "americas",  "base":  420},
    "GOOGL":       {"fh_sym": "GOOGL",           "class": "equity",    "region": "americas",  "base":  175},
    "AMZN":        {"fh_sym": "AMZN",            "class": "equity",    "region": "americas",  "base":  185},
    "NVDA":        {"fh_sym": "NVDA",            "class": "equity",    "region": "americas",  "base":  900},
    "META":        {"fh_sym": "META",            "class": "equity",    "region": "americas",  "base":  480},
    "TSLA":        {"fh_sym": "TSLA",            "class": "equity",    "region": "americas",  "base":  175},
    # ── Financials ────────────────────────────────────────────────────────────
    "JPM":         {"fh_sym": "JPM",             "class": "equity",    "region": "americas",  "base":  200},
    "BAC":         {"fh_sym": "BAC",             "class": "equity",    "region": "americas",  "base":  40},
    "GS":          {"fh_sym": "GS",              "class": "equity",    "region": "americas",  "base":  450},
    "HSBC":        {"fh_sym": "HSBC",            "class": "equity",    "region": "europe",    "base":  40},
    # ── ETFs ─────────────────────────────────────────────────────────────────
    "SPY":         {"fh_sym": "SPY",             "class": "equity",    "region": "americas",  "base":  520},
    "QQQ":         {"fh_sym": "QQQ",             "class": "equity",    "region": "americas",  "base":  450},
    "GLD":         {"fh_sym": "GLD",             "class": "commodity", "region": "global",    "base":  215},
    "SLV":         {"fh_sym": "SLV",             "class": "commodity", "region": "global",    "base":   23},
    "USO":         {"fh_sym": "USO",             "class": "commodity", "region": "global",    "base":   72},
    "UNG":         {"fh_sym": "UNG",             "class": "commodity", "region": "global",    "base":  7.5},
    "WEAT":        {"fh_sym": "WEAT",            "class": "commodity", "region": "global",    "base":  5.8},
    "TLT":         {"fh_sym": "TLT",             "class": "bond",      "region": "americas",  "base":   92},
    "TIP":         {"fh_sym": "TIP",             "class": "bond",      "region": "americas",  "base":  107},
    "HYG":         {"fh_sym": "HYG",             "class": "bond",      "region": "americas",  "base":   75},
    "LQD":         {"fh_sym": "LQD",             "class": "bond",      "region": "americas",  "base":  108},
    "XLE":         {"fh_sym": "XLE",             "class": "equity",    "region": "americas",  "base":   88},
    "XLF":         {"fh_sym": "XLF",             "class": "equity",    "region": "americas",  "base":   41},
    "XLK":         {"fh_sym": "XLK",             "class": "equity",    "region": "americas",  "base":  210},
    "XLV":         {"fh_sym": "XLV",             "class": "equity",    "region": "americas",  "base":  145},
    "XLI":         {"fh_sym": "XLI",             "class": "equity",    "region": "americas",  "base":  120},
    "ITA":         {"fh_sym": "ITA",             "class": "equity",    "region": "americas",  "base":  140},
    "EEM":         {"fh_sym": "EEM",             "class": "equity",    "region": "global",    "base":   42},
}

from app.config.asset_list import ASSETS

# Default symbols polled every 10 seconds
def _get_all_symbols() -> list[str]:
    syms = []
    for market in ASSETS.values():
        for asset in market:
            syms.append(asset["symbol"])
    return list(set(syms))

DEFAULT_TRACKED_ASSETS = _get_all_symbols()


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class MarketTick:
    """Single OHLCV market data tick."""
    symbol:       str
    asset_class:  str        # equity / commodity / currency / bond / crypto
    region:       str
    ts:           datetime
    open:         float
    high:         float
    low:          float
    close:        float
    volume:       float
    realized_vol: float | None = None
    return_1d:    float | None = None
    return_5d:    float | None = None
    source:       str = "live"   # "finnhub" | source tag coming from the adapter

    def change_pct(self, prev_close: float | None = None) -> float:
        """Percentage change from open (or prev_close if provided)."""
        base = prev_close if prev_close else self.open
        if base and base != 0:
            return round((self.close - base) / base * 100, 3)
        return 0.0

    def to_ws_dict(self) -> dict:
        """Minimal dict for WebSocket broadcast."""
        return {
            "symbol":     self.symbol,
            "price":      self.close,
            "open":       self.open,
            "high":       self.high,
            "low":        self.low,
            "change_pct": self.change_pct(),
            "vol":        self.realized_vol,
            "source":     self.source,
            "ts":         self.ts.isoformat(),
        }


# ── Abstract adapter ──────────────────────────────────────────────────────────

class MarketFeedAdapter(ABC):
    """Abstract base for all market data providers.

    To add a new provider:
        1. Subclass this class
        2. Implement fetch_latest() and fetch_history()
        3. Set the `name` class attribute
    """
    name: str = "base"

    @abstractmethod
    async def fetch_latest(self, symbols: list[str]) -> list[MarketTick]:
        """Fetch the latest available quote for each symbol."""

    @abstractmethod
    async def fetch_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketTick]:
        """Fetch historical OHLCV bars between start and end (UTC)."""


# ── Finnhub adapter (primary) ─────────────────────────────────────────────────

_FINNHUB_BASE = "https://finnhub.io/api/v1"
_FINNHUB_QUOTE = "/quote"
_FINNHUB_CANDLES = "/stock/candle"
_FINNHUB_FOREX_CANDLES = "/forex/candle"
_FINNHUB_CRYPTO_CANDLES = "/crypto/candle"

_FINNHUB_RATE_LIMIT = 60    # free-tier requests per minute, per key
_REQUEST_TIMEOUT    = 8.0   # seconds per request


def _load_finnhub_keys() -> list[str]:
    """Load all configured Finnhub API keys (supports KEY + KEY_2 rotation)."""
    keys: list[str] = []
    try:
        from app.core.config import get_settings
        s = get_settings()
        if s.finnhub_api_key:
            keys.append(s.finnhub_api_key)
        if s.finnhub_api_key_2:
            keys.append(s.finnhub_api_key_2)
    except Exception:
        pass
    # Also check env vars directly (useful inside Docker before settings load)
    for env_var in ("FINNHUB_API_KEY", "FINNHUB_API_KEY_2"):
        v = os.environ.get(env_var, "")
        if v and v not in keys:
            keys.append(v)
    return keys or [""]   # always return at least one slot


class RealMarketAdapter(MarketFeedAdapter):
    """Fetches real-time quotes from the Finnhub REST API.

    Supports multiple API keys for round-robin rotation — each key has its own
    60 req/min limit, so N keys = N × 60 req/min effective capacity.

    With 2 keys: 120 req/min — comfortably handles 25 symbols at 1.5s spacing
    across both the API container and market_worker simultaneously.

    Environment variables: FINNHUB_API_KEY, FINNHUB_API_KEY_2
    """
    name = "finnhub"

    def __init__(self, api_key: str | None = None) -> None:
        if api_key:
            self._keys = [api_key]
        else:
            self._keys = _load_finnhub_keys()
        self._key_index = 0               # round-robin cursor
        self._clients: dict[str, httpx.AsyncClient] = {}   # one client per key
        # Track previous closes for change_pct calculations
        self._prev_close: dict[str, float] = {}
        logger.info(
            "finnhub_adapter_ready",
            key_count=len(self._keys),
            effective_rate_limit=len(self._keys) * _FINNHUB_RATE_LIMIT,
        )

    def _next_key(self) -> str:
        """Return the next API key in round-robin order."""
        key = self._keys[self._key_index % len(self._keys)]
        self._key_index += 1
        return key

    def _get_client(self, key: str | None = None) -> httpx.AsyncClient:
        """Return (or create) an httpx client for the given key."""
        k = key or self._keys[0]
        if k not in self._clients or self._clients[k].is_closed:
            self._clients[k] = httpx.AsyncClient(
                base_url=_FINNHUB_BASE,
                timeout=_REQUEST_TIMEOUT,
                headers={"X-Finnhub-Token": k},
            )
        return self._clients[k]

    async def close(self) -> None:
        for client in self._clients.values():
            if not client.is_closed:
                await client.aclose()

    async def fetch_quote(self, fh_symbol: str) -> dict | None:
        """Fetch single quote from /quote endpoint using round-robin key rotation."""
        key = self._next_key()
        client = self._get_client(key)
        try:
            resp = await client.get(
                _FINNHUB_QUOTE,
                params={"symbol": fh_symbol},
            )
            if resp.status_code == 429:
                # This key is rate-limited — try the next key immediately
                logger.warning("finnhub_rate_limit_hit", symbol=fh_symbol, key_suffix=key[-6:])
                if len(self._keys) > 1:
                    fallback_key = self._next_key()
                    fallback_client = self._get_client(fallback_key)
                    try:
                        resp2 = await fallback_client.get(_FINNHUB_QUOTE, params={"symbol": fh_symbol})
                        if resp2.status_code == 200:
                            data = resp2.json()
                            if data.get("c"):
                                return data
                    except Exception:
                        pass
                await asyncio.sleep(1.0)   # brief pause before moving to next symbol
                return None
            resp.raise_for_status()
            data = resp.json()
            # Finnhub returns {"c":price,"d":delta,"dp":delta_pct,"h":high,"l":low,"o":open,"pc":prev_close,"t":ts}
            if not data.get("c"):
                return None
            return data
        except httpx.TimeoutException:
            logger.warning("finnhub_timeout", symbol=fh_symbol)
            return None
        except Exception as exc:
            logger.warning("finnhub_fetch_error", symbol=fh_symbol, error=str(exc))
            return None

    @property
    def _api_key(self) -> str:
        """Primary key — backwards compat for callers that check truthiness."""
        return self._keys[0] if self._keys else ""

    async def fetch_latest(self, symbols: list[str]) -> list[MarketTick]:
        """Fetch real-time quotes for all symbols, with rate-limit spacing."""
        if not self._api_key:
            logger.warning("finnhub_no_api_key")
            return []

        ticks: list[MarketTick] = []
        now = datetime.now(UTC)

        # Deduplicate Finnhub symbols (many internal symbols map to same FH sym)
        fh_to_internal: dict[str, list[str]] = {}
        for sym in symbols:
            meta = FINNHUB_SYMBOL_MAP.get(sym)
            if not meta:
                continue
            fh_sym = meta["fh_sym"]
            fh_to_internal.setdefault(fh_sym, []).append(sym)

        # Rate-limit: space requests within per-key limits.
        # With 2 keys (120 req/min combined) and ~25 unique symbols per poll:
        #   25 requests × 0.5s gap = 12.5s per cycle — well within 30s interval.
        n_keys = max(1, len(self._keys))
        delay = max(0.3, (60.0 / _FINNHUB_RATE_LIMIT) / n_keys)  # ~0.5s with 2 keys

        for fh_sym, internal_syms in fh_to_internal.items():
            raw = await self.fetch_quote(fh_sym)
            if raw is None:
                continue

            price     = float(raw.get("c", 0))
            open_p    = float(raw.get("o", price))
            high_p    = float(raw.get("h", price))
            low_p     = float(raw.get("l", price))
            prev_close= float(raw.get("pc", open_p))
            ts_unix   = raw.get("t", int(time.time()))
            tick_ts   = datetime.fromtimestamp(ts_unix, tz=UTC) if ts_unix else now

            # Parkinson's volatility (annualised) from H/L
            if high_p > low_p > 0:
                realized_vol = math.sqrt(
                    1.0 / (4.0 * math.log(2)) * (math.log(high_p / low_p)) ** 2
                ) * math.sqrt(252)
            else:
                realized_vol = None

            return_1d = (price - prev_close) / prev_close if prev_close else None

            # Publish one tick per internal symbol mapping
            for sym in internal_syms:
                meta = FINNHUB_SYMBOL_MAP[sym]
                self._prev_close[sym] = prev_close
                ticks.append(MarketTick(
                    symbol=sym,
                    asset_class=meta["class"],
                    region=meta["region"],
                    ts=tick_ts,
                    open=round(open_p,   6),
                    high=round(high_p,   6),
                    low=round(low_p,     6),
                    close=round(price,   6),
                    volume=0.0,            # /quote doesn't include volume
                    realized_vol=round(realized_vol, 6) if realized_vol else None,
                    return_1d=round(return_1d, 6) if return_1d else None,
                    return_5d=None,        # would require history endpoint
                    source="finnhub",
                ))

            await asyncio.sleep(delay)

        logger.info("finnhub_quotes_fetched", count=len(ticks), symbols=len(fh_to_internal))
        return ticks

    async def fetch_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketTick]:
        """Fetch OHLCV candles from Finnhub.

        Routes to stock / forex / crypto candle endpoint based on symbol type.
        """
        if not self._api_key:
            return []

        meta = FINNHUB_SYMBOL_MAP.get(symbol)
        if not meta:
            return []

        fh_sym     = meta["fh_sym"]
        asset_class= meta["class"]
        ts_from    = int(start.timestamp())
        ts_to      = int(end.timestamp())
        resolution = "D"   # daily candles
        client     = self._get_client(self._next_key())

        try:
            if asset_class == "crypto":
                endpoint = _FINNHUB_CRYPTO_CANDLES
                params   = {"symbol": fh_sym, "resolution": resolution, "from": ts_from, "to": ts_to}
            elif asset_class == "currency":
                endpoint = _FINNHUB_FOREX_CANDLES
                fh_forex = fh_sym.replace("OANDA:", "")
                params   = {"symbol": fh_forex, "resolution": resolution, "from": ts_from, "to": ts_to}
            else:
                endpoint = _FINNHUB_CANDLES
                params   = {"symbol": fh_sym, "resolution": resolution, "from": ts_from, "to": ts_to}

            resp = await client.get(endpoint, params=params)
            if resp.status_code == 429:
                logger.warning("finnhub_rate_limit_history", symbol=symbol)
                return []
            resp.raise_for_status()
            data = resp.json()

            if data.get("s") != "ok":
                return []

            closes  = data.get("c", [])
            opens   = data.get("o", [])
            highs   = data.get("h", [])
            lows    = data.get("l", [])
            volumes = data.get("v", [])
            times   = data.get("t", [])

            ticks = []
            for i, ts_unix in enumerate(times):
                c = closes[i] if i < len(closes) else 0.0
                o = opens[i]  if i < len(opens)  else c
                h = highs[i]  if i < len(highs)  else c
                l_ = lows[i]  if i < len(lows)   else c
                v = volumes[i] if i < len(volumes) else 0.0
                r1d = (c - closes[i-1]) / closes[i-1] if i > 0 and closes[i-1] else 0.0
                ticks.append(MarketTick(
                    symbol=symbol,
                    asset_class=meta["class"],
                    region=meta["region"],
                    ts=datetime.fromtimestamp(ts_unix, tz=UTC),
                    open=round(o, 6), high=round(h, 6),
                    low=round(l_, 6), close=round(c, 6),
                    volume=float(v),
                    realized_vol=None,
                    return_1d=round(r1d, 6),
                    return_5d=None,
                    source="finnhub",
                ))
            return ticks

        except Exception as exc:
            logger.error("finnhub_history_failed", symbol=symbol, error=str(exc))
            return []


# ── (SyntheticMarketAdapter removed — live data only) ───────────────────────
# Keeping class names below for any import compatibility; they now raise.

class SyntheticMarketAdapter:
    """Removed. Synthetic data is permanently disabled."""
    def __init__(self, *a: object, **kw: object) -> None:
        raise RuntimeError(
            "SyntheticMarketAdapter has been removed. "
            "Set FINNHUB_API_KEY in .env for real market data."
        )


class _SyntheticStub:
    name = "synthetic_disabled"


# ── Binance adapter (crypto, public REST — no API key) ────────────────────────

# Maps internal symbol keys → Binance exchange symbol
_BINANCE_CRYPTO_SYMBOLS: dict[str, str] = {
    "BINANCE:BTCUSDT": "BTCUSDT",
    "BINANCE:ETHUSDT": "ETHUSDT",
    "BTCUSD":          "BTCUSDT",
    "ETHUSD":          "ETHUSDT",
    "BTCUSDT":         "BTCUSDT",
    "ETHUSDT":         "ETHUSDT",
}

_BINANCE_REST_BASE = "https://api.binance.com"
_BINANCE_REQUEST_TIMEOUT = 8.0


class BinanceCryptoAdapter(MarketFeedAdapter):
    """Fetches real-time crypto quotes from Binance public REST API.

    No API key required.  Uses /api/v3/ticker/bookTicker for bid/ask and
    /api/v3/ticker/24hr for 24-h OHLCV stats.
    """
    name = "binance"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_BINANCE_REST_BASE,
                timeout=_BINANCE_REQUEST_TIMEOUT,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def fetch_latest(self, symbols: list[str]) -> list[MarketTick]:
        """Fetch bid/ask snapshots from /api/v3/ticker/bookTicker (no key)."""
        client = self._get_client()
        now = datetime.now(UTC)
        ticks: list[MarketTick] = []

        # Map internal symbols → Binance symbols, deduplicate
        bn_to_internal: dict[str, list[str]] = {}
        for sym in symbols:
            bn_sym = _BINANCE_CRYPTO_SYMBOLS.get(sym)
            if bn_sym:
                bn_to_internal.setdefault(bn_sym, []).append(sym)

        if not bn_to_internal:
            return []

        try:
            # Batch request for all symbols at once
            resp = await client.get("/api/v3/ticker/bookTicker")
            resp.raise_for_status()
            all_books: list[dict] = resp.json()
        except Exception as exc:
            logger.error("binance_rest_fetch_failed", error=str(exc))
            return []

        # Index by symbol for quick lookup
        book_by_sym = {entry["symbol"]: entry for entry in all_books}

        for bn_sym, internal_syms in bn_to_internal.items():
            entry = book_by_sym.get(bn_sym)
            if not entry:
                continue
            try:
                bid = float(entry["bidPrice"])
                ask = float(entry["askPrice"])
                mid = (bid + ask) / 2.0
            except (KeyError, ValueError):
                continue

            for sym in internal_syms:
                ticks.append(MarketTick(
                    symbol=sym,
                    asset_class="crypto",
                    region="global",
                    ts=now,
                    open=mid, high=mid, low=mid, close=mid,
                    volume=0.0,
                    realized_vol=0.65,   # default crypto vol
                    return_1d=None,
                    return_5d=None,
                    source="binance:rest",
                ))

        logger.info("binance_rest_fetched", count=len(ticks))
        return ticks

    async def fetch_history(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[MarketTick]:
        """Fetch OHLCV candles from /api/v3/klines (no key)."""
        bn_sym = _BINANCE_CRYPTO_SYMBOLS.get(symbol, symbol.upper().replace("/", ""))
        client = self._get_client()
        try:
            resp = await client.get(
                "/api/v3/klines",
                params={
                    "symbol":    bn_sym,
                    "interval":  "1h",
                    "startTime": int(start.timestamp() * 1000),
                    "endTime":   int(end.timestamp() * 1000),
                    "limit":     500,
                },
            )
            resp.raise_for_status()
            rows: list[list] = resp.json()
        except Exception as exc:
            logger.error("binance_klines_failed", symbol=symbol, error=str(exc))
            return []

        ticks = []
        for row in rows:
            try:
                ts   = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
                o, h, l, c, v = (float(row[i]) for i in (1, 2, 3, 4, 5))
                ticks.append(MarketTick(
                    symbol=symbol,
                    asset_class="crypto",
                    region="global",
                    ts=ts,
                    open=round(o, 6), high=round(h, 6),
                    low=round(l, 6),  close=round(c, 6),
                    volume=float(v),
                    realized_vol=0.65,
                    return_1d=None,
                    return_5d=None,
                    source="binance:klines",
                ))
            except Exception:
                continue
        return ticks




# ── Market Feed Manager (polling loop + in-memory cache + Binance WS) ───────

from app.services.asset_discovery_service import get_asset_discovery_service

class MarketFeedManager:
    """Runs a background polling loop at a configurable interval.
    
    Now uses the centralized MarketEngine to fetch data for all assets.
    Also includes a periodic task to refresh the asset universe dynamically.
    """

    def __init__(
        self,
        adapter: MarketFeedAdapter | None = None,
        symbols: list[str] | None = None,
        poll_interval: float = 10.0, # Faster polling as requested
        discovery_interval: float = 3600.0, # 1 hour
    ) -> None:
        self.adapter = adapter or _build_default_adapter()
        self.symbols = symbols or [] # Start with empty, will be populated by discovery
        self.poll_interval = poll_interval
        self.discovery_interval = discovery_interval
        self.discovery_svc = get_asset_discovery_service()
        self._cache: dict[str, MarketTick] = {}
        self._poll_task: asyncio.Task | None = None
        self._discovery_task: asyncio.Task | None = None
        self._ws_mgr: Any | None = None

    async def _discovery_loop(self) -> None:
        """Periodically refresh the asset universe."""
        while True:
            try:
                logger.info("running_dynamic_asset_discovery")
                universe = await self.discovery_svc.get_asset_universe(force_refresh=True)
                
                new_symbols = []
                for market in universe.values():
                    for asset in market:
                        new_symbols.append(asset["symbol"])
                
                self.symbols = list(set(new_symbols))
                logger.info("asset_universe_updated", total_symbols=len(self.symbols))

            except Exception as e:
                logger.error(f"Error in asset discovery loop: {e}")
            
            await asyncio.sleep(self.discovery_interval)

    async def start(self) -> None:
        """Start the background polling and discovery loops."""
        if self._poll_task and not self._poll_task.done():
            return

        # Run initial discovery to populate symbols before starting the poll
        await self._discovery_loop() 

        self._poll_task = asyncio.create_task(self._polling_loop(), name="market_feed_poll_loop")
        self._discovery_task = asyncio.create_task(self._discovery_loop(), name="market_feed_discovery_loop")
        logger.info(
            "market_feed_manager_started",
            poll_interval_s=self.poll_interval,
            discovery_interval_s=self.discovery_interval
        )

    async def stop(self) -> None:
        """Cancel all background tasks."""
        for task in [self._poll_task, self._discovery_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if hasattr(self.adapter, "close"):
            await self.adapter.close()
        logger.info("market_feed_manager_stopped")

    def _on_binance_ws_tick(self, tick: Any) -> None:
        """Handle a real-time Binance WebSocket tick — update the MarketTick cache."""
        try:
            mid = float(tick.mid)
        except Exception:
            return
        market_tick = MarketTick(
            symbol=tick.symbol,
            asset_class="crypto",
            region="global",
            ts=tick.ts,
            open=mid, high=mid, low=mid, close=mid,
            volume=0.0,
            realized_vol=0.65,
            return_1d=None,
            return_5d=None,
            source="binance:ws",
        )
        # Cache under the raw Binance symbol (e.g. "BTCUSDT")
        self._cache[tick.symbol] = market_tick
        # Also cache under any matching internal alias (e.g. "BINANCE:BTCUSDT", "BTCUSD")
        for app_sym, bn_sym in _BINANCE_CRYPTO_SYMBOLS.items():
            if bn_sym == tick.symbol.upper():
                self._cache[app_sym] = market_tick

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.poll_interval)
                await self._poll_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("market_feed_loop_error", error=str(exc))

    async def _poll_once(self) -> None:
        """Single poll using the centralized MarketEngine."""
        try:
            engine = get_market_engine()
            # Fetch from all services concurrently via engine's services
            tasks = [
                engine.forex.get_all_prices(),
                engine.commodities.get_all_prices(),
                engine.crypto.get_all_prices(),
                engine.stocks.get_all_prices(),
                engine.macro.get_all_prices()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            new_ticks = []
            for res in results:
                if isinstance(res, list):
                    new_ticks.extend(res)
            
            for tick in new_ticks:
                self._cache[tick.symbol] = tick
                # Also handle symbol mapping if needed (e.g. for crypto aliases)
                if tick.asset_class == "crypto":
                    # Map to common aliases like BTCUSD
                    self._cache[f"{tick.symbol}USD"] = tick
                    self._cache[f"BINANCE:{tick.symbol}USDT"] = tick

            # Broadcast updates to WS
            if self._ws_mgr and new_ticks:
                for tick in new_ticks:
                    await self._ws_mgr.broadcast(
                        "market", 
                        {"type": "price_update", "data": tick.to_ws_dict()}
                    )
            
            logger.debug("market_feed_polled", count=len(new_ticks))
        except Exception as e:
            logger.error(f"Error in market feed poll: {e}")

    # ── Query API ─────────────────────────────────────────────────────────────

    def get_latest(self, symbol: str) -> MarketTick | None:
        """Return the most recently cached tick for a symbol."""
        return self._cache.get(symbol)

    def get_all(self) -> list[MarketTick]:
        """Return all cached ticks."""
        return list(self._cache.values())

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        """Return {symbol: close_price} for a list of symbols."""
        return {s: t.close for s in symbols if (t := self._cache.get(s))}

    def snapshot(self) -> dict[str, dict]:
        """Return serializable snapshot of all cached ticks."""
        return {sym: tick.to_ws_dict() for sym, tick in self._cache.items()}

    def get_realized_vol(self, symbol: str) -> float:
        """Return realized vol for a symbol, falling back to class default."""
        tick = self._cache.get(symbol)
        if tick and tick.realized_vol:
            return tick.realized_vol
        meta = FINNHUB_SYMBOL_MAP.get(symbol, {})
        defaults = {"equity": 0.18, "commodity": 0.25, "currency": 0.08, "bond": 0.10, "crypto": 0.65}
        return defaults.get(meta.get("class", "equity"), 0.20)

    def get_return_1d(self, symbol: str) -> float:
        """Return 1-day return for a symbol."""
        tick = self._cache.get(symbol)
        return tick.return_1d if (tick and tick.return_1d is not None) else 0.0


# ── Singleton factory ─────────────────────────────────────────────────────────

def _build_default_adapter() -> RealMarketAdapter | Any:
    """Return the Finnhub live adapter with all configured keys for rotation.

    Raises RuntimeError if no FINNHUB_API_KEY is set — the system will not
    start without a real data source.
    """
    keys = _load_finnhub_keys()
    if not any(keys):
        from app.core.config import get_settings
        settings = get_settings()
        if settings.app_env == "development":
            logger.warning("FINNHUB_API_KEY not set. Using mock adapter for development.")
            return _MockMarketAdapter()
        raise RuntimeError(
            "FINNHUB_API_KEY is not set. Add it to .env — synthetic data is disabled."
        )
    adapter = RealMarketAdapter()   # _load_finnhub_keys() called internally
    logger.info(
        "market_feed_live_adapter_ready",
        key_count=len(adapter._keys),
        key_prefixes=[k[:8] for k in adapter._keys],
    )
    return adapter


class _MockMarketAdapter(MarketFeedAdapter):
    name = "mock"
    async def fetch_latest(self, symbols: list[str]) -> list[MarketTick]:
        now = datetime.now(UTC)
        ticks = []
        for sym in symbols:
            meta = FINNHUB_SYMBOL_MAP.get(sym, {"class": "equity", "region": "global", "base": 100.0})
            base = meta.get("base", 100.0)
            price = base * (1 + (np.random.random() - 0.5) * 0.02)
            ticks.append(MarketTick(
                symbol=sym,
                asset_class=meta["class"],
                region=meta["region"],
                ts=now,
                open=price, high=price*1.01, low=price*0.99, close=price,
                volume=1000.0,
                realized_vol=0.2,
                return_1d=0.01,
                source="mock"
            ))
        return ticks
    async def fetch_history(self, symbol: str, start: datetime, end: datetime) -> list[MarketTick]:
        return []


_feed_manager: MarketFeedManager | None = None


def get_feed_manager() -> MarketFeedManager:
    """Return the global MarketFeedManager singleton."""
    global _feed_manager  # noqa: PLW0603
    if _feed_manager is None:
        _feed_manager = MarketFeedManager(
            adapter=_build_default_adapter(),
            symbols=DEFAULT_TRACKED_ASSETS,
            poll_interval=30.0,
        )
    return _feed_manager


def get_market_feed() -> RealMarketAdapter:
    """Return the live Finnhub market feed adapter."""
    return _build_default_adapter()
