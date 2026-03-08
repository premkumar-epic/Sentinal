"""
SENTINAL v2 — FastAPI application entry point.

Handles app lifecycle (DB init, camera restore, graceful shutdown),
CORS middleware, and router registration.
"""

import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engine.config import settings
from engine.storage.db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic for the FastAPI app."""
    # Ensure all required directories exist
    os.makedirs(settings.models_dir, exist_ok=True)
    os.makedirs(os.path.dirname(settings.snapshots_dir), exist_ok=True)
    os.makedirs(os.path.dirname(settings.zones_file), exist_ok=True)
    os.makedirs(settings.logs_dir, exist_ok=True)

    # Lazy import to avoid circular imports at module load time
    from api.services.camera_service import camera_service

    logger.info("SENTINAL v2 starting up…")
    await init_db()
    camera_service.restore_cameras()
    _load_startup_cameras(camera_service)
    logger.info("Startup complete.")

    yield

    logger.info("SENTINAL v2 shutting down…")
    camera_service.stop_all()
    logger.info("All camera pipelines stopped.")


def _load_startup_cameras(camera_service) -> None:
    """
    Parse settings.startup_cameras (JSON array) and auto-add any cameras
    not already registered by restore_cameras().  Logs and skips on errors.
    """
    raw = settings.startup_cameras.strip()
    if not raw:
        return

    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("STARTUP_CAMERAS parse error — skipping: %s", exc)
        return

    if not isinstance(entries, list):
        logger.warning("STARTUP_CAMERAS must be a JSON array — skipping")
        return

    existing = {c["cam_id"] for c in camera_service.list_cameras()}
    for entry in entries:
        cam_id = entry.get("cam_id", "").strip()
        url = entry.get("url", "").strip()
        label = entry.get("label", "").strip() or None
        if not cam_id or not url:
            logger.warning("STARTUP_CAMERAS: skipping entry missing cam_id or url: %s", entry)
            continue
        if cam_id in existing:
            logger.info("STARTUP_CAMERAS: '%s' already registered — skipping", cam_id)
            continue
        try:
            camera_service.add_camera(cam_id, url, label)
            logger.info("STARTUP_CAMERAS: auto-started camera '%s' (%s)", cam_id, url)
        except Exception as exc:
            logger.error("STARTUP_CAMERAS: failed to start '%s': %s", cam_id, exc)


app = FastAPI(
    title="SENTINAL v2",
    description="Zero-cloud on-premise AI video surveillance system.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://192.168.1.*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers — import here so they register after the app object is created.
# Each router module may also import camera_service lazily.
# ---------------------------------------------------------------------------
from api.routers import cameras, stream, ws, zones, events, identities, alerts, stats, auth  # noqa: E402
from api.middleware.auth import get_current_user  # noqa: E402

_auth_dep = [Depends(get_current_user)]

# Auth router — no token required (it IS the login endpoint)
app.include_router(auth.router)

# Protected routers — require valid Bearer JWT
app.include_router(cameras.router, prefix="/api", dependencies=_auth_dep)
app.include_router(zones.router, dependencies=_auth_dep)      # already has /api prefix
app.include_router(events.router, dependencies=_auth_dep)     # already has /api paths
app.include_router(identities.router, dependencies=_auth_dep) # already has /api/identities prefix
app.include_router(alerts.router, dependencies=_auth_dep)     # already has /api/alerts prefix
app.include_router(stats.router, prefix="/api", dependencies=_auth_dep)

# Unprotected routers — browsers cannot send Bearer headers on <img> or WS
app.include_router(stream.router, prefix="/api")  # MJPEG stream via <img src="...">
app.include_router(ws.router, prefix="/ws")       # WebSocket live feed
