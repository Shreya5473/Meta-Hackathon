"""WebSocket connection manager for real-time UI updates.

Supports multiple channels:
    - gti       : GTI value changes
    - signals   : new trading signals
    - events    : new geopolitical events
    - market    : market data ticks
    - alerts    : threshold alerts

Architecture:
    ConnectionManager maintains per-channel subscriber sets.
    Background tasks publish to channels; connections receive broadcasts.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect

from app.core.logging import get_logger

logger = get_logger(__name__)


class WSChannel(str, Enum):
    GTI = "gti"
    SIGNALS = "signals"
    EVENTS = "events"
    MARKET = "market"
    ALERTS = "alerts"
    ALL = "all"


class ConnectionManager:
    """Manages WebSocket connections and channel subscriptions."""

    def __init__(self) -> None:
        # channel → set of (connection_id, websocket)
        self._connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, channels: list[str] | None = None
    ) -> str:
        """Accept a WebSocket and subscribe to channels. Returns connection ID."""
        await websocket.accept()
        conn_id = str(uuid4())[:8]

        channels = channels or [WSChannel.ALL.value]
        async with self._lock:
            for channel in channels:
                self._connections[channel][conn_id] = websocket

        logger.info(
            "ws_connected",
            conn_id=conn_id,
            channels=channels,
            total_connections=self.total_connections,
        )

        # Send initial connection acknowledgment
        await websocket.send_json({
            "type": "connection_established",
            "conn_id": conn_id,
            "channels": channels,
            "ts": datetime.now(UTC).isoformat(),
        })

        return conn_id

    async def disconnect(self, conn_id: str) -> None:
        """Remove a connection from all channels."""
        async with self._lock:
            for channel in list(self._connections.keys()):
                self._connections[channel].pop(conn_id, None)
                if not self._connections[channel]:
                    del self._connections[channel]

        logger.info(
            "ws_disconnected",
            conn_id=conn_id,
            total_connections=self.total_connections,
        )

    async def broadcast(self, channel: str, data: dict[str, Any]) -> None:
        """Broadcast a message to all subscribers of a channel."""
        message = {
            "channel": channel,
            "data": data,
            "ts": datetime.now(UTC).isoformat(),
        }

        disconnected: list[str] = []

        # Send to channel subscribers
        for conn_id, ws in self._connections.get(channel, {}).items():
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(conn_id)

        # Also send to "all" subscribers
        for conn_id, ws in self._connections.get(WSChannel.ALL.value, {}).items():
            if conn_id not in self._connections.get(channel, {}):
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(conn_id)

        # Clean up disconnected
        for conn_id in disconnected:
            await self.disconnect(conn_id)

    async def broadcast_gti_update(
        self,
        region: str,
        gti_value: float,
        gti_delta: float,
        confidence: float,
    ) -> None:
        await self.broadcast(WSChannel.GTI.value, {
            "type": "gti_update",
            "region": region,
            "gti_value": gti_value,
            "gti_delta_1h": gti_delta,
            "confidence": confidence,
        })

    async def broadcast_new_event(
        self,
        event_id: str,
        title: str,
        region: str,
        classification: str,
        severity: float,
    ) -> None:
        await self.broadcast(WSChannel.EVENTS.value, {
            "type": "new_event",
            "event_id": event_id,
            "title": title,
            "region": region,
            "classification": classification,
            "severity_score": severity,
        })

    async def broadcast_new_signal(
        self,
        asset: str,
        action: str,
        confidence: float,
        reasoning: str,
    ) -> None:
        await self.broadcast(WSChannel.SIGNALS.value, {
            "type": "new_signal",
            "asset": asset,
            "action": action,
            "confidence_pct": confidence,
            "reasoning_summary": reasoning,
        })

    async def broadcast_market_tick(
        self,
        symbol: str,
        price: float,
        change_pct: float,
    ) -> None:
        await self.broadcast(WSChannel.MARKET.value, {
            "type": "market_tick",
            "symbol": symbol,
            "price": price,
            "change_pct": change_pct,
        })

    @property
    def total_connections(self) -> int:
        seen: set[str] = set()
        for conns in self._connections.values():
            seen.update(conns.keys())
        return len(seen)

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_connections": self.total_connections,
            "channels": {
                channel: len(conns)
                for channel, conns in self._connections.items()
            },
        }


# ── Module singleton ──────────────────────────────────────────────────────────

_ws_manager: ConnectionManager | None = None


def get_ws_manager() -> ConnectionManager:
    global _ws_manager  # noqa: PLW0603
    if _ws_manager is None:
        _ws_manager = ConnectionManager()
    return _ws_manager
