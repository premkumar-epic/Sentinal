"""
SENTINAL v2 — DB Service
Thin re-export of engine.storage.db public interface for use by API routers.
"""

from engine.storage.db import (  # noqa: F401
    get_events,
    insert_event,
    get_identities,
    upsert_identity,
    get_stats,
)
