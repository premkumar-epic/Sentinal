from datetime import datetime, timedelta
from fastapi import APIRouter
from typing import Dict, Any

from config import load_config
from sentinal.db import _get_pool
from sentinal.utils.logging_utils import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats() -> Dict[str, Any]:
    """Return aggregate statistics for the dashboard panel (IMP-13)."""
    cfg = load_config()
    db_url = cfg.alert.database_url
    if not db_url:
        return {
            "intrusions_24h": 0,
            "unique_people_24h": 0,
            "top_zone": "N/A"
        }

    pool = _get_pool(db_url)
    if not pool:
        return {
            "error": "Database not connected"
        }

    conn = None
    try:
        conn = pool.getconn()
        with conn.cursor() as cur:
            # Stats for last 24h
            yesterday = datetime.utcnow() - timedelta(hours=24)

            # Total Intrusions
            cur.execute("SELECT COUNT(*) FROM events WHERE timestamp >= %s", (yesterday,))
            total_intrusions = cur.fetchone()[0]

            # Unique People (distinct object_id)
            cur.execute("SELECT COUNT(DISTINCT object_id) FROM events WHERE timestamp >= %s", (yesterday,))
            unique_people = cur.fetchone()[0]

            # Top Zone
            cur.execute(
                "SELECT zone, COUNT(*) as c FROM events WHERE timestamp >= %s GROUP BY zone ORDER BY c DESC LIMIT 1",
                (yesterday,)
            )
            top_zone_row = cur.fetchone()
            top_zone = top_zone_row[0] if top_zone_row else "None"

        return {
            "intrusions_24h": total_intrusions,
            "unique_people_24h": unique_people,
            "top_zone": top_zone
        }
    except Exception as exc:
        logger.error("Failed to fetch stats: %s", exc)
        return {"error": str(exc)}
    finally:
        if conn:
            pool.putconn(conn)
