"""
SENTINAL v2 — WebSocket Authentication Tests

Tests JWT token validation on the /ws/live endpoint.
Uses starlette.testclient.TestClient for synchronous WebSocket testing.
"""

from datetime import datetime, timedelta, timezone
import pytest
from jose import jwt
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.main import app
from engine.config import settings


@pytest.fixture
def client():
    """Synchronous test client for WebSocket testing."""
    return TestClient(app)


@pytest.fixture
def valid_token():
    """Generate a valid JWT token."""
    payload = {
        "sub": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def test_ws_no_token(client: TestClient) -> None:
    """
    WebSocket connection without token query param should be rejected.
    Endpoint closes connection with code 4001.
    """
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/live") as ws:
            pass

    # Check that the close code is 4001 (custom close code for auth failure)
    assert exc_info.value.code == 4001


def test_ws_invalid_token(client: TestClient) -> None:
    """
    WebSocket connection with invalid token should be rejected.
    Endpoint closes connection with code 4001.
    """
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/live?token=badtoken") as ws:
            pass

    # Check that the close code is 4001 (JWT decode error)
    assert exc_info.value.code == 4001


def test_ws_valid_token(client: TestClient, valid_token: str) -> None:
    """
    WebSocket connection with valid JWT token should be accepted.
    Connection stays open and can receive/send messages.
    """
    with client.websocket_connect(f"/ws/live?token={valid_token}") as ws:
        # Connection is open — verify by checking that the context manager works
        # The endpoint keeps the connection open waiting for messages
        # We won't send anything, just verify we can connect and disconnect cleanly
        assert ws is not None
