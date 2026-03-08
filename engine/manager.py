"""
SENTINAL v2 — MultiCamManager
Manages all camera pipelines, one threading.Thread per camera.
Persists camera registry to data/cameras.json for restart recovery.
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
_MAX_CAMERAS = 4


class MultiCamManager:
    """
    Orchestrates all CameraPipeline instances.

    Each camera runs in its own daemon thread.  The registry is
    protected by a re-entrant lock so add/remove can be called from
    any thread (e.g. FastAPI request handlers).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # cam_id → {"pipeline": CameraPipeline, "thread": Thread, "url": str, "label": str, "added_at": str}
        self._cameras: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_camera(self, cam_id: str, url: str, label: str = "") -> None:
        """
        Add a camera, start its pipeline in a daemon thread.

        Raises:
            ValueError: if cam_id is already registered.
        """
        with self._lock:
            if cam_id in self._cameras:
                raise ValueError(f"Camera '{cam_id}' is already registered.")

            if len(self._cameras) >= _MAX_CAMERAS:
                logger.warning(
                    "MultiCamManager: adding camera '%s' but already at %d cameras "
                    "(recommended max for RTX 4050 is %d).",
                    cam_id, len(self._cameras), _MAX_CAMERAS,
                )

            pipeline = CameraPipeline(cam_id=cam_id, source_url=url)
            thread = threading.Thread(
                target=pipeline.start,
                name=f"CamMgr-{cam_id}",
                daemon=True,
            )

            added_at = datetime.now(timezone.utc).isoformat()
            self._cameras[cam_id] = {
                "pipeline": pipeline,
                "thread": thread,
                "url": url,
                "label": label or cam_id,
                "added_at": added_at,
            }
            thread.start()
            logger.info("MultiCamManager: camera '%s' added (url=%s).", cam_id, url)
            self._persist()

    def remove_camera(self, cam_id: str) -> None:
        """
        Stop a camera pipeline and remove it from the registry.

        Raises:
            KeyError: if cam_id is not registered.
        """
        with self._lock:
            entry = self._cameras.get(cam_id)
            if entry is None:
                raise KeyError(f"Camera '{cam_id}' not found.")

            pipeline: CameraPipeline = entry["pipeline"]
            thread: threading.Thread = entry["thread"]

            pipeline.stop()
            thread.join(timeout=5.0)
            if thread.is_alive():
                logger.warning(
                    "MultiCamManager: thread for '%s' did not exit within 5 s.", cam_id
                )

            del self._cameras[cam_id]
            logger.info("MultiCamManager: camera '%s' removed.", cam_id)
            self._persist()

    def list_cameras(self) -> list[dict]:
        """Return a snapshot of all registered cameras with status info."""
        with self._lock:
            result = []
            for cam_id, entry in self._cameras.items():
                pipeline: CameraPipeline = entry["pipeline"]
                result.append(
                    {
                        "cam_id": cam_id,
                        "url": entry["url"],
                        "label": entry["label"],
                        "added_at": entry["added_at"],
                        "alive": pipeline.is_alive(),
                    }
                )
            return result

    def get_mjpeg_buffer(self, cam_id: str) -> Optional[MJPEGBuffer]:
        """Return the MJPEGBuffer for *cam_id*, or None if not found."""
        with self._lock:
            entry = self._cameras.get(cam_id)
            if entry is None:
                return None
            pipeline: CameraPipeline = entry["pipeline"]
            return pipeline.get_mjpeg_buffer()

    def get_status(self) -> dict:
        """Return a high-level status dict (used by /api/stats)."""
        with self._lock:
            cameras = self.list_cameras()
            return {
                "total_cameras": len(cameras),
                "active_cameras": sum(1 for c in cameras if c["alive"]),
                "cameras": cameras,
            }

    def restore_cameras(self) -> None:
        """
        Re-add cameras from data/cameras.json on startup.
        Skips entries that fail silently (logs error, continues).
        """
        if not _CAMERAS_JSON.exists():
            logger.info("MultiCamManager: no cameras.json found — starting empty.")
            return

        try:
            entries: list[dict] = json.loads(_CAMERAS_JSON.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("MultiCamManager: could not read cameras.json: %s", exc)
            return

        for entry in entries:
            cam_id = entry.get("cam_id", "")
            url = entry.get("url", "")
            label = entry.get("label", cam_id)
            if not cam_id or not url:
                logger.warning("MultiCamManager: skipping invalid entry in cameras.json: %s", entry)
                continue
            try:
                self.add_camera(cam_id=cam_id, url=url, label=label)
            except Exception as exc:
                logger.error(
                    "MultiCamManager: failed to restore camera '%s': %s", cam_id, exc
                )

    def stop_all(self) -> None:
        """Stop all camera pipelines and join their threads."""
        with self._lock:
            cam_ids = list(self._cameras.keys())

        for cam_id in cam_ids:
            try:
                self.remove_camera(cam_id)
            except Exception as exc:
                logger.error("MultiCamManager: error stopping '%s': %s", cam_id, exc)

        logger.info("MultiCamManager: all cameras stopped.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Write the current registry to data/cameras.json (called under lock)."""
        _CAMERAS_JSON.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "cam_id": cam_id,
                "url": entry["url"],
                "label": entry["label"],
                "added_at": entry["added_at"],
            }
            for cam_id, entry in self._cameras.items()
        ]
        try:
            tmp = _CAMERAS_JSON.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(_CAMERAS_JSON)
        except Exception as exc:
            logger.error("MultiCamManager: failed to persist cameras.json: %s", exc)
