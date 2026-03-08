"""
SENTINAL v2 — API Router: cameras.py

POST   /api/cameras              — add a camera and start its pipeline
DELETE /api/cameras/{cam_id}     — remove camera and stop its pipeline
GET    /api/cameras              — list all cameras with status
PATCH  /api/cameras/{cam_id}     — update camera label, url, or active flag
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CameraAddRequest(BaseModel):
    cam_id: str = Field(..., description="Unique camera identifier, e.g. 'cam_0'")
    url: str = Field(..., description="Stream URL (HTTP, RTSP, or device index as string)")
    label: Optional[str] = Field(None, description="Human-readable name for the camera")


class CameraPatchRequest(BaseModel):
    url: Optional[str] = None
    label: Optional[str] = None
    active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/cameras", status_code=201)
async def add_camera(body: CameraAddRequest) -> dict:
    """Start a new camera pipeline and persist it."""
    from api.services.camera_service import camera_service  # lazy — avoids circular import

    existing = camera_service.get_camera_info(body.cam_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Camera '{body.cam_id}' already exists.")

    camera_service.add_camera(body.cam_id, body.url, body.label)
    logger.info("Camera added: cam_id=%s url=%s", body.cam_id, body.url)
    return {"cam_id": body.cam_id, "url": body.url, "label": body.label, "status": "started"}


@router.delete("/cameras/{cam_id}", status_code=200)
async def remove_camera(cam_id: str) -> dict:
    """Stop and remove a camera pipeline."""
    from api.services.camera_service import camera_service

    if camera_service.get_camera_info(cam_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera '{cam_id}' not found.")

    camera_service.remove_camera(cam_id)
    logger.info("Camera removed: cam_id=%s", cam_id)
    return {"cam_id": cam_id, "status": "removed"}


@router.get("/cameras")
async def list_cameras() -> list[dict]:
    """Return all registered cameras with their current status."""
    from api.services.camera_service import camera_service

    return camera_service.list_cameras()


@router.patch("/cameras/{cam_id}")
async def patch_camera(cam_id: str, body: CameraPatchRequest) -> dict:
    """Update camera metadata or restart with a new URL."""
    from api.services.camera_service import camera_service

    info = camera_service.get_camera_info(cam_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Camera '{cam_id}' not found.")

    camera_service.update_camera(cam_id, url=body.url, label=body.label, active=body.active)
    logger.info("Camera patched: cam_id=%s patch=%s", cam_id, body.model_dump(exclude_none=True))
    return camera_service.get_camera_info(cam_id)
