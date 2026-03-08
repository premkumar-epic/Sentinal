"""
SENTINAL v2 — FastAPI stats endpoint.

Provides system-wide statistics: event counts by type/camera/zone, active cameras.
"""

import logging
from typing import Optional

import aiosqlite
from fastapi import APIRouter
from pydantic import BaseModel

from engine.storage import db

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Model
# ============================================================================


class StatsResponse(BaseModel):
    """Response model for GET /api/stats endpoint."""

    total_events: int
    """Total number of events ever recorded."""

    events_today: int
    """Number of events recorded since 00:00 UTC today."""

    active_cameras: int
    """Number of cameras currently alive (running pipelines)."""

    events_by_type: dict[str, int]
    """Count of events grouped by alert_type (intrusion, weapon, etc.)."""

    events_by_camera: dict[str, int]
    """Count of events grouped by cam_id."""

    top_zones: list[dict]
    """Top 5 zones by event count. Each dict has {zone_id, count}."""


# ============================================================================
# Endpoint
# ============================================================================


@router.get("/stats", response_model=StatsResponse, tags=["stats"])
async def get_stats_endpoint() -> StatsResponse:
    """
    Get system statistics: event counts, active cameras, type/camera/zone breakdowns.

    Returns aggregated stats across all cameras and zones:
    - total_events: lifetime count
    - events_today: events since 00:00 UTC today
    - active_cameras: count of pipelines with alive=True
    - events_by_type: {alert_type: count} dict
    - events_by_camera: {cam_id: count} dict
    - top_zones: list of {zone_id, count} for top 5 zones (skip NULL zones)
    """
    # Get base stats from db (total_events, events_today, most_active_camera, active_cameras, known_identities)
    base_stats = await db.get_stats()

    # Override active_cameras with live pipeline count from camera_service
    # Lazy import to avoid circular imports
    from api.services.camera_service import camera_service

    cameras = camera_service.list_cameras()
    active_cameras_count = sum(1 for c in cameras if c.get("alive", False))

    # Query events_by_type, events_by_camera, top_zones
    events_by_type = await _query_events_by_type()
    events_by_camera = await _query_events_by_camera()
    top_zones = await _query_top_zones()

    return StatsResponse(
        total_events=base_stats["total_events"],
        events_today=base_stats["events_today"],
        active_cameras=active_cameras_count,
        events_by_type=events_by_type,
        events_by_camera=events_by_camera,
        top_zones=top_zones,
    )


# ============================================================================
# Helper Functions
# ============================================================================


async def _query_events_by_type() -> dict[str, int]:
    """
    Query events table, group by alert_type.

    Returns dict mapping alert_type string to event count.
    """
    if db._USE_PG:
        # PostgreSQL path
        async with db._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT alert_type, COUNT(*) as cnt FROM events GROUP BY alert_type"
            )
        return {row["alert_type"]: row["cnt"] for row in rows}
    else:
        # SQLite path
        async with aiosqlite.connect(db._DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT alert_type, COUNT(*) as cnt FROM events GROUP BY alert_type"
            ) as cursor:
                rows = await cursor.fetchall()
        return {row["alert_type"]: row["cnt"] for row in rows}


async def _query_events_by_camera() -> dict[str, int]:
    """
    Query events table, group by cam_id.

    Returns dict mapping cam_id string to event count.
    """
    if db._USE_PG:
        # PostgreSQL path
        async with db._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT cam_id, COUNT(*) as cnt FROM events GROUP BY cam_id"
            )
        return {row["cam_id"]: row["cnt"] for row in rows}
    else:
        # SQLite path
        async with aiosqlite.connect(db._DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT cam_id, COUNT(*) as cnt FROM events GROUP BY cam_id"
            ) as cursor:
                rows = await cursor.fetchall()
        return {row["cam_id"]: row["cnt"] for row in rows}


async def _query_top_zones() -> list[dict]:
    """
    Query events table, group by zone_id, order by count DESC, limit 5.

    Skips rows where zone_id is NULL (zone-less events).

    Returns list of dicts: [{zone_id: str, count: int}, ...]
    """
    if db._USE_PG:
        # PostgreSQL path
        async with db._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT zone_id, COUNT(*) as cnt FROM events
                WHERE zone_id IS NOT NULL
                GROUP BY zone_id
                ORDER BY cnt DESC
                LIMIT 5
                """
            )
        return [{"zone_id": row["zone_id"], "count": row["cnt"]} for row in rows]
    else:
        # SQLite path
        async with aiosqlite.connect(db._DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                """
                SELECT zone_id, COUNT(*) as cnt FROM events
                WHERE zone_id IS NOT NULL
                GROUP BY zone_id
                ORDER BY cnt DESC
                LIMIT 5
                """
            ) as cursor:
                rows = await cursor.fetchall()
        return [{"zone_id": row["zone_id"], "count": row["cnt"]} for row in rows]
