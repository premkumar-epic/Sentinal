"""
SENTINAL v2 — API Router: /api/events + /api/snapshots
Event log (paginated, filterable) and snapshot file serving.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.middleware.auth import get_current_user_from_query
from engine.storage.db import get_events, delete_all_events

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])

# Snapshot router — requires token via query parameter
# because browsers load <img src="..."> without Bearer headers.
snapshot_router = APIRouter(tags=["snapshots"])


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------

class EventResponse(BaseModel):
    id: str
    alert_type: str
    cam_id: str
    zone_id: Optional[str]
    track_ids: list
    global_ids: list
    name: Optional[str]
    confidence: Optional[float]
    timestamp: str
    snapshot_path: Optional[str]
    metadata: dict


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/api/events", response_model=list[EventResponse])
async def list_events(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    cam_id: Optional[str] = Query(default=None),
    alert_type: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None, description="ISO datetime string"),
):
    """Return paginated event log with optional filters."""
    since_dt: Optional[datetime] = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid 'since' datetime: {since!r}")

    rows = await get_events(
        limit=limit,
        offset=offset,
        cam_id=cam_id,
        alert_type=alert_type,
        since=since_dt,
    )
    return rows


@router.delete("/api/events")
async def clear_events():
    """Clear all records from the event log."""
    await delete_all_events()
    return {"status": "cleared", "message": "Event log has been purged"}


@router.get("/api/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str):
    """Return a single event by ID. 404 if not found."""
    from engine.storage.db import get_event_by_id
    row = await get_event_by_id(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
    return row


@snapshot_router.get("/api/snapshots/{path:path}")
async def serve_snapshot(path: str, _user: str = Depends(get_current_user_from_query)):
    """Serve a snapshot JPEG file by relative path. Requires token in query."""
    # Security: resolve path and ensure it stays within the snapshots directory
    from engine.config import settings as _settings
    snapshots_root = Path(_settings.snapshots_dir).resolve()
    file_path = (snapshots_root / path).resolve()

    # Prevent path traversal (e.g. ../../.env)
    if not str(file_path).startswith(str(snapshots_root)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Snapshot not found.")
    if not file_path.suffix.lower() in (".jpg", ".jpeg", ".png"):
        raise HTTPException(status_code=403, detail="Invalid file type")
    return FileResponse(str(file_path), media_type="image/jpeg")
