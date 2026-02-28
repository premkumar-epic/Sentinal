from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from Core_AI.config import load_config

cfg = load_config()

def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
    db_url = cfg.alert.database_url
    if not db_url:
        return []
        
    query = """
    SELECT id, camera_id, object_id, zone, timestamp, snapshot_path 
    FROM events 
    ORDER BY timestamp DESC 
    LIMIT %s
    """
    try:
        conn = psycopg2.connect(db_url)
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit,))
                rows = cur.fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        print(f"Failed to fetch events: {exc}")
        return []
