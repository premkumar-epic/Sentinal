"""
SENTINAL v2 — FastAPI stats endpoint.

Provides system-wide statistics: event counts by type/camera/zone, active cameras.
"""

import logging
from typing import Optional

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

    # Query detailed stats from backend
    detailed_stats = await db.get_detailed_stats()

    return StatsResponse(
        total_events=base_stats["total_events"],
        events_today=base_stats["events_today"],
        active_cameras=active_cameras_count,
        events_by_type=detailed_stats["events_by_type"],
        events_by_camera=detailed_stats["events_by_camera"],
        top_zones=detailed_stats["top_zones"],
    )
