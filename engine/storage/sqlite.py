"""
SENTINAL v2 — Storage: sqlite.py
SQLite implementation of the database backend.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict

import aiosqlite
from .base import DatabaseBackend

logger = logging.getLogger(__name__)


class SQLiteBackend(DatabaseBackend):
    def __init__(self, db_url: str):
        self.db_path = db_url.replace("sqlite:///", "")
        self.conn: Optional[aiosqlite.Connection] = None
        self.lock = asyncio.Lock()

    async def initialize(self) -> None:
        if self.db_path:
            try:
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            except Exception as e:
                logger.error("Failed to create database directory %s: %s", os.path.dirname(self.db_path), e)
                raise

        try:
            self.conn = await aiosqlite.connect(self.db_path, check_same_thread=False)
            await self.conn.execute("PRAGMA journal_mode=WAL")
            await self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.row_factory = aiosqlite.Row
            
            # DDL
            await self.conn.execute("""
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
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS identities (
                    global_id      TEXT PRIMARY KEY,
                    name           TEXT,
                    embedding      BLOB,
                    enrolled_at    TEXT,
                    last_seen      TEXT,
                    last_cam       TEXT,
                    sighting_count INTEGER DEFAULT 0
                );
            """)
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    cam_id   TEXT PRIMARY KEY,
                    url      TEXT NOT NULL,
                    label    TEXT,
                    active   INTEGER DEFAULT 1,
                    added_at TEXT
                );
            """)
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS zones (
                    zone_id TEXT PRIMARY KEY,
                    label   TEXT NOT NULL,
                    cam_id  TEXT NOT NULL,
                    polygon TEXT NOT NULL,
                    color   TEXT DEFAULT '#FF0000',
                    active  INTEGER DEFAULT 1
                );
            """)
            await self.conn.commit()
            logger.info("SQLite database initialised at %s", self.db_path)
        except Exception as e:
            logger.error("Failed to initialize SQLite database at %s: %s", self.db_path, e)
            raise

    async def insert_event(self, alert: object) -> None:
        async with self.lock:
            await self.conn.execute(
                """
                INSERT OR REPLACE INTO events
                    (id, alert_type, cam_id, zone_id, track_ids, global_ids,
                     name, confidence, timestamp, snapshot_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                ),
            )
            await self.conn.commit()

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
            conditions.append("cam_id = ?")
            params.append(cam_id)
        if alert_type:
            conditions.append("alert_type = ?")
            params.append(alert_type)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since.isoformat())

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"""
            SELECT id, alert_type, cam_id, zone_id, track_ids, global_ids,
                   name, confidence, timestamp, snapshot_path, metadata
            FROM events
            {where}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        result: List[Dict] = []
        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            d = dict(row)
            d["track_ids"] = json.loads(d["track_ids"]) if d["track_ids"] else []
            d["global_ids"] = json.loads(d["global_ids"]) if d["global_ids"] else []
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            result.append(d)
        return result

    async def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        async with self.conn.execute(
            "SELECT id, alert_type, cam_id, zone_id, track_ids, global_ids, "
            "name, confidence, timestamp, snapshot_path, metadata "
            "FROM events WHERE id = ?",
            (event_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["track_ids"] = json.loads(d["track_ids"]) if d["track_ids"] else []
        d["global_ids"] = json.loads(d["global_ids"]) if d["global_ids"] else []
        d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
        return d

    async def get_identities(self) -> List[Dict]:
        query = "SELECT global_id, name, embedding, enrolled_at, last_seen, last_cam, sighting_count FROM identities"
        async with self.conn.execute(query) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def upsert_identity(
        self,
        global_id: str,
        name: str,
        embedding: bytes,
        last_cam: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with self.lock:
            await self.conn.execute(
                """
                INSERT INTO identities (global_id, name, embedding, enrolled_at, last_seen, last_cam, sighting_count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(global_id) DO UPDATE SET
                    name = COALESCE(excluded.name, identities.name),
                    embedding = excluded.embedding,
                    enrolled_at = COALESCE(identities.enrolled_at, excluded.enrolled_at),
                    last_seen = excluded.last_seen,
                    last_cam = excluded.last_cam,
                    sighting_count = sighting_count + 1
                """,
                (global_id, name, embedding, now, now, last_cam),
            )
            await self.conn.commit()

    async def update_identity_name(self, global_id: str, name: str) -> bool:
        async with self.lock:
            cursor = await self.conn.execute(
                "UPDATE identities SET name = ? WHERE global_id = ?",
                (name, global_id),
            )
            await self.conn.commit()
            return cursor.rowcount > 0

    async def delete_identity(self, global_id: str) -> bool:
        async with self.lock:
            cursor = await self.conn.execute(
                "DELETE FROM identities WHERE global_id = ?",
                (global_id,),
            )
            await self.conn.commit()
            return cursor.rowcount > 0

    async def delete_all_events(self) -> None:
        async with self.lock:
            await self.conn.execute("DELETE FROM events")
            await self.conn.commit()

    async def get_stats(self) -> Dict:
        async with self.conn.execute("SELECT COUNT(*) AS total FROM events") as cur:
            total_events = (await cur.fetchone())["total"]

        today = datetime.now(timezone.utc).date().isoformat()
        async with self.conn.execute(
            "SELECT COUNT(*) AS cnt FROM events WHERE timestamp >= ?", (today,)
        ) as cur:
            events_today = (await cur.fetchone())["cnt"]

        async with self.conn.execute(
            "SELECT cam_id, COUNT(*) AS cnt FROM events GROUP BY cam_id ORDER BY cnt DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            most_active_camera = row["cam_id"] if row else None

        async with self.conn.execute("SELECT COUNT(*) AS cnt FROM cameras WHERE active = 1") as cur:
            active_cameras = (await cur.fetchone())["cnt"]

        async with self.conn.execute("SELECT COUNT(*) AS cnt FROM identities") as cur:
            known_identities = (await cur.fetchone())["cnt"]

        return {
            "total_events": total_events,
            "events_today": events_today,
            "most_active_camera": most_active_camera,
            "active_cameras": active_cameras,
            "known_identities": known_identities,
        }

    async def get_zones(self, cam_id: Optional[str] = None) -> List[Dict]:
        query = "SELECT zone_id, label, cam_id, polygon, color, active FROM zones"
        params: list = []
        if cam_id:
            query += " WHERE cam_id = ?"
            params.append(cam_id)
        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["polygon"] = json.loads(d["polygon"]) if isinstance(d["polygon"], str) else d["polygon"]
            d["active"] = bool(d["active"])
            result.append(d)
        return result

    async def get_zone_by_id(self, zone_id: str) -> Optional[Dict]:
        async with self.conn.execute(
            "SELECT zone_id, label, cam_id, polygon, color, active FROM zones WHERE zone_id = ?",
            (zone_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["polygon"] = json.loads(d["polygon"]) if isinstance(d["polygon"], str) else d["polygon"]
        d["active"] = bool(d["active"])
        return d

    async def upsert_zone(self, zone_id: str, label: str, cam_id: str, polygon: str, color: str, active: int) -> None:
        async with self.lock:
            await self.conn.execute(
                """INSERT INTO zones (zone_id, label, cam_id, polygon, color, active) VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(zone_id) DO UPDATE SET label=excluded.label, polygon=excluded.polygon, color=excluded.color, active=excluded.active""",
                (zone_id, label, cam_id, polygon, color, active),
            )
            await self.conn.commit()

    async def delete_zone(self, zone_id: str) -> bool:
        async with self.lock:
            cursor = await self.conn.execute("DELETE FROM zones WHERE zone_id = ?", (zone_id,))
            await self.conn.commit()
            return cursor.rowcount > 0

    async def get_detailed_stats(self) -> Dict:
        # Events by type
        async with self.conn.execute(
            "SELECT alert_type, COUNT(*) as cnt FROM events GROUP BY alert_type"
        ) as cursor:
            type_rows = await cursor.fetchall()
        events_by_type = {row["alert_type"]: row["cnt"] for row in type_rows}

        # Events by camera
        async with self.conn.execute(
            "SELECT cam_id, COUNT(*) as cnt FROM events GROUP BY cam_id"
        ) as cursor:
            cam_rows = await cursor.fetchall()
        events_by_camera = {row["cam_id"]: row["cnt"] for row in cam_rows}

        # Top zones
        async with self.conn.execute(
            """
            SELECT zone_id, COUNT(*) as cnt FROM events
            WHERE zone_id IS NOT NULL
            GROUP BY zone_id
            ORDER BY cnt DESC
            LIMIT 5
            """
        ) as cursor:
            zone_rows = await cursor.fetchall()
        top_zones = [{"zone_id": row["zone_id"], "count": row["cnt"]} for row in zone_rows]

        return {
            "events_by_type": events_by_type,
            "events_by_camera": events_by_camera,
            "top_zones": top_zones,
        }
