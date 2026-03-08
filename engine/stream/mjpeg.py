"""
SENTINAL v2 — MJPEGBuffer
JPEG-encodes annotated frames and serves them as a multipart HTTP stream.
Uses asyncio.Queue(maxsize=2) — drops oldest frame when full (non-blocking push).
"""

import asyncio
import logging
from typing import AsyncGenerator

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_BOUNDARY = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
_TAIL = b"\r\n"


class MJPEGBuffer:
    """
    Accepts BGR frames from the AI pipeline (sync side) and serves them
    as a multipart MJPEG stream to FastAPI (async side).

    Push model: pipeline calls push_frame() from its thread.
    Pull model: FastAPI iterates frame_generator() in an async context.
    """

    def __init__(self, cam_id: str) -> None:
        self.cam_id = cam_id
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2)
        # Capture the event loop to safely interact with the queue from threads
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.get_event_loop()

    def push_frame(self, frame: np.ndarray) -> None:
        """
        JPEG-encode frame and push into the async queue.
        Called from a synchronous pipeline thread.
        Drops the oldest frame if the queue is full to avoid lag.
        """
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            logger.warning("MJPEGBuffer[%s] JPEG encode failed — dropping frame", self.cam_id)
            return

        jpeg_bytes: bytes = buf.tobytes()

        # Thread-safe push into the asyncio queue
        self._loop.call_soon_threadsafe(self._safe_put, jpeg_bytes)

    def _safe_put(self, jpeg_bytes: bytes) -> None:
        """Internal helper to put into queue within the event loop."""
        try:
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            self._queue.put_nowait(jpeg_bytes)
        except Exception as e:
            logger.error("MJPEGBuffer[%s] error in _safe_put: %s", self.cam_id, e)

    async def frame_generator(self) -> AsyncGenerator[bytes, None]:
        """
        Async generator that yields multipart MJPEG chunks.
        Intended to be consumed by a FastAPI StreamingResponse.

        Yields bytes in the format:
            b"--frame\\r\\nContent-Type: image/jpeg\\r\\n\\r\\n" + jpeg + b"\\r\\n"
        """
        logger.info("MJPEGBuffer[%s] stream started", self.cam_id)
        try:
            while True:
                jpeg_bytes = await self._queue.get()
                yield _BOUNDARY + jpeg_bytes + _TAIL
        except asyncio.CancelledError:
            logger.info("MJPEGBuffer[%s] stream cancelled", self.cam_id)
            raise
