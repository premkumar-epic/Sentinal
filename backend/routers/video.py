from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.services.video_service import video_manager
from config import load_config

router = APIRouter()
cfg = load_config()

@router.get("/stream/{camera_id}")
async def video_stream(camera_id: str):
    """Stream MJPEG video output from the surveillance pipeline."""
    if camera_id != cfg.alert.camera_id:
        raise HTTPException(status_code=404, detail="Camera ID not found")
        
    return StreamingResponse(
        video_manager.generate_mjpeg(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
