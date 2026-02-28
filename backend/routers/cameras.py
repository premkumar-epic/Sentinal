from fastapi import APIRouter
from typing import List, Dict, Any

from backend.services.video_service import video_manager

router = APIRouter()

@router.get("/cameras")
async def list_cameras() -> List[Dict[str, Any]]:
    """Return all currently active camera pipelines."""
    return [{"id": cam_id, "status": "active"} for cam_id in video_manager.pipelines.keys()]


@router.post("/cameras/{camera_id}/start")
async def start_camera(camera_id: str, video_path: str = None) -> Dict[str, str]:
    """Start a headless surveillance pipeline for a given camera ID."""
    success = video_manager.start_camera(camera_id, video_path)
    if success:
        return {"status": "started", "camera_id": camera_id}
    return {"status": "already_running_or_failed", "camera_id": camera_id}


@router.post("/cameras/{camera_id}/stop")
async def stop_camera(camera_id: str) -> Dict[str, str]:
    """Stop a specific camera pipeline."""
    success = video_manager.stop_camera(camera_id)
    if success:
        return {"status": "stopped", "camera_id": camera_id}
    return {"status": "not_running", "camera_id": camera_id}
