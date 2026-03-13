"""
SENTINAL v2 — MultiCamManager
Manages all camera pipelines, one threading.Thread per camera for Windows compatibility.
Persists camera registry to data/cameras.json for restart recovery.
"""

import json
import logging
import queue
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
    Orchestrates all CameraPipeline instances using threads.
    Shared queue for alerts from all camera threads.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # cam_id → {"pipeline": CameraPipeline, "thread": Thread, "url": str, "label": str, "added_at": str}
        self._cameras: dict[str, dict] = {}
        # Shared queue for alerts
        self._alert_queue = queue.Queue()
        self._alert_listener_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start_alert_listener(self, alert_manager) -> None:
        """Start a background thread to listen for alerts."""
        if self._alert_listener_thread and self._alert_listener_thread.is_alive():
            return

        def _listener():
            logger.info("MultiCamManager: Alert listener thread started.")
            while not self._stop_event.is_set():
                try:
                    # item is (event, frame, cam_id)
                    item = self._alert_queue.get(timeout=1.0)
                    if item:
                        event, frame, cam_id = item
                        alert_manager.dispatch(event, frame, cam_id)
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error("Error in alert listener: %s", e)
            logger.info("MultiCamManager: Alert listener thread exiting.")

        self._stop_event.clear()
        self._alert_listener_thread = threading.Thread(
            target=_listener, name="AlertQueueListener", daemon=True
        )
        self._alert_listener_thread.start()

    def add_camera(self, cam_id: str, url: str, label: str = "", **kwargs) -> None:
        """Start a new pipeline in a daemon thread."""
        with self._lock:
            if len(self._cameras) >= _MAX_CAMERAS:
                raise ValueError(f"Maximum number of cameras reached ({_MAX_CAMERAS}).")

            if cam_id in self._cameras:
                raise ValueError(f"Camera '{cam_id}' is already registered.")

            pipeline = CameraPipeline(
                cam_id=cam_id,
                source_url=url,
                alert_queue=self._alert_queue,
                **kwargs
            )
            
            thread = threading.Thread(
                target=pipeline.start_sync,
                name=f"CamThread-{cam_id}",
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
            logger.info("MultiCamManager: camera '%s' started in thread.", cam_id)
            self._persist()

    def remove_camera(self, cam_id: str) -> None:
        """Stop a camera pipeline."""
        with self._lock:
            entry = self._cameras.get(cam_id)
            if entry is None:
                raise KeyError(f"Camera '{cam_id}' not found.")

            pipeline: CameraPipeline = entry["pipeline"]
            pipeline.stop()
            
            thread: threading.Thread = entry["thread"]
            thread.join(timeout=2.0)

            del self._cameras[cam_id]
            logger.info("MultiCamManager: camera '%s' removed.", cam_id)
            self._persist()

    def update_metadata(self, cam_id: str, url: str = None, label: str = None) -> None:
        """Update camera metadata without restarting the pipeline."""
        with self._lock:
            entry = self._cameras.get(cam_id)
            if entry is None:
                raise KeyError(f"Camera '{cam_id}' not found.")
            
            if url:
                entry["url"] = url
            if label:
                entry["label"] = label
            
            logger.info("MultiCamManager: metadata for camera '%s' updated.", cam_id)
            self._persist()

    def list_cameras(self) -> list[dict]:
        with self._lock:
            result = []
            for cam_id, entry in self._cameras.items():
                pipeline: CameraPipeline = entry["pipeline"]
                result.append({
                    "cam_id": cam_id,
                    "url": entry["url"],
                    "label": entry["label"],
                    "added_at": entry["added_at"],
                    "alive": pipeline.is_alive(),
                })
            return result

    def get_mjpeg_buffer(self, cam_id: str) -> Optional[MJPEGBuffer]:
        with self._lock:
            entry = self._cameras.get(cam_id)
            if entry:
                return entry["pipeline"].get_mjpeg_buffer()
        return None

    def restore_cameras(self, add_camera_fn=None) -> None:
        """Restore cameras from data/cameras.json.

        Args:
            add_camera_fn: Optional callable(cam_id, url, label) that routes
                through the CameraService so shared singletons are used.
                Falls back to self.add_camera() if not provided.
        """
        if not _CAMERAS_JSON.exists():
            return
        try:
            entries = json.loads(_CAMERAS_JSON.read_text(encoding="utf-8"))
            for entry in entries:
                cam_id = entry.get("cam_id")
                url = entry.get("url")
                label = entry.get("label")
                if cam_id and url:
                    if add_camera_fn:
                        add_camera_fn(cam_id=cam_id, url=url, label=label)
                    else:
                        self.add_camera(cam_id=cam_id, url=url, label=label)
        except Exception as exc:
            logger.error("MultiCamManager: restore failed: %s", exc)

    def stop_all(self) -> None:
        self._stop_event.set()
        with self._lock:
            cam_ids = list(self._cameras.keys())
        for cam_id in cam_ids:
            self.remove_camera(cam_id)

    def _persist(self) -> None:
        _CAMERAS_JSON.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = [{"cam_id": cid, "url": e["url"], "label": e["label"]} for cid, e in self._cameras.items()]
        try:
            _CAMERAS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("MultiCamManager: persist failed: %s", exc)
