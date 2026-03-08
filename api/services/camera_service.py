"""
SENTINAL v2 — camera_service.py

Singleton wrapper around all active CameraPipeline instances.
Provides the interface consumed by api/routers/cameras.py and api/routers/stream.py.

Camera configs are persisted to data/cameras.json so they survive server restarts.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from engine.pipeline import CameraPipeline
from engine.stream.mjpeg import MJPEGBuffer

logger = logging.getLogger(__name__)

_CAMERAS_JSON = Path("data/cameras.json")


class _CameraService:
    """
    Manages all active camera pipelines.

    Thread-safe: a single RLock guards the internal registry.
    All public methods are synchronous (called from FastAPI async handlers
    via the standard threadpool — they are fast enough not to block the loop).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # {cam_id: {"pipeline": CameraPipeline, "url": str, "label": str, "added_at": str}}
        self._registry: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Lifecycle helpers called from api/main.py lifespan
    # ------------------------------------------------------------------

    def restore_cameras(self) -> None:
        """Re-start cameras persisted in data/cameras.json on server boot."""
        if not _CAMERAS_JSON.exists():
            logger.info("camera_service: no cameras.json found — starting fresh")
            return

        try:
            cameras = json.loads(_CAMERAS_JSON.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.error("camera_service: failed to read cameras.json — %s", exc)
            return

        for entry in cameras:
            cam_id = entry.get("cam_id")
            url = entry.get("url")
            label = entry.get("label")
            if cam_id and url:
                logger.info("camera_service: restoring cam_id=%s", cam_id)
                self._start_pipeline(cam_id, url, label, persist=False)

    def stop_all(self) -> None:
        """Stop every running pipeline. Called on server shutdown."""
        with self._lock:
            cam_ids = list(self._registry.keys())
        for cam_id in cam_ids:
            self._stop_pipeline(cam_id)
        logger.info("camera_service: all pipelines stopped")

    # ------------------------------------------------------------------
    # Public API (used by routers)
    # ------------------------------------------------------------------

    def add_camera(self, cam_id: str, url: str, label: Optional[str] = None) -> None:
        """Start a new pipeline and persist the camera config."""
        self._start_pipeline(cam_id, url, label, persist=True)

    def remove_camera(self, cam_id: str) -> None:
        """Stop pipeline and remove from persistence."""
        self._stop_pipeline(cam_id)
        self._persist()

    def list_cameras(self) -> list[dict]:
        """Return info dicts for all registered cameras."""
        with self._lock:
            result = []
            for cam_id, entry in self._registry.items():
                pipeline: CameraPipeline = entry["pipeline"]
                result.append({
                    "cam_id": cam_id,
                    "url": entry["url"],
                    "label": entry["label"],
                    "active": entry["active"],
                    "added_at": entry["added_at"],
                    "alive": pipeline.is_alive(),
                })
        return result

    def get_camera_info(self, cam_id: str) -> Optional[dict]:
        """Return info dict for a single camera, or None if not found."""
        with self._lock:
            entry = self._registry.get(cam_id)
            if entry is None:
                return None
            pipeline: CameraPipeline = entry["pipeline"]
            return {
                "cam_id": cam_id,
                "url": entry["url"],
                "label": entry["label"],
                "active": entry["active"],
                "added_at": entry["added_at"],
                "alive": pipeline.is_alive(),
            }

    def get_mjpeg_buffer(self, cam_id: str) -> Optional[MJPEGBuffer]:
        """Return the MJPEGBuffer for a camera, or None if not found."""
        with self._lock:
            entry = self._registry.get(cam_id)
            if entry is None:
                return None
            pipeline: CameraPipeline = entry["pipeline"]
            return pipeline.get_mjpeg_buffer()

    def update_camera(
        self,
        cam_id: str,
        url: Optional[str] = None,
        label: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> None:
        """Update camera metadata. If url changes, restarts the pipeline."""
        with self._lock:
            entry = self._registry.get(cam_id)
            if entry is None:
                return

            if label is not None:
                entry["label"] = label

            if active is not None:
                entry["active"] = active

            if url is not None and url != entry["url"]:
                # Restart pipeline with new URL
                entry["pipeline"].stop()
                entry["url"] = url
                pipeline = CameraPipeline(cam_id=cam_id, source_url=url)
                pipeline.start()
                entry["pipeline"] = pipeline

        self._persist()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_pipeline(
        self,
        cam_id: str,
        url: str,
        label: Optional[str],
        *,
        persist: bool,
    ) -> None:
        pipeline = CameraPipeline(cam_id=cam_id, source_url=url)
        pipeline.start()

        with self._lock:
            self._registry[cam_id] = {
                "pipeline": pipeline,
                "url": url,
                "label": label or cam_id,
                "active": True,
                "added_at": datetime.now(tz=timezone.utc).isoformat(),
            }

        if persist:
            self._persist()

    def _stop_pipeline(self, cam_id: str) -> None:
        with self._lock:
            entry = self._registry.pop(cam_id, None)
        if entry:
            entry["pipeline"].stop()

    def _persist(self) -> None:
        """Write current camera list to data/cameras.json."""
        _CAMERAS_JSON.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = [
                {"cam_id": cid, "url": e["url"], "label": e["label"]}
                for cid, e in self._registry.items()
                if e["active"]
            ]
        try:
            _CAMERAS_JSON.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("camera_service: failed to write cameras.json — %s", exc)


# Module-level singleton — imported by routers via lazy import
camera_service = _CameraService()
