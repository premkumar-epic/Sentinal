"""
SENTINAL v2 — API Router: /api/zones
Zone CRUD — all mutations write to DB and zones.json, then hot-reload ZoneManager.
Uses the storage facade (supports both SQLite and PostgreSQL).
"""

import json
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from engine.storage.db import get_zones, get_zone_by_id, upsert_zone, delete_zone as db_delete_zone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/zones", tags=["zones"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ZoneCreate(BaseModel):
    label: str
    cam_id: str
    polygon: list[list[float]]  # [[x,y], ...]
    color: str = Field(default="#FF0000")


class ZoneUpdate(BaseModel):
    label: Optional[str] = None
    polygon: Optional[list[list[float]]] = None
    color: Optional[str] = None
    active: Optional[bool] = None


class ZoneResponse(BaseModel):
    zone_id: str
    label: str
    cam_id: str
    polygon: list[list[float]]
    color: str
    active: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_zone_manager():
    """Return the process-wide ZoneManager singleton."""
    from engine.zones.manager import ZoneManager
    return ZoneManager.get_instance()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ZoneResponse])
async def list_zones(cam_id: Optional[str] = Query(default=None)):
    """Return all zones, optionally filtered by cam_id."""
    rows = await get_zones(cam_id=cam_id)
    return [ZoneResponse(**row) for row in rows]


@router.post("", response_model=ZoneResponse, status_code=201)
async def create_zone(body: ZoneCreate):
    """Create a new zone, persist to DB and zones.json, hot-reload ZoneManager."""
    zone_id = str(uuid.uuid4())
    polygon_json = json.dumps(body.polygon)

    await upsert_zone(zone_id, body.label, body.cam_id, polygon_json, body.color, 1)

    # Sync zones.json via ZoneManager
    from engine.zones.manager import Zone
    zm = _get_zone_manager()
    zm.add_zone(Zone(
        zone_id=zone_id,
        label=body.label,
        cam_id=body.cam_id,
        polygon=[tuple(p) for p in body.polygon],
        color=body.color,
        active=True,
    ))
    zm.reload()

    return ZoneResponse(
        zone_id=zone_id,
        label=body.label,
        cam_id=body.cam_id,
        polygon=body.polygon,
        color=body.color,
        active=True,
    )


@router.put("/{zone_id}", response_model=ZoneResponse)
async def update_zone(zone_id: str, body: ZoneUpdate):
    """Update an existing zone by zone_id. Returns 404 if not found."""
    existing = await get_zone_by_id(zone_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    new_label = body.label if body.label is not None else existing["label"]
    new_polygon_raw = body.polygon if body.polygon is not None else existing["polygon"]
    new_color = body.color if body.color is not None else existing["color"]
    new_active = int(body.active) if body.active is not None else int(existing["active"])

    await upsert_zone(zone_id, new_label, existing["cam_id"], json.dumps(new_polygon_raw), new_color, new_active)

    # Sync zones.json
    from engine.zones.manager import Zone
    zm = _get_zone_manager()
    zm.add_zone(Zone(
        zone_id=zone_id,
        label=new_label,
        cam_id=existing["cam_id"],
        polygon=[tuple(p) for p in new_polygon_raw],
        color=new_color,
        active=bool(new_active),
    ))
    zm.reload()

    return ZoneResponse(
        zone_id=zone_id,
        label=new_label,
        cam_id=existing["cam_id"],
        polygon=new_polygon_raw,
        color=new_color,
        active=bool(new_active),
    )


@router.delete("/{zone_id}", status_code=204)
async def delete_zone(zone_id: str):
    """Delete a zone by zone_id. Returns 404 if not found."""
    deleted = await db_delete_zone(zone_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    zm = _get_zone_manager()
    zm.remove_zone(zone_id)
    zm.reload()
