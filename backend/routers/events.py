from fastapi import APIRouter
from typing import List

from backend.models.event import EventResponse
from backend.services.db_service import get_recent_events

router = APIRouter()

@router.get("/events", response_model=List[EventResponse])
async def list_events(limit: int = 50):
    """Return the most recent intrusion events from PostgreSQL."""
    return get_recent_events(limit=limit)
