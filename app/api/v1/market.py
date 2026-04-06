"""Market data endpoints.

Endpoints:
    GET /market/prices          — latest prices from DB
    GET /market/live            — real-time prices from Finnhub cache (no DB)
    GET /market/live/{symbol}   — single symbol live quote
    GET /market/history/{symbol} — historical OHLCV from DB
    POST /market/refresh        — trigger on-demand poll from Finnhub
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.pipelines.market_feeds import get_feed_manager, FINNHUB_SYMBOL_MAP
from app.repositories.market_repo import MarketDataRepository

from app.services.market_engine import get_market_engine

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/all")
async def get_all_markets(
    refresh: bool = Query(default=False, description="Force refresh from source APIs"),
) -> List[Dict[str, Any]]:
    """Return ALL assets across ALL markets with real-time prices and AI signals.
    
    This is the complete market data engine endpoint.
    """
    engine = get_market_engine()
    return await engine.get_all_market_data(refresh=refresh)


@router.get("/prices")
async def get_latest_prices(
    symbols: str | None = Query(default=None, description="Comma-separated symbols"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get latest market prices for tracked assets."""
    repo = MarketDataRepository(db)
    rows = await repo.get_latest_per_symbol()

    if symbols:
        symbol_set = {s.strip().upper() for s in symbols.split(",")}
        rows = [r for r in rows if r.symbol in symbol_set]

    return {
        "prices": [
            {
                "symbol": r.symbol,
                "asset_class": r.asset_class,
                "region": r.region,
                "ts": r.ts.isoformat() if r.ts else None,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "realized_vol": r.realized_vol,
                "return_1d": r.return_1d,
                "return_5d": r.return_5d,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/live")
async def get_live_prices(
    symbols: str | None = Query(default=None, description="Comma-separated symbols; omit for all"),
) -> dict:
    """Return real-time prices from the live feed cache.

    This endpoint reads from the in-memory MarketFeedManager cache that is
    refreshed every 30 seconds. No DB call is made.
    Source field indicates the upstream adapter (finnhub / binance:ws / binance:rest).
    """
    mgr  = get_feed_manager()
    all_ticks = mgr.get_all()

    if symbols:
        sym_set = {s.strip().upper() for s in symbols.split(",")}
        all_ticks = [t for t in all_ticks if t.symbol in sym_set]

    data = [t.to_ws_dict() for t in all_ticks]
    data.sort(key=lambda d: d["symbol"])

    return {
        "prices":      data,
        "count":       len(data),
        "data_source": "live_feed_manager",
        "data_as_of":  datetime.now(UTC).isoformat(),
    }


@router.get("/live/{symbol}")
async def get_live_price_single(symbol: str) -> dict:
    """Return the latest real-time quote for a single symbol."""
    mgr  = get_feed_manager()
    tick = mgr.get_latest(symbol.upper())

    if tick is None:
        # Try fetching on demand if not yet in cache
        from app.pipelines.market_feeds import _build_default_adapter
        adapter = _build_default_adapter()
        ticks   = await adapter.fetch_latest([symbol.upper()])
        tick    = ticks[0] if ticks else None

    if tick is None:
        meta = FINNHUB_SYMBOL_MAP.get(symbol.upper(), {})
        return {
            "symbol":  symbol.upper(),
            "price":   meta.get("base", 0),
            "source":  "not_found",
            "message": f"No live data for {symbol}. Is it in the tracked symbol list?",
        }

    return {"symbol": tick.symbol, **tick.to_ws_dict()}


@router.post("/refresh")
async def trigger_market_refresh() -> dict:
    """Trigger an immediate poll from the Finnhub API (bypasses 30s timer)."""
    mgr = get_feed_manager()
    await mgr._poll_once()
    return {
        "status":      "ok",
        "symbols_cached": len(mgr._cache),
        "data_as_of":  datetime.now(UTC).isoformat(),
    }


@router.get("/history/{symbol}")
async def get_price_history(
    symbol: str,
    start: datetime = Query(
        default_factory=lambda: datetime.now(UTC) - timedelta(days=7),
    ),
    end: datetime = Query(default_factory=lambda: datetime.now(UTC)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get historical OHLCV data for a symbol."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)

    repo = MarketDataRepository(db)
    rows = await repo.get_history(symbol=symbol.upper(), start=start, end=end)

    return {
        "symbol": symbol.upper(),
        "data": [
            {
                "ts": r.ts.isoformat(),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "realized_vol": r.realized_vol,
            }
            for r in rows
        ],
        "count": len(rows),
    }
