"""
WebSocket endpoint for real-time alert event broadcasting.
AlertManager calls broadcast() to push events to all connected clients.
"""
from __future__ import annotations

import asyncio
import json
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_clients: Set[WebSocket] = set()


async def broadcast(event: dict) -> None:
    """Push an alert event dict to every connected WebSocket client."""
    if not _clients:
        return
    message = json.dumps(event)
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(message)
        except Exception:  # noqa: BLE001
            dead.add(ws)
    _clients.difference_update(dead)


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    """WebSocket endpoint — clients connect here to receive live alert events."""
    await websocket.accept()
    _clients.add(websocket)
    try:
        while True:
            # Keep connection alive; server pushes via broadcast()
            await asyncio.sleep(30)
            await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
