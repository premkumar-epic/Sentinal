"""
SENTINAL v2 — Storage: db.py
Dual async database layer: SQLite via aiosqlite (Phase 1–4) + PostgreSQL via asyncpg (Phase 5+).
Implements a unified public interface so either backend can be selected via config.db_url.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

import aiosqlite

from engine.config import settings

logger = logging.getLogger(__name__)

# Backend detection at module level
_USE_PG: bool = settings.db_url.startswith(("postgresql", "postgres"))
_DB_PATH: str = "" if _USE_PG else settings.db_url.replace("sqlite:///", "")
_pool = None  # asyncpg pool — set by init_db() when PG backend active

# ============================================================================
# DDL Statements (shared schemas for both backends)
# ============================================================================

_CREATE_EVENTS = """
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
"""

_CREATE_IDENTITIES = """
CREATE TABLE IF NOT EXISTS identities (
    global_id      TEXT PRIMARY KEY,
    name           TEXT,
    embedding      BYTEA,
    enrolled_at    TEXT,
    last_seen      TEXT,
    last_cam       TEXT,
    sighting_count INTEGER DEFAULT 0
);
"""

_CREATE_CAMERAS = """
CREATE TABLE IF NOT EXISTS cameras (
    cam_id   TEXT PRIMARY KEY,
    url      TEXT NOT NULL,
    label    TEXT,
    active   INTEGER DEFAULT 1,
    added_at TEXT
);
"""

_CREATE_ZONES = """
CREATE TABLE IF NOT EXISTS zones (
    zone_id TEXT PRIMARY KEY,
    label   TEXT NOT NULL,
    cam_id  TEXT NOT NULL,
    polygon TEXT NOT NULL,
    color   TEXT DEFAULT '#FF0000',
    active  INTEGER DEFAULT 1
);
"""


# ============================================================================
# Initialization
# ============================================================================


async def init_db() -> None:
    """
    Create all tables if they don't exist. Called once at app startup.
    Detects backend (SQLite or PostgreSQL) and initializes accordingly.
    """
    global _pool

    if _USE_PG:
        # PostgreSQL backend
        try:
            import asyncpg
        except ImportError as e:
            raise RuntimeError(
                "PostgreSQL backend selected (db_url starts with 'postgresql://' or 'postgres://') "
                "but asyncpg is not installed. Install with: pip install asyncpg"
            ) from e

        try:
            _pool = await asyncpg.create_pool(
                dsn=settings.db_url,
                min_size=2,
                max_size=10,
            )
            async with _pool.acquire() as conn:
                await conn.execute(_CREATE_EVENTS)
                await conn.execute(_CREATE_IDENTITIES)
                await conn.execute(_CREATE_CAMERAS)
                await conn.execute(_CREATE_ZONES)
            logger.info("Database initialised — backend=PostgreSQL dsn=%s", settings.db_url)
        except Exception as e:
            logger.error("Failed to initialize PostgreSQL database at %s: %s", settings.db_url, e)
            raise
    else:
        # SQLite backend (default)
        if _DB_PATH:
            try:
                os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
            except Exception as e:
                logger.error("Failed to create database directory %s: %s", os.path.dirname(_DB_PATH), e)
                raise

        try:
            async with aiosqlite.connect(_DB_PATH) as db:
                await db.execute(_CREATE_EVENTS)
                await db.execute(_CREATE_IDENTITIES)
                await db.execute(_CREATE_CAMERAS)
                await db.execute(_CREATE_ZONES)
                await db.commit()
            logger.info("Database initialised — backend=SQLite path=%s", _DB_PATH)
        except Exception as e:
            logger.error("Failed to initialize SQLite database at %s: %s", _DB_PATH, e)
            raise


# ============================================================================
# Event Storage
# ============================================================================


async def insert_event(alert: object) -> None:
    """
    Persist an Alert to the events table.
    Accepts any object with the Alert dataclass fields.
    """
    if _USE_PG:
        # PostgreSQL path
        try:
            import asyncpg
        except ImportError as e:
            raise RuntimeError("asyncpg not installed") from e

        async with _pool.acquire() as conn:
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
    else:
        # SQLite path (unchanged)
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute(
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
            await db.commit()


async def get_events(
    limit: int = 50,
    offset: int = 0,
    cam_id: Optional[str] = None,
    alert_type: Optional[str] = None,
    since: Optional[datetime] = None,
) -> list[dict]:
    """Return paginated event rows as dicts."""
    conditions: list[str] = []
    params: list = []

    if cam_id:
        param_idx = len(params) + 1
        conditions.append(f"cam_id = ${param_idx}" if _USE_PG else "cam_id = ?")
        params.append(cam_id)
    if alert_type:
        param_idx = len(params) + 1
        conditions.append(f"alert_type = ${param_idx}" if _USE_PG else "alert_type = ?")
        params.append(alert_type)
    if since:
        param_idx = len(params) + 1
        conditions.append(f"timestamp >= ${param_idx}" if _USE_PG else "timestamp >= ?")
        params.append(since.isoformat())

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    if _USE_PG:
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
    else:
        query = f"""
            SELECT id, alert_type, cam_id, zone_id, track_ids, global_ids,
                   name, confidence, timestamp, snapshot_path, metadata
            FROM events
            {where}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

    result: list[dict] = []

    if _USE_PG:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        for row in rows:
            d = dict(row)
            d["track_ids"] = json.loads(d["track_ids"]) if d["track_ids"] else []
            d["global_ids"] = json.loads(d["global_ids"]) if d["global_ids"] else []
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            result.append(d)
    else:
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        for row in rows:
            d = dict(row)
            d["track_ids"] = json.loads(d["track_ids"]) if d["track_ids"] else []
            d["global_ids"] = json.loads(d["global_ids"]) if d["global_ids"] else []
            d["metadata"] = json.loads(d["metadata"]) if d["metadata"] else {}
            result.append(d)

    return result


