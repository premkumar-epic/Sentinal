"""
SENTINAL v2 — API Router: ws.py
WebSocket broadcaster for real-time JSON events (Phase 1–4).
Clients (dashboard) connect to /ws/live to receive alerts.
"""

import asyncio
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError
from engine.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
            count = len(self.active_connections)
        logger.info("WebSocket client connected. Total: %d", count)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                count = len(self.active_connections)
                logger.info("WebSocket client disconnected. Total: %d", count)

    async def broadcast(self, message: dict):
        """Send a JSON message to all connected clients."""
        async with self._lock:
            if not self.active_connections:
                return
            connections = list(self.active_connections)

        message_str = json.dumps(message)
        disconnected_clients = []

        for connection in connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error("Failed to send WS message: %s", e)
                disconnected_clients.append(connection)

        for client in disconnected_clients:
            await self.disconnect(client)


# Global manager instance
manager = ConnectionManager()


@router.websocket("/live")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(default=None)):
    """
    Main real-time event stream.
    Dashboard connects here: ws://[host]:8000/ws/live?token=<jwt>
    """
    if not token:
        logger.warning("WS rejected: missing token")
        await websocket.close(code=4001)
        return

    try:
        # Validate token
        jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except JWTError:
        logger.warning("WS rejected: invalid token")
        await websocket.close(code=4001)
        return

    await manager.connect(websocket)
    try:
        # Keep connection open. We only send data, but must receive to detect disconnects.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        await manager.disconnect(websocket)


async def broadcast_event(event: dict):
    """Public helper to push an event to all connected clients."""
    await manager.broadcast(event)
