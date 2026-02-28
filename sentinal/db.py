from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Optional

import psycopg2
from psycopg2 import pool

from sentinal.utils.logging_utils import get_logger

logger = get_logger(__name__)

_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_lock = Lock()


def _get_pool(db_url: str) -> Optional[pool.ThreadedConnectionPool]:
    """Lazy-init a thread-safe connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            try:
                _pool = pool.ThreadedConnectionPool(minconn=1, maxconn=5, dsn=db_url)
                logger.info("DB connection pool initialized (minconn=1, maxconn=5).")
            except Exception as exc:
                logger.error("Failed to create DB connection pool: %s", exc)
                return None
    return _pool


def init_db(db_url: str) -> None:
    """Initialize the PostgreSQL schema if it doesn't exist."""
    if not db_url:
        logger.warning("No DATABASE_URL configured, skipping DB init.")
        return

    schema = """
    CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
        camera_id VARCHAR(50) NOT NULL,
        object_id INTEGER NOT NULL,
        zone VARCHAR(100) NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        snapshot_path TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
    """
    p = _get_pool(db_url)
    if p is None:
        return
    conn = None
    try:
        conn = p.getconn()
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()
        logger.info("Database schema initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database schema: %s", exc)
    finally:
        if conn:
            p.putconn(conn)


def insert_event(db_url: str, camera_id: str, object_id: int, zone: str, ts: datetime, snapshot_path: str) -> None:
    """Insert a single alert event, reusing a pooled connection."""
    if not db_url:
        return

    query = """
    INSERT INTO events (camera_id, object_id, zone, timestamp, snapshot_path)
    VALUES (%s, %s, %s, %s, %s)
    """
    p = _get_pool(db_url)
    if p is None:
        return
    conn = None
    try:
        conn = p.getconn()
        with conn.cursor() as cur:
            cur.execute(query, (camera_id, object_id, zone, ts, snapshot_path))
        conn.commit()
    except Exception as exc:
        logger.error("Failed to insert event into database: %s", exc)
    finally:
        if conn:
            p.putconn(conn)


def get_recent_events(db_url: str, limit: int = 50) -> list:
    """Fetch the most recent alert events from the database."""
    if not db_url:
        return []
    p = _get_pool(db_url)
    if p is None:
        return []
    conn = None
    try:
        conn = p.getconn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, camera_id, object_id, zone, timestamp, snapshot_path "
                "FROM events ORDER BY timestamp DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {"id": r[0], "camera_id": r[1], "object_id": r[2], "zone": r[3],
             "timestamp": r[4].isoformat(), "snapshot_path": r[5]}
            for r in rows
        ]
    except Exception as exc:
        logger.error("Failed to fetch events: %s", exc)
        return []
    finally:
        if conn:
            p.putconn(conn)
