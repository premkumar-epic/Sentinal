"""
SENTINAL v2 — Storage: postgres.py
PostgreSQL implementation of the database backend using asyncpg.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict

from .base import DatabaseBackend

logger = logging.getLogger(__name__)


class PostgresBackend(DatabaseBackend):
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool = None

    async def initialize(self) -> None:
        try:
            import asyncpg
        except ImportError as e:
            raise RuntimeError(
                "PostgreSQL backend selected but asyncpg is not installed. "
                "Install with: pip install asyncpg"
            ) from e

        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.db_url,
                min_size=2,
                max_size=10,
            )
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id            TEXT PRIMARY KEY,
                        alert_type    TEXT NOT NULL,
                        cam_id        TEXT NOT NULL,
                        zone_id       TEXT,
                        track_ids     TEXT,
                        global_ids    TEXT,
                        name          TEXT,
                        confidence    REAL,
                        timestamp     TEXT NOT NULL,
                        snapshot_path TEXT,
                        metadata      TEXT
                    );
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS identities (
                        global_id      TEXT PRIMARY KEY,
                        name           TEXT,
                        embedding      BYTEA,
                        enrolled_at    TEXT,
                        last_seen      TEXT,
                        last_cam       TEXT,
                        sighting_count INTEGER DEFAULT 0
                    );
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS cameras (
                        cam_id   TEXT PRIMARY KEY,
                        url      TEXT NOT NULL,
                        label    TEXT,
                        active   INTEGER DEFAULT 1,
                        added_at TEXT
                    );
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zones (
                        zone_id TEXT PRIMARY KEY,
                        label   TEXT NOT NULL,
                        cam_id  TEXT NOT NULL,
                        polygon TEXT NOT NULL,
                        color   TEXT DEFAULT '#FF0000',
                        active  INTEGER DEFAULT 1
                    );
                """)
            logger.info("PostgreSQL database initialised — dsn=%s", self.db_url)
        except Exception as e:
            logger.error("Failed to initialize PostgreSQL database: %s", e)
            raise

    async def insert_event(self, alert: object) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO events
                    (id, alert_type, cam_id, zone_id, track_ids, global_ids,
                     name, confidence, timestamp, snapshot_path, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO UPDATE SET
                    alert_type = EXCLUDED.alert_type,
                    cam_id = EXCLUDED.cam_id,
                    zone_id = EXCLUDED.zone_id,
                    track_ids = EXCLUDED.track_ids,
                    global_ids = EXCLUDED.global_ids,
                    name = EXCLUDED.name,
                    confidence = EXCLUDED.confidence,
                    timestamp = EXCLUDED.timestamp,
                    snapshot_path = EXCLUDED.snapshot_path,
                    metadata = EXCLUDED.metadata
                """,
                alert.alert_id,
                str(alert.alert_type.value if hasattr(alert.alert_type, "value") else alert.alert_type),
                alert.cam_id,
                alert.zone_id,
                json.dumps(alert.track_ids),
                json.dumps(alert.global_ids),
                alert.name,
                alert.confidence,
                alert.timestamp.isoformat() if isinstance(alert.timestamp, datetime) else alert.timestamp,
                alert.snapshot_path,
                json.dumps(alert.metadata) if alert.metadata else None,
            )

    async def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        cam_id: Optional[str] = None,
        alert_type: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict]:
        conditions: list[str] = []
        params: list = []

        if cam_id:
            param_idx = len(params) + 1
            conditions.append(f"cam_id = ${param_idx}")
            params.append(cam_id)
        if alert_type:
            param_idx = len(params) + 1
            conditions.append(f"alert_type = ${param_idx}")
            params.append(alert_type)
        if since:
            param_idx = len(params) + 1
            conditions.append(f"timestamp >= ${param_idx}")
            params.append(since.isoformat())

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        limit_idx = len(params) + 1
        offset_idx = len(params) + 2
        query = f"""
            SELECT id, alert_type, cam_id, zone_id, track_ids, global_ids,
                   name, confidence, timestamp, snapshot_path, metadata
            FROM events
            {where}
            ORDER BY timestamp DESC
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """
        params.extend([limit, offset])

        result: List[Dict] = []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        for row in rows:
            d = dict(row)
            d["track_ids"] = json.loads(d["track_ids"]) if d["track_ids"] else []
            d["global_ids"] = json.loads(d["global_ids"]) if d["global_ids"] else []
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            result.append(d)
        return result

    async def get_identities(self) -> List[Dict]:
        query = "SELECT global_id, name, embedding, enrolled_at, last_seen, last_cam, sighting_count FROM identities"
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    async def upsert_identity(
        self,
        global_id: str,
        name: str,
        embedding: bytes,
        last_cam: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO identities (global_id, name, embedding, enrolled_at, last_seen, last_cam, sighting_count)
                VALUES ($1, $2, $3, $4, $5, $6, 1)
                ON CONFLICT (global_id) DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, identities.name),
                    embedding = EXCLUDED.embedding,
                    enrolled_at = COALESCE(identities.enrolled_at, EXCLUDED.enrolled_at),
                    last_seen = EXCLUDED.last_seen,
                    last_cam = EXCLUDED.last_cam,
                    sighting_count = identities.sighting_count + 1
                """,
                global_id,
                name,
                embedding,
                now,
                now,
                last_cam,
            )

    async def update_identity_name(self, global_id: str, name: str) -> bool:
        async with self.pool.acquire() as conn:
            status = await conn.execute(
                "UPDATE identities SET name = $1 WHERE global_id = $2",
                name,
                global_id,
            )
        return "1" in status

    async def delete_identity(self, global_id: str) -> bool:
        async with self.pool.acquire() as conn:
            status = await conn.execute(
                "DELETE FROM identities WHERE global_id = $1",
                global_id,
            )
        return "1" in status

    async def delete_all_events(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM events")

    async def get_stats(self) -> Dict:
        async with self.pool.acquire() as conn:
            # Total events
            total_events = await conn.fetchval("SELECT COUNT(*) FROM events") or 0

            # Events today
            today = datetime.now(timezone.utc).date().isoformat()
            events_today = await conn.fetchval(
                "SELECT COUNT(*) FROM events WHERE timestamp >= $1",
                today,
            ) or 0

            # Most active camera
            most_active_row = await conn.fetchrow(
                "SELECT cam_id FROM events GROUP BY cam_id ORDER BY COUNT(*) DESC LIMIT 1"
            )
            most_active_camera = most_active_row["cam_id"] if most_active_row else None

            # Active cameras
            active_cameras = await conn.fetchval("SELECT COUNT(*) FROM cameras WHERE active = 1") or 0

            # Known identities
            known_identities = await conn.fetchval("SELECT COUNT(*) FROM identities") or 0

        return {
            "total_events": total_events,
            "events_today": events_today,
            "most_active_camera": most_active_camera,
            "active_cameras": active_cameras,
            "known_identities": known_identities,
        }

    async def get_detailed_stats(self) -> Dict:
        async with self.pool.acquire() as conn:
            # Events by type
            type_rows = await conn.fetch(
                "SELECT alert_type, COUNT(*) as cnt FROM events GROUP BY alert_type"
            )
            events_by_type = {row["alert_type"]: row["cnt"] for row in type_rows}

            # Events by camera
            cam_rows = await conn.fetch(
                "SELECT cam_id, COUNT(*) as cnt FROM events GROUP BY cam_id"
            )
            events_by_camera = {row["cam_id"]: row["cnt"] for row in cam_rows}

            # Top zones
            zone_rows = await conn.fetch(
                """
                SELECT zone_id, COUNT(*) as cnt FROM events
                WHERE zone_id IS NOT NULL
                GROUP BY zone_id
                ORDER BY cnt DESC
                LIMIT 5
                """
            )
            top_zones = [{"zone_id": row["zone_id"], "count": row["cnt"]} for row in zone_rows]

        return {
            "events_by_type": events_by_type,
            "events_by_camera": events_by_camera,
            "top_zones": top_zones,
        }
