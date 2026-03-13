"""
SENTINAL v2 — API Router: stream.py

GET /api/stream/{cam_id}
    Returns a multipart/x-mixed-replace MJPEG stream for the given camera.
    Sourced from the camera's MJPEGBuffer.frame_generator().
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.middleware.auth import get_current_user_from_query

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stream/{cam_id}")
async def mjpeg_stream(cam_id: str, _user: str = Depends(get_current_user_from_query)) -> StreamingResponse:
    """
    Stream live MJPEG frames for a given camera.

    The browser can consume this directly via:
        <img src="/api/stream/{cam_id}?token={JWT}" />
    """
    from api.services.camera_service import camera_service  # lazy to avoid circular import

    mjpeg_buffer = camera_service.get_mjpeg_buffer(cam_id)
    if mjpeg_buffer is None:
        raise HTTPException(status_code=404, detail=f"Camera '{cam_id}' not found or not running.")

    logger.info("MJPEG stream requested for cam_id=%s", cam_id)

    return StreamingResponse(
        mjpeg_buffer.frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
