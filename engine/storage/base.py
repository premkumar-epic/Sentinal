"""
SENTINAL v2 — Storage: base.py
Abstract base class for database backends.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict


class DatabaseBackend(ABC):
    """Unified interface for all storage operations."""

    @abstractmethod
    async def initialize(self) -> None:
        """Create tables and setup connection pools."""
        pass

    @abstractmethod
    async def insert_event(self, alert: object) -> None:
        """Persist an Alert to the events table."""
        pass

    @abstractmethod
    async def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        cam_id: Optional[str] = None,
        alert_type: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict]:
        """Return paginated event rows as dicts."""
        pass

    @abstractmethod
    async def get_identities(self) -> List[Dict]:
        """Return all known identities."""
        pass

    @abstractmethod
    async def upsert_identity(
        self,
        global_id: str,
        name: str,
        embedding: bytes,
        last_cam: Optional[str] = None,
    ) -> None:
        """Insert or update a known identity."""
        pass

    @abstractmethod
    async def update_identity_name(self, global_id: str, name: str) -> bool:
        """Update display name for an identity."""
        pass

    @abstractmethod
    async def delete_identity(self, global_id: str) -> bool:
        """Delete an identity."""
        pass

    @abstractmethod
    async def delete_all_events(self) -> None:
        """Clear the events table."""
        pass

    @abstractmethod
    async def get_stats(self) -> Dict:
        """Return summary statistics."""
        pass

    @abstractmethod
    async def get_detailed_stats(self) -> Dict:
        """Return detailed statistics (by type, camera, zone)."""
        pass
