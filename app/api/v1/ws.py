"""WebSocket endpoint for real-time updates."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.websocket import WSChannel, get_ws_manager
from app.schemas.backtest import WSStatsResponse

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    channels: str | None = Query(default=None, description="Comma-separated channels: gti,signals,events,market,alerts,all"),
) -> None:
    """WebSocket endpoint for real-time data.

    Subscribe to channels via query param, e.g.:
        ws://host/ws?channels=gti,signals,events
    """
    manager = get_ws_manager()

    # Parse channels
    if channels:
        channel_list = [c.strip() for c in channels.split(",") if c.strip()]
    else:
        channel_list = [WSChannel.ALL.value]

    conn_id = await manager.connect(websocket, channel_list)

    try:
        while True:
            # Keep connection alive; handle client messages
            data = await websocket.receive_json()

            # Client can dynamically subscribe/unsubscribe
            msg_type = data.get("type")
            if msg_type == "subscribe":
                new_channels = data.get("channels", [])
                async with manager._lock:
                    for ch in new_channels:
                        manager._connections[ch][conn_id] = websocket
                await websocket.send_json({
                    "type": "subscribed",
                    "channels": new_channels,
                })
            elif msg_type == "unsubscribe":
                rm_channels = data.get("channels", [])
                async with manager._lock:
                    for ch in rm_channels:
                        manager._connections[ch].pop(conn_id, None)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "channels": rm_channels,
                })
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        await manager.disconnect(conn_id)
    except Exception:
        await manager.disconnect(conn_id)


@router.get("/ws/stats", response_model=WSStatsResponse, tags=["meta"])
async def ws_stats() -> WSStatsResponse:
    """Get current WebSocket connection statistics."""
    manager = get_ws_manager()
    stats = manager.get_stats()
    return WSStatsResponse(**stats)
