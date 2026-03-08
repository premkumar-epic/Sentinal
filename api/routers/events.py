"""
SENTINAL v2 — API Router: /api/events + /api/snapshots
Event log (paginated, filterable) and snapshot file serving.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from engine.storage.db import get_events

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])


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


@router.get("/api/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str):
    """Return a single event by ID. 404 if not found."""
    # get_events doesn't filter by id; fetch with limit=1 offset trick won't work —
    # query directly via aiosqlite for a single row lookup.
    import aiosqlite
    import json
    from engine.config import settings

    db_path = settings.db_url.replace("sqlite:///", "")

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, alert_type, cam_id, zone_id, track_ids, global_ids, "
            "name, confidence, timestamp, snapshot_path, metadata "
            "FROM events WHERE id = ?",
            (event_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")

    d = dict(row)
    d["track_ids"] = json.loads(d["track_ids"]) if d["track_ids"] else []
    d["global_ids"] = json.loads(d["global_ids"]) if d["global_ids"] else []
    d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
    return d


@router.get("/api/snapshots/{path:path}")
async def serve_snapshot(path: str):
    """Serve a snapshot JPEG file by relative path. 404 if file not found."""
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Snapshot '{path}' not found.")
    return FileResponse(str(file_path), media_type="image/jpeg")
