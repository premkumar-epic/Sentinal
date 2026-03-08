"""
SENTINAL v2 — API Router: ws.py
WebSocket broadcaster for real-time JSON events (Phase 1–4).
Clients (dashboard) connect to /ws/live to receive alerts.
"""

import asyncio
import json
import logging
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket client disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, message: dict):
        """Send a JSON message to all connected clients."""
        if not self.active_connections:
            return

        message_str = json.dumps(message)
        disconnected_clients = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error("Failed to send WS message: %s", e)
                disconnected_clients.append(connection)

        for client in disconnected_clients:
            self.disconnect(client)


# Global manager instance
manager = ConnectionManager()


@router.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main real-time event stream.
    Dashboard connects here: ws://[host]:8000/ws/live
    """
    await manager.connect(websocket)
    try:
        # Keep connection open. We only send data, but must receive to detect disconnects.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect(websocket)


async def broadcast_event(event: dict):
    """Public helper to push an event to all connected clients."""
    await manager.broadcast(event)
