"""
SENTINAL v2 — Storage: snapshots.py
Saves annotated JPEG snapshots to disk.
Called from daemon threads — must never block the video pipeline.
"""

import logging
import os
from datetime import datetime, timezone

import cv2
import numpy as np

from engine.config import settings

logger = logging.getLogger(__name__)


def save_snapshot(frame: np.ndarray, cam_id: str, alert_type: str) -> str:
    """
    JPEG-encode and write a snapshot frame to disk.

    Path format: data/snapshots/{YYYY-MM-DD}/{cam_id}_{alert_type}_{HHMMSSffffff}.jpg
    Quality: 85

    Returns:
        Relative file path from project root (stored in DB, served by FastAPI).
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S%f")

    dir_path = os.path.join(settings.snapshots_dir, date_str)
    os.makedirs(dir_path, exist_ok=True)

    filename = f"{cam_id}_{alert_type}_{time_str}.jpg"
    file_path = os.path.join(dir_path, filename)

    ok = cv2.imwrite(file_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        logger.error("save_snapshot failed to write: %s", file_path)
        return ""

    logger.debug("Snapshot saved: %s", file_path)
    return file_path
