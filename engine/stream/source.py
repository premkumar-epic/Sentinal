"""
SENTINAL v2 — VideoSource
Threaded camera stream reader with auto-reconnect and exponential backoff.
"""

import logging
import threading
from collections import deque
from typing import Optional

import cv2
import numpy as np

from engine.config import settings

logger = logging.getLogger(__name__)


class VideoSource:
    """
    Opens a video stream in a background daemon thread.
    Stores only the latest frame (deque maxlen=2).
    Auto-reconnects on failure with exponential backoff.
    Never blocks the caller — get_latest_frame() returns immediately.
    """

    def __init__(self, url: str, cam_id: str) -> None:
        self.url = url
        self.cam_id = cam_id
        self._frames: deque = deque(maxlen=2)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._healthy = False

    def start(self) -> None:
        """Start the background capture thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"VideoSource-{self.cam_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("VideoSource[%s] started — url=%s", self.cam_id, self.url)

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._healthy = False
        logger.info("VideoSource[%s] stopped", self.cam_id)

    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Return the most recent frame, or None if not yet available."""
        if self._frames:
            return self._frames[-1]
        return None

    def is_alive(self) -> bool:
        """True if the background thread is running."""
        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        """Open a VideoCapture with the required buffer settings."""
        # Convert to int if the URL is just a number (e.g. "0" for webcam)
        if self.url.isdigit():
            source = int(self.url)
            # Use MSMF (Microsoft Media Foundation) on Windows — more reliable than DSHOW
            cap = cv2.VideoCapture(source, cv2.CAP_MSMF)
            if not cap.isOpened():
                # Fallback: try default backend
                cap = cv2.VideoCapture(source)
        else:
            source = self.url
            cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            return None
        # MANDATORY: prevents frames from being 2-5s old
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FPS, settings.stream_fps_target)
        return cap

    def _capture_loop(self) -> None:
        """
        Main capture loop. Reads frames continuously; on failure uses
        exponential backoff: 2 → 4 → 8 → 16 → 32s (then keeps retrying).
        Uses threading.Event for sleep so stop() wakes the thread immediately.
        """
        error_threshold = settings.stream_reconnect_error_threshold
        retry = 0
        cap: Optional[cv2.VideoCapture] = None

        while not self._stop_event.is_set():
            # --- connect ---
            if cap is None or not cap.isOpened():
                self._healthy = False
                if retry > 0:
                    delay = min(2 ** retry, 32)
                    if retry <= error_threshold:
                        logger.warning(
                            "VideoSource[%s] reconnect attempt %d — waiting %ds",
                            self.cam_id, retry, delay,
                        )
                    else:
                        logger.error(
                            "VideoSource[%s] exceeded %d retries — still trying (waiting %ds)",
                            self.cam_id, error_threshold, delay,
                        )
                    # Sleep interruptibly so stop() takes effect immediately
                    self._stop_event.wait(timeout=delay)
                    if self._stop_event.is_set():
                        break

                cap = self._open_capture()
                if cap is None:
                    retry += 1
                    continue
                retry = 0
                self._healthy = True
                logger.info("VideoSource[%s] stream opened", self.cam_id)

            # --- read frame ---
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning("VideoSource[%s] read failed — reconnecting", self.cam_id)
                cap.release()
                cap = None
                retry += 1
                continue

            self._frames.append(frame)

        # Cleanup
        if cap is not None:
            cap.release()
        self._healthy = False
        logger.info("VideoSource[%s] capture loop exited", self.cam_id)
