"""
Shared frame buffer between the SurveillancePipeline and the MJPEG stream endpoint.
The pipeline writes encoded JPEG bytes here; VideoStreamManager reads from it.
This eliminates the need for a second pipeline (and a competing camera open).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Generator, Optional

from sentinal.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Module-level shared buffer — pipeline.py writes here
_shared_frame: deque[bytes] = deque(maxlen=2)
_shared_lock = threading.Lock()
_running = False


def push_frame(jpeg_bytes: bytes) -> None:
    """Called by pipeline.py to push the latest encoded frame."""
    with _shared_lock:
        _shared_frame.append(jpeg_bytes)


class VideoStreamManager:
    """Reads from the shared frame buffer and serves MJPEG streams."""

    _instance: Optional["VideoStreamManager"] = None

    def __new__(cls) -> "VideoStreamManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

    def start(self) -> None:
        global _running
        _running = True
        logger.info("VideoStreamManager ready — consuming shared frame buffer.")

    def stop(self) -> None:
        global _running
        _running = False

    def generate_mjpeg(self, camera_id: str) -> Generator[bytes, None, None]:
        """Yield MJPEG frames for the given camera from the shared buffer."""
        while _running:
            with _shared_lock:
                frame = _shared_frame[-1] if _shared_frame else None

            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            time.sleep(0.03)


video_manager = VideoStreamManager()
