"""
SENTINAL v2 — camera_service.py

Singleton wrapper around all active CameraPipeline instances.
Provides the interface consumed by api/routers/cameras.py and api/routers/stream.py.

Camera configs are persisted to data/cameras.json so they survive server restarts.
"""

import asyncio
import logging
import os
import threading
from typing import Optional

from engine.stream.mjpeg import MJPEGBuffer

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Shared singletons — lazy-initialized on first use
# -----------------------------------------------------------------------
_init_lock = threading.Lock()

_reid_engine_instance = None
_face_recognizer_instance = None
_zone_manager_instance = None
_alert_manager_instance = None
_module_registry_instance = None
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store the running asyncio event loop (called from lifespan)."""
    global _event_loop
    _event_loop = loop


def _get_reid_engine():
    """Get or initialize the shared ReIDEngine singleton."""
    global _reid_engine_instance
    with _init_lock:
        if _reid_engine_instance is None:
            try:
                from engine.vision.reid import ReIDEngine
                from engine.config import settings

                model_path = os.path.join(settings.models_dir, settings.reid_model)
                _reid_engine_instance = ReIDEngine(model_path=model_path)
                logger.info("camera_service: ReIDEngine initialized")
            except Exception as exc:
                logger.warning("camera_service: ReIDEngine init failed — %s", exc)
                _reid_engine_instance = None
        return _reid_engine_instance


def _get_zone_manager():
    """Get or initialize the shared ZoneManager singleton."""
    global _zone_manager_instance
    with _init_lock:
        if _zone_manager_instance is None:
            try:
                from engine.zones.manager import ZoneManager

                _zone_manager_instance = ZoneManager()
                logger.info("camera_service: ZoneManager initialized")
            except Exception as exc:
                logger.warning("camera_service: ZoneManager init failed — %s", exc)
                _zone_manager_instance = None
        return _zone_manager_instance


def _get_face_recognizer():
    """Get or initialize the shared FaceRecognizer singleton."""
    global _face_recognizer_instance
    with _init_lock:
        if _face_recognizer_instance is None:
            try:
                from engine.vision.face import FaceRecognizer

                _face_recognizer_instance = FaceRecognizer()
                logger.info("camera_service: FaceRecognizer initialized")
            except Exception as exc:
                logger.warning("camera_service: FaceRecognizer init failed — %s", exc)
                _face_recognizer_instance = None
        return _face_recognizer_instance


def _get_module_registry():
    """Get or initialize the shared ModuleRegistry singleton."""
    global _module_registry_instance
    with _init_lock:
        if _module_registry_instance is None:
            try:
                from engine.vision.modules.registry import ModuleRegistry
                from engine.vision.modules.weapon_module import WeaponModule
                from engine.vision.modules.ppe_module import PPEModule
                from engine.vision.modules.anomaly_module import AnomalyModule
                from engine.config import settings

                registry = ModuleRegistry()
                
                # Register default modules
                registry.register(
                    WeaponModule(
                        model_path=os.path.join(settings.models_dir, settings.module_weapon_model),
                        confidence=settings.module_weapon_confidence,
                    ),
                    enabled_default=settings.module_weapon_enabled
                )
                
                registry.register(
                    PPEModule(
                        model_path=os.path.join(settings.models_dir, settings.module_ppe_model),
                        confidence=settings.module_ppe_confidence,
                        required_items=settings.module_ppe_required_items.split(","),
                    ),
                    enabled_default=settings.module_ppe_enabled
                )
                
                registry.register(
                    AnomalyModule(),
                    enabled_default=settings.module_anomaly_enabled
                )
                
                _module_registry_instance = registry
                logger.info("camera_service: ModuleRegistry initialized with %d modules", len(registry.list_modules()))
            except Exception as exc:
                logger.warning("camera_service: ModuleRegistry init failed — %s", exc)
                _module_registry_instance = None
        return _module_registry_instance


def _get_alert_manager():
    """Get or initialize the shared AlertManager singleton."""
    global _alert_manager_instance
    with _init_lock:
        if _alert_manager_instance is None:
            try:
                from engine.alerts.manager import AlertManager
                from engine.storage.db import insert_event
                from engine.storage.snapshots import save_snapshot
                from api.routers.ws import broadcast_event

                _alert_manager_instance = AlertManager(
                    ws_broadcaster=broadcast_event,
                    db_insert_fn=insert_event,
                    snapshot_fn=save_snapshot,
                    loop=_event_loop,
                )
                logger.info("camera_service: AlertManager initialized (loop=%s)", _event_loop is not None)
            except Exception as exc:
                logger.warning("camera_service: AlertManager init failed — %s", exc)
                _alert_manager_instance = None
        return _alert_manager_instance


class _CameraService:
    """
    Manages all active camera pipelines.
    Acts as a bridge to MultiCamManager which handles multiprocessing.
    """

    def __init__(self) -> None:
        from engine.manager import MultiCamManager
        self._manager = MultiCamManager()

    def start_listener(self) -> None:
        """Start the background alert listener thread."""
        alert_manager = _get_alert_manager()
        if alert_manager:
            self._manager.start_alert_listener(alert_manager)

    def restore_cameras(self) -> None:
        """Re-start cameras persisted in data/cameras.json on server boot.

        Routes through self.add_camera so each pipeline gets the shared
        ReIDEngine / FaceRecognizer / etc. singletons (critical for cross-camera Re-ID).
        """
        self._manager.restore_cameras(add_camera_fn=self.add_camera)

    def stop_all(self) -> None:
        """Stop every running pipeline. Called on server shutdown."""
        self._manager.stop_all()

    def add_camera(self, cam_id: str, url: str, label: Optional[str] = None) -> None:
        """Start a new pipeline using shared model singletons."""
        self._manager.add_camera(
            cam_id,
            url,
            label,
            zone_manager=_get_zone_manager(),
            alert_manager=_get_alert_manager(),
            reid_engine=_get_reid_engine(),
            face_recognizer=_get_face_recognizer(),
            module_registry=_get_module_registry(),
            loop=_event_loop,
        )

    def remove_camera(self, cam_id: str) -> None:
        """Stop pipeline and remove from persistence."""
        self._manager.remove_camera(cam_id)

    def list_cameras(self) -> list[dict]:
        """Return info dicts for all registered cameras."""
        return self._manager.list_cameras()

    def get_camera_info(self, cam_id: str) -> Optional[dict]:
        """Return info dict for a single camera, or None if not found."""
        cameras = self._manager.list_cameras()
        for cam in cameras:
            if cam["cam_id"] == cam_id:
                return cam
        return None

    def get_mjpeg_buffer(self, cam_id: str) -> Optional[MJPEGBuffer]:
        """Return the MJPEGBuffer for a camera, or None if not found."""
        return self._manager.get_mjpeg_buffer(cam_id)

    def get_module_registry(self):
        """Access the shared module registry."""
        return _get_module_registry()

    def update_camera(
        self,
        cam_id: str,
        url: Optional[str] = None,
        label: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> None:
        """Update camera metadata. If url changes, restarts the pipeline."""
        if url or label or active is not None:
            current_info = self.get_camera_info(cam_id)
            if current_info:
                new_url = url or current_info["url"]
                new_label = label or current_info["label"]
                
                if url and url != current_info["url"]:
                    # URL changed — must restart
                    self.remove_camera(cam_id)
                    self.add_camera(cam_id, new_url, new_label)
                else:
                    # URL same — just update metadata in persistence and memory
                    # Currently MultiCamManager stores metadata in self._cameras and data/cameras.json
                    # We need to expose a method in MultiCamManager to update metadata without restart.
                    # For now, if we don't have that method, we might still have to restart or 
                    # just update the persistence file manually.
                    # Let's assume we want to avoid restart if possible.
                    # I will add an update_metadata method to MultiCamManager.
                    self._manager.update_metadata(cam_id, url=new_url, label=new_label)

    def load_identities(self, identities: list[dict]) -> None:
        """Load known identities from DB into the shared Re-ID engine and Face recognizer."""
        if not identities:
            return

        reid = _get_reid_engine()
        if reid is not None:
            try:
                reid.load_known_identities(identities)
            except Exception as exc:
                logger.warning("load_identities: ReIDEngine failed — %s", exc)

        face = _get_face_recognizer()
        if face is not None:
            try:
                face.load_known_from_db(identities)
            except Exception as exc:
                logger.warning("load_identities: FaceRecognizer failed — %s", exc)


# Module-level singleton
camera_service = _CameraService()
