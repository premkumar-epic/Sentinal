from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class EventResponse(BaseModel):
    id: int
    camera_id: str
    object_id: int
    zone: str
    timestamp: datetime
    snapshot_path: Optional[str] = None
