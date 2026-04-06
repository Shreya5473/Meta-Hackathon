"""Paper Trading — Market Data Ingestion Service.

Fetches live prices from two sources and persists them to the
``live_price_ticks`` TimescaleDB hypertable:

* **OANDA v20 Practice API** — EUR/USD (and any other FX pair)
* **Binance Public REST API** — crypto spot prices, no API key required
* **Binance Public WebSocket** — millisecond real-time trades, no API key

Beat tasks are wired via :mod:`app.tasks.market_tasks`; call
``PaperTradingFeed.run_once()`` from a Celery task to keep the
async/sync boundary clean.

Binance WebSocket streams used (all public, no authentication):
  wss://stream.binance.com:9443/ws/<symbol>@bookTicker
  wss://stream.binance.com:9443/ws/<symbol>@trade
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Binance public REST base (no API key needed for market data)
_BINANCE_REST = "https://api.binance.com"
# Binance public WebSocket base
_BINANCE_WS = "wss://stream.binance.com:9443/ws"

# Map internal symbol → Binance REST symbol
_BINANCE_SYMBOL_MAP: dict[str, str] = {
    "BTCUSDT":          "BTCUSDT",
    "ETHUSDT":          "ETHUSDT",
    "BNBUSDT":          "BNBUSDT",
    "SOLUSDT":          "SOLUSDT",
    "XRPUSDT":          "XRPUSDT",
    "ADAUSDT":          "ADAUSDT",
    "DOGEUSDT":         "DOGEUSDT",
    "LTCUSDT":          "LTCUSDT",
    "DOTUSDT":          "DOTUSDT",
    "MATICUSDT":        "MATICUSDT",
    "LINKUSDT":         "LINKUSDT",
    "AVAXUSDT":         "AVAXUSDT",
    "SHIBUSDT":         "SHIBUSDT",
    "TRXUSDT":          "TRXUSDT",
    "DOTUSDT":          "DOTUSDT",
    # Canonical aliases used across the app
    "BINANCE:BTCUSDT":  "BTCUSDT",
    "BINANCE:ETHUSDT":  "ETHUSDT",
    "BINANCE:BNBUSDT":  "BNBUSDT",
    "BINANCE:SOLUSDT":  "SOLUSDT",
    "BINANCE:XRPUSDT":  "XRPUSDT",
    "BINANCE:ADAUSDT":  "ADAUSDT",
    "BINANCE:DOGEUSDT": "DOGEUSDT",
    "BINANCE:DOTUSDT":  "DOTUSDT",
    "BINANCE:MATICUSDT":"MATICUSDT",
    "BINANCE:LINKUSDT": "LINKUSDT",
    "BTCUSD":           "BTCUSDT",
    "ETHUSD":           "ETHUSDT",
    "BNBUSD":           "BNBUSDT",
    "SOLUSD":           "SOLUSDT",
    "XRPUSD":           "XRPUSDT",
    "ADAUSD":           "ADAUSDT",
    "DOGEUSD":          "DOGEUSDT",
    "DOTUSD":           "DOTUSDT",
    "MATICUSD":         "MATICUSDT",
    "LINKUSD":          "LINKUSDT",
}

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class PriceTick:
    """Normalised price tick from any data source."""

    symbol: str          # e.g. "EUR_USD", "BTC/USDT"
    source: str          # "oanda" | "ccxt:<exchange>"
    ts: datetime         # UTC timestamp
    bid: Decimal
    ask: Decimal
    mid: Decimal
    spread: Decimal


# ---------------------------------------------------------------------------
# OANDA adapter
# ---------------------------------------------------------------------------


class OandaFeed:
    """Fetch live FX prices from the OANDA v20 practice API.

    Uses the ``oandapyV20`` synchronous SDK wrapped in
    ``asyncio.to_thread`` so it does not block the event loop.
    """

    DEFAULT_INSTRUMENTS = [
        "EUR_USD", "USD_JPY", "GBP_USD", "USD_CHF", "AUD_USD", 
        "USD_CAD", "NZD_USD", "EUR_GBP", "EUR_JPY", "GBP_JPY"
    ]

    def __init__(self) -> None:
        self._settings = get_settings()

    async def fetch(self, instruments: list[str] | None = None) -> list[PriceTick]:
        """Return latest bid/ask ticks for *instruments*."""
        instruments = instruments or self.DEFAULT_INSTRUMENTS
        return await asyncio.to_thread(self._fetch_sync, instruments)

    # ------------------------------------------------------------------
    def _fetch_sync(self, instruments: list[str]) -> list[PriceTick]:
        try:
            import oandapyV20  # type: ignore[import-untyped]
            import oandapyV20.endpoints.pricing as pricing  # type: ignore[import-untyped]
        except ImportError as exc:
            logger.error("oandapyV20_not_installed", error=str(exc))
            return []

        settings = self._settings
        if not settings.oanda_api_key or not settings.oanda_account_id:
            logger.warning(
                "oanda_credentials_missing",
                hint="Set OANDA_API_KEY and OANDA_ACCOUNT_ID in .env",
            )
            return []

        client = oandapyV20.API(
            access_token=settings.oanda_api_key,
            environment=settings.oanda_environment,  # "practice" or "live"
        )

        params = {"instruments": ",".join(instruments)}
        request = pricing.PricingInfo(accountID=settings.oanda_account_id, params=params)

        try:
            client.request(request)
        except Exception as exc:  # noqa: BLE001
            logger.error("oanda_request_failed", error=str(exc))
            return []

        ticks: list[PriceTick] = []
        now = datetime.now(UTC)
        for price in request.response.get("prices", []):
            try:
                bid = Decimal(str(price["bids"][0]["price"]))
                ask = Decimal(str(price["asks"][0]["price"]))
                mid = (bid + ask) / 2
                spread = ask - bid
                # OANDA timestamps are ISO-8601 strings
                raw_ts = price.get("time", "")
                ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")) if raw_ts else now
                ticks.append(
                    PriceTick(
                        symbol=price["instrument"],  # e.g. "EUR_USD"
                        source="oanda",
                        ts=ts,
                        bid=bid,
                        ask=ask,
                        mid=mid,
                        spread=spread,
                    )
                )
            except (KeyError, IndexError, Exception) as exc:  # noqa: BLE001
                logger.warning("oanda_tick_parse_error", instrument=price.get("instrument"), error=str(exc))

        logger.info("oanda_ticks_fetched", count=len(ticks))
        return ticks


# ---------------------------------------------------------------------------
# Binance public REST adapter  (no API key required)
# ---------------------------------------------------------------------------


class BinanceFeed:
    """Fetch live crypto prices from Binance public REST API.

    Uses ``GET /api/v3/ticker/bookTicker`` (best bid/ask) for snapshots.
    No API key, no authentication — Binance public endpoint.

    Symbol format accepted:
      - "BTCUSDT", "ETHUSDT"  (Binance native)
      - "BTC/USDT", "ETH/USDT" (CCXT-style, auto-converted)
      - "BINANCE:BTCUSDT"      (Finnhub-style, auto-converted)
      - "BTCUSD", "ETHUSD"     (app-internal aliases)
    """

    DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

    async def fetch(self, symbols: list[str] | None = None) -> list[PriceTick]:
        """Return best bid/ask ticks for *symbols* via Binance REST."""
        symbols = symbols or self.DEFAULT_SYMBOLS
        binance_syms = [
            _BINANCE_SYMBOL_MAP.get(s, s.replace("/", "").replace("BINANCE:", "")).upper()
            for s in symbols
        ]
        # Deduplicate while preserving original→binance mapping
        orig_map: dict[str, str] = {}  # binance_sym → original_sym
        for orig, bn in zip(symbols, binance_syms):
            orig_map[bn] = orig

        async with httpx.AsyncClient(timeout=8.0) as client:
            ticks: list[PriceTick] = []
            if len(binance_syms) == 1:
                # Single-symbol endpoint (faster)
                ticks = await self._fetch_one(client, binance_syms[0], orig_map)
            else:
                # Batch: fetch all bookTickers, then filter
                ticks = await self._fetch_batch(client, set(binance_syms), orig_map)
        logger.info("binance_rest_ticks_fetched", count=len(ticks))
        return ticks

    async def _fetch_one(
        self, client: httpx.AsyncClient, symbol: str, orig_map: dict[str, str]
    ) -> list[PriceTick]:
        try:
            r = await client.get(
                f"{_BINANCE_REST}/api/v3/ticker/bookTicker",
                params={"symbol": symbol},
            )
            r.raise_for_status()
            return [self._parse_book(r.json(), orig_map)]
        except Exception as exc:
            logger.warning("binance_rest_fetch_failed", symbol=symbol, error=str(exc))
            return []

    async def _fetch_batch(
        self,
        client: httpx.AsyncClient,
        symbols: set[str],
        orig_map: dict[str, str],
    ) -> list[PriceTick]:
        try:
            # /api/v3/ticker/bookTicker with no symbol returns ALL symbols
            r = await client.get(f"{_BINANCE_REST}/api/v3/ticker/bookTicker")
            r.raise_for_status()
            ticks = []
            for item in r.json():
                if item["symbol"] in symbols:
                    ticks.append(self._parse_book(item, orig_map))
            return ticks
        except Exception as exc:
            logger.warning("binance_rest_batch_failed", error=str(exc))
            return []

    @staticmethod
    def _parse_book(data: dict, orig_map: dict[str, str]) -> PriceTick:
        """Parse a bookTicker response into a PriceTick."""
        bn_sym = data["symbol"]
        bid = Decimal(str(data["bidPrice"]))
        ask = Decimal(str(data["askPrice"]))
        mid = (bid + ask) / 2
        spread = ask - bid
        return PriceTick(
            symbol=orig_map.get(bn_sym, bn_sym),  # restore original symbol name
            source="binance:rest",
            ts=datetime.now(UTC),
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
        )

    @staticmethod
    async def fetch_klines(
        symbol: str,
        interval: str = "1h",
        limit: int = 500,
    ) -> list[dict]:
        """Fetch historical candlestick (kline) data — no API key needed.

        Args:
            symbol:   Binance symbol, e.g. "BTCUSDT"
            interval: Kline interval: 1m 5m 15m 1h 4h 1d 1w
            limit:    Number of candles (max 1000)

        Returns:
            List of dicts with keys: ts, open, high, low, close, volume
        """
        bn_sym = _BINANCE_SYMBOL_MAP.get(symbol, symbol.replace("/", "")).upper()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{_BINANCE_REST}/api/v3/klines",
                params={"symbol": bn_sym, "interval": interval, "limit": limit},
            )
            r.raise_for_status()
            return [
                {
                    "ts":     datetime.fromtimestamp(row[0] / 1000, tz=UTC),
                    "open":   float(row[1]),
                    "high":   float(row[2]),
                    "low":    float(row[3]),
                    "close":  float(row[4]),
                    "volume": float(row[5]),
                }
                for row in r.json()
            ]


# ---------------------------------------------------------------------------
# Binance public WebSocket adapter  (no API key required)
# ---------------------------------------------------------------------------


class BinanceWSFeed:
    """Stream real-time crypto prices via Binance public WebSocket.

    Connects to the combined stream endpoint and subscribes to
    ``<symbol>@bookTicker`` for live best bid/ask on every market update.
    No API key or authentication is required.

    WebSocket URL format:
        wss://stream.binance.com:9443/ws/<symbol1>@bookTicker/<symbol2>@bookTicker

    Usage::

        feed = BinanceWSFeed(["BTCUSDT", "ETHUSDT"])
        await feed.start(on_tick=my_callback)  # runs forever in background
        await feed.stop()
    """

    DEFAULT_SYMBOLS = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", 
        "ADAUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT"
    ]
    _RECONNECT_DELAY = 5   # seconds before reconnecting after disconnect

    def __init__(self, symbols: list[str] | None = None) -> None:
        self._symbols: list[str] = [
            _BINANCE_SYMBOL_MAP.get(s, s.upper().replace("/", "").replace("BINANCE:", ""))
            for s in (symbols or self.DEFAULT_SYMBOLS)
        ]
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._on_tick_cb: Any = None   # Callable[[PriceTick], None]
        # Latest tick per symbol — available for synchronous reads
        self.cache: dict[str, PriceTick] = {}

    async def start(self, on_tick: Any = None) -> None:
        """Start background WebSocket listener.

        Args:
            on_tick: Optional async/sync callable(PriceTick) called on each update.
        """
        self._on_tick_cb = on_tick
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="binance_ws_feed")
        logger.info("binance_ws_started", symbols=self._symbols)

    async def stop(self) -> None:
        """Gracefully stop the WebSocket listener."""
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("binance_ws_stopped")

    def get_latest(self, symbol: str) -> PriceTick | None:
        """Return the last received tick for *symbol* (sync, non-blocking)."""
        return self.cache.get(symbol)

    # ------------------------------------------------------------------
    # Internal

    def _build_ws_url(self) -> str:
        """Compose the combined stream URL for all symbols."""
        streams = "/".join(f"{s.lower()}@bookTicker" for s in self._symbols)
        return f"{_BINANCE_WS}/{streams}"

    async def _run_loop(self) -> None:
        """Reconnecting WebSocket loop — runs until stop() is called.

        HTTP 4xx responses (e.g. 451 geo-block, 403 forbidden) are treated as
        permanent failures.  After _MAX_4XX_ATTEMPTS the loop exits cleanly so
        the MarketFeedManager REST fallback takes over for crypto prices.
        """
        import websockets  # type: ignore[import]

        url = self._build_ws_url()
        consecutive_4xx = 0
        _MAX_4XX_ATTEMPTS = 3

        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    consecutive_4xx = 0  # reset on successful connection
                    logger.info("binance_ws_connected", url=url)
                    async for raw_msg in ws:
                        if self._stop_event.is_set():
                            break
                        self._handle_message(raw_msg)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                # Detect permanent HTTP errors (geo-block 451, forbidden 403, etc.)
                err_str = str(exc)
                status_code: int | None = None
                if hasattr(exc, "status_code"):
                    status_code = int(exc.status_code)  # type: ignore[union-attr]
                elif "HTTP 4" in err_str:
                    try:
                        status_code = int(err_str.split("HTTP ")[1].split()[0])
                    except Exception:
                        pass

                if status_code is not None and 400 <= status_code < 500:
                    consecutive_4xx += 1
                    if consecutive_4xx >= _MAX_4XX_ATTEMPTS:
                        logger.warning(
                            "binance_ws_permanently_blocked",
                            status=status_code,
                            hint="Binance WebSocket is geo-blocked on this server. "
                                 "Crypto prices will be served via REST fallback.",
                        )
                        self._stop_event.set()
                        break
                    # Exponential back-off before retrying
                    backoff = self._RECONNECT_DELAY * (2 ** consecutive_4xx)
                    logger.warning(
                        "binance_ws_disconnected",
                        error=err_str,
                        status=status_code,
                        attempt=consecutive_4xx,
                        reconnect_in=backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    # Transient error (network blip, timeout) — standard delay
                    logger.warning(
                        "binance_ws_disconnected",
                        error=err_str,
                        reconnect_in=self._RECONNECT_DELAY,
                    )
                    await asyncio.sleep(self._RECONNECT_DELAY)

    def _handle_message(self, raw_msg: str) -> None:
        """Parse a bookTicker frame and update cache + callback."""
        try:
            data = json.loads(raw_msg)
            # bookTicker payload: {"u":..., "s":"BTCUSDT", "b":"bid", "B":"bidQty", "a":"ask", "A":"askQty"}
            bn_sym = data.get("s", "")
            if not bn_sym:
                return
            bid = Decimal(str(data["b"]))
            ask = Decimal(str(data["a"]))
            mid = (bid + ask) / 2
            spread = ask - bid
            tick = PriceTick(
                symbol=bn_sym,
                source="binance:ws",
                ts=datetime.now(UTC),
                bid=bid,
                ask=ask,
                mid=mid,
                spread=spread,
            )
            self.cache[bn_sym] = tick
            if self._on_tick_cb is not None:
                try:
                    result = self._on_tick_cb(tick)
                    if asyncio.iscoroutine(result):
                        asyncio.ensure_future(result)
                except Exception as exc:
                    logger.warning("binance_ws_callback_error", error=str(exc))
        except Exception as exc:
            logger.warning("binance_ws_parse_error", error=str(exc))


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------


async def _persist_ticks(ticks: list[PriceTick]) -> int:
    """Bulk-insert *ticks* into ``live_price_ticks`` using raw SQL.

    Uses ``INSERT … ON CONFLICT DO NOTHING`` so duplicate ticks from
    overlapping Celery beats are silently discarded.
    """
    if not ticks:
        return 0

    from sqlalchemy import text

    from app.core.database import get_db_session

    rows = [
        {
            "symbol": t.symbol,
            "source": t.source,
            "ts": t.ts,
            "bid": float(t.bid),
            "ask": float(t.ask),
            "mid": float(t.mid),
            "spread": float(t.spread),
        }
        for t in ticks
    ]

    stmt = text(
        """
        INSERT INTO live_price_ticks (symbol, source, ts, bid, ask, mid, spread)
        VALUES (:symbol, :source, :ts, :bid, :ask, :mid, :spread)
        ON CONFLICT (symbol, ts) DO NOTHING
        """
    )

    async with get_db_session() as session:
        await session.execute(stmt, rows)
        await session.commit()

    return len(rows)


# ---------------------------------------------------------------------------
# Orchestrator — called from Celery task
# ---------------------------------------------------------------------------


class PaperTradingFeed:
    """Orchestrate price fetching from all configured sources.

    Sources:
    - OANDA Practice API   → FX pairs (requires OANDA_API_KEY in .env)
    - Binance Public REST  → crypto spot prices (no API key needed)
    """

    def __init__(self) -> None:
        self._oanda = OandaFeed()
        self._binance = BinanceFeed()

    async def run_once(self) -> dict[str, int]:
        """Fetch from all sources and persist.  Returns per-source counts."""
        oanda_ticks, binance_ticks = await asyncio.gather(
            self._oanda.fetch(),
            self._binance.fetch(),
            return_exceptions=True,
        )

        all_ticks: list[PriceTick] = []
        if isinstance(oanda_ticks, list):
            all_ticks.extend(oanda_ticks)
        if isinstance(binance_ticks, list):
            all_ticks.extend(binance_ticks)

        saved = await _persist_ticks(all_ticks)
        logger.info("paper_trading_feed_cycle_done", saved=saved)
        return {
            "oanda": len(oanda_ticks) if isinstance(oanda_ticks, list) else 0,
            "binance": len(binance_ticks) if isinstance(binance_ticks, list) else 0,
            "saved": saved,
        }
