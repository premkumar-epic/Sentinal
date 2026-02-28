from __future__ import annotations

from datetime import datetime

import psycopg2
from psycopg2.extensions import connection

from sentinal.utils.logging_utils import get_logger


logger = get_logger(__name__)


def get_db_connection(db_url: str) -> connection:
    """Return a synchronous psycopg2 connection to PostgreSQL."""
    return psycopg2.connect(db_url)


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
    try:
        with get_db_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(schema)
            conn.commit()
        logger.info("Database schema initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database schema: %s", exc)


def insert_event(db_url: str, camera_id: str, object_id: int, zone: str, ts: datetime, snapshot_path: str) -> None:
    """Insert a single alert event into the PostgreSQL database."""
    if not db_url:
        return

    query = """
    INSERT INTO events (camera_id, object_id, zone, timestamp, snapshot_path)
    VALUES (%s, %s, %s, %s, %s)
    """
    try:
        with get_db_connection(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (camera_id, object_id, zone, ts, snapshot_path))
            conn.commit()
    except Exception as exc:
        logger.error("Failed to insert event into database: %s", exc)