# ============================================================================
# Identity Storage
# ============================================================================


async def get_identities() -> list[dict]:
    """Return all known identities (excluding raw embedding bytes)."""
    query = "SELECT global_id, name, enrolled_at, last_seen, last_cam, sighting_count FROM identities"

    if _USE_PG:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [dict(row) for row in rows]
    else:
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def upsert_identity(
    global_id: str,
    name: str,
    embedding: bytes,
    last_cam: Optional[str] = None,
) -> None:
    """Insert or update a known identity with its embedding."""
    now = datetime.utcnow().isoformat()

    if _USE_PG:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO identities (global_id, name, embedding, enrolled_at, last_seen, last_cam, sighting_count)
                VALUES ($1, $2, $3, $4, $5, $6, 1)
                ON CONFLICT (global_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    embedding = EXCLUDED.embedding,
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
    else:
        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO identities (global_id, name, embedding, enrolled_at, last_seen, last_cam, sighting_count)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(global_id) DO UPDATE SET
                    name = excluded.name,
                    embedding = excluded.embedding,
                    last_seen = excluded.last_seen,
                    last_cam = excluded.last_cam,
                    sighting_count = sighting_count + 1
                """,
                (global_id, name, embedding, now, now, last_cam),
            )
            await db.commit()


async def update_identity_name(global_id: str, name: str) -> bool:
    """Update the display name for a known identity. Returns True if found, False if not."""
    if _USE_PG:
        async with _pool.acquire() as conn:
            status = await conn.execute(
                "UPDATE identities SET name = $1 WHERE global_id = $2",
                name,
                global_id,
            )
        # asyncpg returns status string like "UPDATE 1" — check if 1 row was updated
        return "1" in status
    else:
        async with aiosqlite.connect(_DB_PATH) as db:
            cursor = await db.execute(
                "UPDATE identities SET name = ? WHERE global_id = ?",
                (name, global_id),
            )
            await db.commit()
            return cursor.rowcount > 0


async def delete_identity(global_id: str) -> bool:
    """Delete an identity by global_id. Returns True if deleted, False if not found."""
    if _USE_PG:
        async with _pool.acquire() as conn:
            status = await conn.execute(
                "DELETE FROM identities WHERE global_id = $1",
                global_id,
            )
        # asyncpg returns status string like "DELETE 1" — check if 1 row was deleted
        return "1" in status
    else:
        async with aiosqlite.connect(_DB_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM identities WHERE global_id = ?",
                (global_id,),
            )
            await db.commit()
            return cursor.rowcount > 0


# ============================================================================
# Statistics
# ============================================================================


async def get_stats() -> dict:
    """Return summary statistics for the API /stats endpoint."""
    if _USE_PG:
        async with _pool.acquire() as conn:
            # Total events
            total_events_row = await conn.fetchval("SELECT COUNT(*) FROM events")
            total_events = total_events_row or 0

            # Events today
            today = datetime.utcnow().date().isoformat()
            events_today_row = await conn.fetchval(
                "SELECT COUNT(*) FROM events WHERE timestamp >= $1",
                today,
            )
            events_today = events_today_row or 0

            # Most active camera
            most_active_row = await conn.fetchrow(
                "SELECT cam_id FROM events GROUP BY cam_id ORDER BY COUNT(*) DESC LIMIT 1"
            )
            most_active_camera = most_active_row["cam_id"] if most_active_row else None

            # Active cameras
            active_cameras_row = await conn.fetchval("SELECT COUNT(*) FROM cameras WHERE active = 1")
            active_cameras = active_cameras_row or 0

            # Known identities
            known_identities_row = await conn.fetchval("SELECT COUNT(*) FROM identities")
            known_identities = known_identities_row or 0
    else:
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute("SELECT COUNT(*) AS total FROM events") as cur:
                total_events = (await cur.fetchone())["total"]

            today = datetime.utcnow().date().isoformat()
            async with db.execute(
                "SELECT COUNT(*) AS cnt FROM events WHERE timestamp >= ?", (today,)
            ) as cur:
                events_today = (await cur.fetchone())["cnt"]

            async with db.execute(
                "SELECT cam_id, COUNT(*) AS cnt FROM events GROUP BY cam_id ORDER BY cnt DESC LIMIT 1"
            ) as cur:
                row = await cur.fetchone()
                most_active_camera = row["cam_id"] if row else None

            async with db.execute("SELECT COUNT(*) AS cnt FROM cameras WHERE active = 1") as cur:
                active_cameras = (await cur.fetchone())["cnt"]

            async with db.execute("SELECT COUNT(*) AS cnt FROM identities") as cur:
                known_identities = (await cur.fetchone())["cnt"]

    return {
        "total_events": total_events,
        "events_today": events_today,
        "most_active_camera": most_active_camera,
        "active_cameras": active_cameras,
        "known_identities": known_identities,
    }
