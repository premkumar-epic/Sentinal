import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Tuple

from config import load_config, ZoneConfig
from backend.services.video_service import video_manager

router = APIRouter()

class ZonePayload(BaseModel):
    id: str
    label: str
    polygon: List[Tuple[float, float]]

@router.get("/zones")
async def list_zones() -> List[dict]:
    """Return configured active zones."""
    cfg = load_config()
    return [{"id": z.id, "label": z.label, "polygon": z.polygon} for z in cfg.zones]

@router.post("/zones")
async def update_zones(payload: List[ZonePayload]) -> dict:
    """Overwrite zones.json and hot-reload running pipelines."""
    try:
        zones_file = Path("zones.json").resolve()
        data = [z.model_dump() for z in payload]
        with open(zones_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        # Convert to config objects and push to running pipelines
        configs = [ZoneConfig(id=z.id, label=z.label, polygon=z.polygon) for z in payload]
        video_manager.hot_reload_zones(configs)
        
        return {"status": "success", "message": "Zones updated and hot-reloaded"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
