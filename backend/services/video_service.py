"""
Video Service Manager managing multiple camera pipelines for the backend.
Instead of competing for the webcam, the backend spins up headless pipelines
for requested cameras and serves them via MJPEG.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Dict, Generator, Optional, Set

from config import AppConfig, VideoConfig, load_config
from sentinal.pipeline import SurveillancePipeline
from sentinal.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Single global lock for frames, mapping camera_id -> encoded jpeg bytes
_shared_frames: Dict[str, deque[bytes]] = {}
_shared_lock = threading.Lock()
_running = False

# This module-level function is still called by pipeline.py if it's run
# stand-alone (e.g. from gui.py) so it can push a frame. If multiple
# pipelines run, they need to supply their camera_id.
def push_frame(jpeg_bytes: bytes, camera_id: str = "cam_01") -> None:
    """Called by pipeline.py to push the latest encoded frame."""
    with _shared_lock:
        if camera_id not in _shared_frames:
            _shared_frames[camera_id] = deque(maxlen=2)
        _shared_frames[camera_id].append(jpeg_bytes)


class VideoStreamManager:
    """Manages headless pipelines and serves MJPEG streams."""

    _instance: Optional["VideoStreamManager"] = None

    def __new__(cls) -> "VideoStreamManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.pipelines: Dict[str, SurveillancePipeline] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self._initialized = True

    def start(self) -> None:
        global _running
        _running = True
        logger.info("VideoStreamManager ready — waiting for camera start requests.")

    def stop(self) -> None:
        global _running
        _running = False
        for cam_id in list(self.pipelines.keys()):
            self.stop_camera(cam_id)

    def start_camera(self, camera_id: str, video_path: Optional[str] = None) -> bool:
        """Start a headless surveillance pipeline for a given camera."""
        if camera_id in self.pipelines:
            return False  # Already running

        cfg = load_config()
        cfg.alert.camera_id = camera_id
        if video_path:
            from pathlib import Path
            cfg.video.source_type = "video"
            cfg.video.video_path = Path(video_path)
        else:
            cfg.video.source_type = "webcam"

        try:
            pipeline = SurveillancePipeline(cfg)
        except Exception as exc:
            logger.error(f"Failed to init camera {camera_id}: {exc}")
            return False

        self.pipelines[camera_id] = pipeline

        def _run_pipeline():
            logger.info(f"Starting headless pipeline for {camera_id}")
            try:
                for _frame, _tracks, _events in pipeline.frames():
                    if not _running or camera_id not in self.pipelines:
                        break
            except Exception as exc:
                logger.error(f"Pipeline crashed for {camera_id}: {exc}")
            finally:
                logger.info(f"Stopped headless pipeline for {camera_id}")

        t = threading.Thread(target=_run_pipeline, daemon=True, name=f"Pipeline-{camera_id}")
        self.threads[camera_id] = t
        t.start()
        return True

    def stop_camera(self, camera_id: str) -> bool:
        """Stop a specific camera pipeline."""
        if camera_id in self.pipelines:
            del self.pipelines[camera_id]
            # Thread will naturally die because of `camera_id not in self.pipelines` check
            return True
        return False

    def generate_mjpeg(self, camera_id: str) -> Generator[bytes, None, None]:
        """Yield MJPEG frames for the given camera from the shared buffer."""
        while _running:
            frame = None
            with _shared_lock:
                if camera_id in _shared_frames and _shared_frames[camera_id]:
                    frame = _shared_frames[camera_id][-1]

            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            time.sleep(0.03)

    def hot_reload_zones(self, configs: list) -> None:
        """Update zones safely in all running pipelines."""
        for pipeline in self.pipelines.values():
            if hasattr(pipeline, "_zones"):
                pipeline._zones.set_zones(configs)


video_manager = VideoStreamManager()
