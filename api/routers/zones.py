"""
SENTINAL v2 — API Router: /api/zones
Zone CRUD — all mutations write to DB and zones.json, then hot-reload ZoneManager.
"""

import json
import uuid
import logging
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from engine.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/zones", tags=["zones"])

# Derive DB path from settings (same pattern as db.py)
_DB_PATH: str = settings.db_url.replace("sqlite:///", "")


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


def _row_to_response(row: dict) -> ZoneResponse:
    polygon = json.loads(row["polygon"]) if isinstance(row["polygon"], str) else row["polygon"]
    return ZoneResponse(
        zone_id=row["zone_id"],
        label=row["label"],
        cam_id=row["cam_id"],
        polygon=polygon,
        color=row["color"],
        active=bool(row["active"]),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ZoneResponse])
async def list_zones(cam_id: Optional[str] = Query(default=None)):
    """Return all zones, optionally filtered by cam_id."""
    query = "SELECT zone_id, label, cam_id, polygon, color, active FROM zones"
    params: list = []
    if cam_id:
        query += " WHERE cam_id = ?"
        params.append(cam_id)

    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

    return [_row_to_response(dict(row)) for row in rows]


@router.post("", response_model=ZoneResponse, status_code=201)
async def create_zone(body: ZoneCreate):
    """Create a new zone, persist to DB and zones.json, hot-reload ZoneManager."""
    zone_id = str(uuid.uuid4())
    polygon_json = json.dumps(body.polygon)

    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT INTO zones (zone_id, label, cam_id, polygon, color, active) VALUES (?, ?, ?, ?, ?, 1)",
            (zone_id, body.label, body.cam_id, polygon_json, body.color),
        )
        await db.commit()

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
    # Fetch existing
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT zone_id, label, cam_id, polygon, color, active FROM zones WHERE zone_id = ?",
            (zone_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    existing = dict(row)
    new_label = body.label if body.label is not None else existing["label"]
    new_polygon_raw = body.polygon if body.polygon is not None else json.loads(existing["polygon"])
    new_color = body.color if body.color is not None else existing["color"]
    new_active = int(body.active) if body.active is not None else existing["active"]

    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "UPDATE zones SET label=?, polygon=?, color=?, active=? WHERE zone_id=?",
            (new_label, json.dumps(new_polygon_raw), new_color, new_active, zone_id),
        )
        await db.commit()

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
    async with aiosqlite.connect(_DB_PATH) as db:
        async with db.execute("SELECT zone_id FROM zones WHERE zone_id = ?", (zone_id,)) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")
        await db.execute("DELETE FROM zones WHERE zone_id = ?", (zone_id,))
        await db.commit()

    zm = _get_zone_manager()
    zm.remove_zone(zone_id)
    zm.reload()
