"""
SENTINAL v2 — Storage: db.py
Unified database facade. Orchestrates SQLite or PostgreSQL backends.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict

from engine.config import settings
from .base import DatabaseBackend
from .sqlite import SQLiteBackend
from .postgres import PostgresBackend

logger = logging.getLogger(__name__)

# Singleton backend instance
_backend: Optional[DatabaseBackend] = None


def _get_backend() -> DatabaseBackend:
    """Internal helper to get the initialized backend."""
    global _backend
    if _backend is None:
        # Auto-initialize if not already done (though init_db is the preferred entry point)
        # This handles cases where functions are called before init_db() in tests or scripts.
        if settings.db_url.startswith(("postgresql", "postgres")):
            _backend = PostgresBackend(settings.db_url)
        else:
            _backend = SQLiteBackend(settings.db_url)
    return _backend


async def init_db() -> None:
    """Initialize the database backend and create tables."""
    backend = _get_backend()
    await backend.initialize()


async def insert_event(alert: object) -> None:
    """Persist an Alert to the events table."""
    await _get_backend().insert_event(alert)


async def get_events(
    limit: int = 50,
    offset: int = 0,
    cam_id: Optional[str] = None,
    alert_type: Optional[str] = None,
    since: Optional[datetime] = None,
) -> List[Dict]:
    """Return paginated event rows as dicts."""
    return await _get_backend().get_events(limit, offset, cam_id, alert_type, since)


async def get_identities() -> List[Dict]:
    """Return all known identities."""
    return await _get_backend().get_identities()


async def upsert_identity(
    global_id: str,
    name: str,
    embedding: bytes,
    last_cam: Optional[str] = None,
) -> None:
    """Insert or update a known identity."""
    await _get_backend().upsert_identity(global_id, name, embedding, last_cam)


async def update_identity_name(global_id: str, name: str) -> bool:
    """Update display name for an identity."""
    return await _get_backend().update_identity_name(global_id, name)


async def delete_identity(global_id: str) -> bool:
    """Delete an identity."""
    return await _get_backend().delete_identity(global_id)


async def delete_all_events() -> None:
    """Clear the events table."""
    await _get_backend().delete_all_events()


async def get_stats() -> Dict:
    """Return summary statistics."""
    return await _get_backend().get_stats()


async def get_detailed_stats() -> Dict:
    """Return detailed statistics (by type, camera, zone)."""
    return await _get_backend().get_detailed_stats()
