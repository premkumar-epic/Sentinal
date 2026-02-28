from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from Core_AI.config import VideoConfig
from Core_AI.utils.logging_utils import get_logger


Frame = np.ndarray

logger = get_logger(__name__)


@dataclass
class VideoSourceError(Exception):
    message: str


class VideoSource:
    """Thread-safe background frame reader for cv2.VideoCapture."""

    def __init__(self, config: VideoConfig) -> None:
        self._config = config
        self._capture: Optional[cv2.VideoCapture] = None
        # Maxlen=2 keeps only the latest 2 frames, eliminating stale-frame delay
        self._q: deque[np.ndarray] = deque(maxlen=2)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._capture is not None:
            return

        source_type = self._config.source_type
        if source_type == "webcam":
            index = self._config.webcam_index
            logger.info("Opening webcam source index=%s", index)
            self._capture = cv2.VideoCapture(index)  # Default backend (CAP_DSHOW fails on some Windows drivers)
        elif source_type == "video":
            if self._config.video_path is None:
                raise VideoSourceError("Video path must be provided for 'video' source type.")
            logger.info("Opening video file source path=%s", self._config.video_path)
            self._capture = cv2.VideoCapture(str(self._config.video_path))
        else:
            raise VideoSourceError(f"Unsupported source_type: {source_type}")

        if not self._capture.isOpened():
            logger.error("Failed to open video source (type=%s).", source_type)
            self.stop()
            raise VideoSourceError("Failed to open video source.")

        if self._config.frame_width is not None:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.frame_width)
        if self._config.frame_height is not None:
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.frame_height)
        # Minimize internal OpenCV buffer to reduce latency
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._update, daemon=True)
        self._thread.start()

    def _update(self) -> None:
        """Background thread loop to continuously ingest frames."""
        while not self._stop_event.is_set():
            success, frame = self._capture.read()
            if not success:
                logger.info("End of stream or failed frame read from source_type=%s", self._config.source_type)
                self._stop_event.set()
                return
            # Always overwrite oldest, keeping the queue fresh
            with self._lock:
                self._q.append(frame)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._capture is not None:
            logger.info("Releasing video source.")
            self._capture.release()
            self._capture = None

    def read(self) -> Tuple[bool, Optional[Frame]]:
        """Read the latest frame from the source. Blocks briefly if queue is empty."""
        if self._capture is None:
            raise VideoSourceError("Video source has not been started.")

        t0 = time.time()
        while True:
            with self._lock:
                if len(self._q) > 0:
                    return True, self._q.popleft()

            if self._stop_event.is_set():
                return False, None

            if time.time() - t0 > 10.0:
                logger.error("Timeout reading frame from VideoSource.")
                return False, None

            time.sleep(0.002)  # tighter poll interval

    def __enter__(self) -> "VideoSource":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
