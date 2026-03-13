"""
SENTINAL v2 — API Integration Tests

Tests all protected FastAPI routes using httpx.AsyncClient with ASGI transport.
No real DB or camera pipelines are started — all are patched in conftest.py.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from api.main import app
from engine.config import settings


BASE_URL = "http://test"


@pytest_asyncio.fixture(scope="session", autouse=True)
def disable_rate_limiting():
    """Disable rate limiting for the test session."""
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False
    yield
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = True


@pytest_asyncio.fixture
async def client():
    """Async httpx client wired to the FastAPI ASGI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def auth_headers() -> dict:
    """Login once for the whole session to avoid rate limiting."""
    # We need a temporary client here since the main client fixture is function scoped
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as ac:
        resp = await ac.post(
            "/api/auth/login",
            data={"username": settings.auth_username, "password": "sentinal"},
        )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

async def test_login_success(client: AsyncClient) -> None:
    """POST /api/auth/login with valid credentials returns 200 + access_token."""
    resp = await client.post(
        "/api/auth/login",
        data={"username": settings.auth_username, "password": "sentinal"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_failure(client: AsyncClient) -> None:
    """POST /api/auth/login with wrong password returns 401."""
    resp = await client.post(
        "/api/auth/login",
        data={"username": settings.auth_username, "password": "wrongpassword"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Protected route tests
# ---------------------------------------------------------------------------

async def test_stats_requires_auth(client: AsyncClient) -> None:
    """GET /api/stats without token returns 401."""
    resp = await client.get("/api/stats")
    assert resp.status_code == 401


async def test_stats_with_auth(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/stats with valid token returns 200 with active_cameras key."""
    mock_stats = {
        "total_events": 0,
        "events_today": 0,
        "most_active_camera": None,
        "active_cameras": 0,
        "known_identities": 0,
    }
    mock_detailed = {
        "events_by_type": {},
        "events_by_camera": {},
        "top_zones": [],
    }
    with patch("engine.storage.db.get_stats", new_callable=AsyncMock, return_value=mock_stats), \
         patch("engine.storage.db.get_detailed_stats", new_callable=AsyncMock, return_value=mock_detailed):
        resp = await client.get("/api/stats", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "active_cameras" in body


async def test_events_with_auth(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/events with valid token returns 200."""
    with patch("api.routers.events.get_events", new_callable=AsyncMock, return_value=[]):
        resp = await client.get("/api/events", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_cameras_with_auth(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/cameras with valid token returns 200."""
    resp = await client.get("/api/cameras", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_zones_with_auth(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/zones with valid token returns 200."""
    with patch("engine.zones.manager.ZoneManager.get_zones_for_camera", return_value=[]):
        resp = await client.get("/api/zones", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_identities_with_auth(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/identities with valid token returns 200."""
    with patch("api.routers.identities.get_identities", new_callable=AsyncMock, return_value=[]):
        resp = await client.get("/api/identities", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_alerts_config_with_auth(client: AsyncClient, auth_headers: dict) -> None:
    """GET /api/alerts/config with valid token returns 200."""
    resp = await client.get("/api/alerts/config", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "email_enabled" in body
    assert "webhook_enabled" in body


async def test_add_camera_with_auth(client: AsyncClient, auth_headers: dict) -> None:
    """POST /api/cameras with valid token and payload returns 201."""
    with patch("api.services.camera_service.camera_service.add_camera", new_callable=MagicMock), \
         patch("api.services.camera_service.camera_service.get_camera_info", return_value=None):
        resp = await client.post(
            "/api/cameras",
            headers=auth_headers,
            json={"cam_id": "test_cam", "url": "http://localhost:4747/video", "label": "Test"},
        )
    assert resp.status_code == 201


async def test_delete_camera_with_auth(client: AsyncClient, auth_headers: dict) -> None:
    """DELETE /api/cameras/{cam_id} with valid token returns 200."""
    with patch("api.services.camera_service.camera_service.remove_camera", new_callable=MagicMock), \
         patch("api.services.camera_service.camera_service.get_camera_info", return_value={"cam_id": "test_cam"}):
        resp = await client.delete("/api/cameras/test_cam", headers=auth_headers)
    assert resp.status_code == 200
