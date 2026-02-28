from fastapi import APIRouter
from typing import List, Dict, Any

from config import load_config

router = APIRouter()
cfg = load_config()

@router.get("/zones")
async def list_zones() -> List[Dict[str, Any]]:
    """Return configured active zones for the frontend to render the overlay."""
    zones = []
    for z in cfg.zones:
        zones.append({
            "id": z.id,
            "label": z.label,
            "polygon": z.polygon
        })
    return zones
