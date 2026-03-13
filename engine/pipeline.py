"""
SENTINAL v2 — CameraPipeline
Phase 1: per-camera loop — YOLO detection, BoT-SORT tracking, MJPEG output.
Phase 2: zone intrusion detection + alert dispatch + zone polygon annotation.
Phase 3: Re-ID (OSNet-AIN) + face recognition (InsightFace) wired in.
Phase 4: weapon detector + anomaly detector wired in.
"""

import asyncio
import logging
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from engine.config import settings
from engine.stream.source import VideoSource
from engine.stream.mjpeg import MJPEGBuffer
from engine.vision.detector import Detector, Detection
from engine.vision.tracker import Tracker, Track
from engine.vision.modules.base import FrameContext
from engine.alerts.manager import AlertType

logger = logging.getLogger(__name__)

# Annotation colours (BGR)
_GREEN = (0, 220, 0)
_RED = (0, 0, 220)
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)
_BAR_BG = (30, 30, 30)
_YELLOW = (0, 220, 255)
_ORANGE = (0, 140, 255)


def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    """Convert a '#RRGGBB' hex string to a BGR tuple for OpenCV."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b, g, r)


def _draw_annotations(
    frame: np.ndarray,
    tracks: list[Track],
    weapon_detections: list[Detection],
    cam_id: str,
    fps: float,
    zones: list | None = None,
    triggered_zone_ids: set | None = None,
    global_ids: dict[int, str] | None = None,
    names: dict[int, str] | None = None,
    weapon_alert=None,
    module_results: list = None,
) -> np.ndarray:
    """
    Draw zone polygons, tracking boxes, weapon boxes, and a status bar onto a copy of the frame.

    - Zone polygons: filled (0.2 alpha) + outline; triggered zones red, others use zone.color
    - Tracked persons: green box + "ID:{track_id}" label
    - Weapons: red box + class_name + confidence label
    - Module detections (PPE, etc.): custom colored boxes + labels
    - Status bar at top: camera name, FPS, active track count
    """
    out = frame  # Draw directly on the frame (no copy — caller doesn't reuse it)
    h, w = out.shape[:2]

    # --- Scale all annotations based on frame resolution ---
    scale = max(w, h) / 720.0
    scale = max(scale, 1.0)
    font = cv2.FONT_HERSHEY_SIMPLEX
    box_thick = max(2, int(2 * scale))
    pad = int(6 * scale)

    # --- zone polygons (drawn before boxes so they appear underneath) ---
    if zones:
        triggered_zone_ids = triggered_zone_ids or set()
        overlay = out.copy()
        for zone in zones:
            if not zone.active:
                continue
            is_triggered = zone.zone_id in triggered_zone_ids
            color_bgr = _RED if is_triggered else _hex_to_bgr(zone.color)
            pts = np.array([[int(x), int(y)] for x, y in zone.polygon], dtype=np.int32)
            cv2.fillPoly(overlay, [pts], color_bgr)
        alpha = 0.3 if triggered_zone_ids else 0.2
        cv2.addWeighted(overlay, alpha, out, 1 - alpha, 0, out)

        for zone in zones:
            if not zone.active:
                continue
            is_triggered = zone.zone_id in triggered_zone_ids
            color_bgr = _RED if is_triggered else _hex_to_bgr(zone.color)
            pts = np.array([[int(x), int(y)] for x, y in zone.polygon], dtype=np.int32)
            cv2.polylines(out, [pts], isClosed=True, color=color_bgr, thickness=box_thick)
            cx = int(np.mean([p[0] for p in zone.polygon]))
            cy = int(np.mean([p[1] for p in zone.polygon]))
            zs = 0.55 * scale
            cv2.putText(out, zone.label, (cx, cy), font, zs, color_bgr, max(1, int(scale)), cv2.LINE_AA)

    # --- tracked persons ---
    label_fs = 0.7 * scale
    label_thick = max(1, int(1.5 * scale))

    for track in tracks:
        x1, y1, x2, y2 = track.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), _GREEN, box_thick)

        # Build label
        global_id = global_ids.get(track.track_id) if global_ids else None
        name = names.get(track.track_id) if names else None
        if name:
            label = name
        elif global_id:
            label = f"{global_id[:6]}"
        else:
            label = f"{track.track_id}"

        (tw, th), baseline = cv2.getTextSize(label, font, label_fs, label_thick)
        label_y = max(y1 - int(8 * scale), th + pad)
        cv2.rectangle(
            out,
            (x1 - 1, label_y - th - pad),
            (x1 + tw + pad * 2, label_y + baseline + pad // 2),
            _BAR_BG, -1,
        )
        cv2.putText(out, label, (x1 + pad, label_y), font, label_fs, _WHITE, label_thick, cv2.LINE_AA)

    # --- weapons (deprecated, handled by ModuleResult soon) ---
    _THREAT_COLORS = {
        "CRITICAL": (0, 0, 255),
        "HIGH": (0, 80, 255),
        "MEDIUM": _ORANGE,
        "UNKNOWN": _YELLOW,
    }

    for det in weapon_detections:
        x1, y1, x2, y2 = det.bbox
        threat = weapon_alert.threat_level if weapon_alert and weapon_alert.bbox == det.bbox else "UNKNOWN"
        color = _THREAT_COLORS.get(threat, _YELLOW)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, box_thick + 1)

        label = f"{det.class_name} {det.confidence:.2f}"
        if weapon_alert and weapon_alert.bbox == det.bbox:
            label = f"[{weapon_alert.threat_level}] {label}"
        (tw, th), baseline = cv2.getTextSize(label, font, label_fs, label_thick)
        label_y = max(y1 - int(8 * scale), th + pad)
        cv2.rectangle(
            out,
            (x1 - 1, label_y - th - pad),
            (x1 + tw + pad * 2, label_y + baseline + pad // 2),
            _BAR_BG, -1,
        )
        cv2.putText(out, label, (x1 + pad, label_y), font, label_fs, color, label_thick, cv2.LINE_AA)

    # --- Module Detections (PPE, WeaponModule, etc.) ---
    if module_results:
        for m_res in module_results:
            for m_det in m_res.detections:
                mx1, my1, mx2, my2 = m_det.bbox
                cv2.rectangle(out, (mx1, my1), (mx2, my2), m_det.color_bgr, box_thick)
                (tw, th), baseline = cv2.getTextSize(m_det.label, font, label_fs, label_thick)
                label_y = max(my1 - int(8 * scale), th + pad)
                cv2.rectangle(
                    out,
                    (mx1 - 1, label_y - th - pad),
                    (mx1 + tw + pad * 2, label_y + baseline + pad // 2),
                    _BAR_BG, -1,
                )
                cv2.putText(out, m_det.label, (mx1 + pad, label_y), font, label_fs, m_det.color_bgr, label_thick, cv2.LINE_AA)

    # --- weapon-person association line ---
    if weapon_alert and weapon_alert.holder_track_id is not None:
        holder_track = None
        for track in tracks:
            if track.track_id == weapon_alert.holder_track_id:
                holder_track = track
                break
        if holder_track:
            wx = (weapon_alert.bbox[0] + weapon_alert.bbox[2]) // 2
            wy = (weapon_alert.bbox[1] + weapon_alert.bbox[3]) // 2
            px = (holder_track.bbox[0] + holder_track.bbox[2]) // 2
            py = (holder_track.bbox[1] + holder_track.bbox[3]) // 2
            cv2.line(out, (wx, wy), (px, py), _RED, max(2, int(1.5 * scale)), cv2.LINE_AA)
            hx1, hy1, hx2, hy2 = holder_track.bbox
            cv2.rectangle(out, (hx1, hy1), (hx2, hy2), _RED, box_thick + 1)

    return out


class CameraPipeline:
    """
    Main per-camera pipeline.
    Runs in a background daemon thread.
    """

    def __init__(
        self,
        cam_id: str,
        source_url: str,
        zone_manager=None,
        alert_manager=None,
        reid_engine=None,
        face_recognizer=None,
        weapon_detector=None,
        anomaly_detector=None,
        module_registry=None,
        alert_queue=None,
        loop=None,
    ) -> None:
        self.cam_id = cam_id
        self.source_url = source_url
        self._module_registry = module_registry
        self._loop: Optional[asyncio.AbstractEventLoop] = loop

        self._source = VideoSource(url=source_url, cam_id=cam_id)
        self._mjpeg = MJPEGBuffer(cam_id=cam_id, loop=self._loop)
        self._detector: Optional[Detector] = None
        self._tracker: Optional[Tracker] = None

        self._zone_manager = zone_manager
        self._alert_manager = alert_manager
        self._alert_queue = alert_queue

        self._reid_engine = reid_engine
        self._face_recognizer = face_recognizer

        # Deprecated: use module_registry instead
        self._weapon_detector = weapon_detector
        self._anomaly_detector = anomaly_detector

        self._frame_count: int = 0
        self._debug_reid: bool = os.getenv("SENTINAL_DEBUG_REID", "0") == "1"

        self._db_registered: set[str] = set()
        self._track_stability: dict[int, dict] = {}
        self._STABILITY_FRAMES = 10

        self._smoothed_boxes: dict[int, list[float]] = {}
        self._SMOOTHING_ALPHA = 0.45

        self._process_every_n: int = settings.pipeline_process_every_n
        self._reid_every_n: int = settings.pipeline_reid_every_n
        self._face_every_n: int = settings.pipeline_face_every_n
        self._ai_frame_counter: int = 0

        self._cached_tracks: list = []
        self._cached_weapon_dets: list = []
        self._cached_weapon_alert = None
        self._cached_global_ids: dict[int, str] = {}
        self._cached_names: dict[int, str] = {}
        self._cached_triggered_zone_ids: set = set()
        self._cached_module_results: list = []
        self._cached_fps: float = 0.0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the video source and the processing thread."""
        self._stop_event.clear()
        self._source.start()
        self._thread = threading.Thread(
            target=self._run,
            name=f"Pipeline-{self.cam_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("CameraPipeline[%s] started — url=%s", self.cam_id, self.source_url)

    def start_sync(self) -> None:
        """Synchronous entry point — runs _run() in the calling thread."""
        self._stop_event.clear()
        self._source.start()
        self._thread = threading.current_thread()
        logger.info("CameraPipeline[%s] process started — url=%s", self.cam_id, self.source_url)
        self._run()

    def stop(self) -> None:
        """Signal the pipeline to stop and wait for clean shutdown."""
        self._stop_event.set()
        self._source.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10.0)
        logger.info("CameraPipeline[%s] stopped", self.cam_id)

    def get_mjpeg_buffer(self) -> MJPEGBuffer:
        """Return the MJPEG buffer for this camera (consumed by the stream router)."""
        return self._mjpeg

    def is_alive(self) -> bool:
        """True if both the capture thread and pipeline thread are running."""
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._source.is_alive()
        )

    # ------------------------------------------------------------------
    # Internal methods — Re-ID registration
    # ------------------------------------------------------------------

    def _register_new_person(
        self,
        global_id: str,
        crop: np.ndarray,
        embedding: np.ndarray,
    ) -> None:
        """
        Save reference crop + persist identity to DB + push WebSocket notification.
        Runs in a daemon thread so it never blocks the video loop.

        Args:
            global_id: The new person's global identifier.
            crop: BGR image crop of the person (for reference snapshot).
            embedding: Normalized 512-d embedding vector.
        """

        def _work():
            try:
                # 1. Save reference snapshot
                snap_dir = Path("data/snapshots/identities")
                snap_dir.mkdir(parents=True, exist_ok=True)
                snap_path = str(snap_dir / f"{global_id}.jpg")
                cv2.imwrite(snap_path, crop, [cv2.IMWRITE_JPEG_QUALITY, 85])

                # 2. Persist to DB (run async function synchronously from thread)
                from engine.storage import db as storage_db

                emb_bytes = embedding.tobytes()
                coro = storage_db.upsert_identity(
                    global_id=global_id,
                    name=None,
                    embedding=emb_bytes,
                    last_cam=self.cam_id,
                )
                
                _loop = self._loop or asyncio.get_running_loop()
                future = asyncio.run_coroutine_threadsafe(coro, _loop)
                future.result(timeout=5)

                # 3. Mark as saved in reid engine
                if self._reid_engine is not None:
                    self._reid_engine.mark_db_saved(global_id, embedding)

                # 4. Dispatch registration alert (logs to events table + WebSocket)
                if self._alert_manager is not None:
                    # Create a dummy event for AlertManager duck-typing
                    class RegistrationEvent:
                        def __init__(self, gid, cam):
                            self.alert_type = AlertType.IDENTITY_REGISTERED
                            self.global_id = gid
                            self.cam_id = cam
                            self.name = "New Person"
                            self.confidence = 1.0
                    
                    self._alert_manager.dispatch(RegistrationEvent(global_id, self.cam_id), crop, self.cam_id)

                logger.info(
                    "NEW PERSON REGISTERED: global_id=%s cam=%s snapshot=%s",
                    global_id,
                    self.cam_id,
                    snap_path,
                )
            except Exception as exc:
                logger.error("_register_new_person error for gid=%s: %s", global_id, exc)

        t = threading.Thread(target=_work, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Internal loop helpers
    # ------------------------------------------------------------------

    def _init_models(self) -> None:
        """Lazy-init models inside the thread so __init__ stays fast."""
        logger.info("CameraPipeline[%s] loading models…", self.cam_id)
        self._detector = Detector()
        self._tracker = Tracker()

        # In multiprocessing, we must init singletons inside the process
        if self._reid_engine is None:
            try:
                from engine.vision.reid import ReIDEngine
                from engine.config import settings
                model_path = os.path.join(settings.models_dir, settings.reid_model)
                self._reid_engine = ReIDEngine(model_path=model_path)
                logger.warning("CameraPipeline[%s] created NEW ReIDEngine (not shared!)", self.cam_id)
            except Exception as e:
                logger.warning("CameraPipeline[%s] ReIDEngine init failed: %s", self.cam_id, e)
        else:
            logger.info("CameraPipeline[%s] using SHARED ReIDEngine (id=%s)", self.cam_id, id(self._reid_engine))

        if self._face_recognizer is None:
            try:
                from engine.vision.face import FaceRecognizer
                self._face_recognizer = FaceRecognizer()
            except Exception as e:
                logger.warning("CameraPipeline[%s] FaceRecognizer init failed: %s", self.cam_id, e)

        if self._weapon_detector is None:
            try:
                from engine.vision.weapon import WeaponDetector
                self._weapon_detector = WeaponDetector()
            except Exception as e:
                logger.warning("CameraPipeline[%s] WeaponDetector init failed: %s", self.cam_id, e)

        if self._zone_manager is None:
            try:
                from engine.zones.manager import ZoneManager
                self._zone_manager = ZoneManager.get_instance()
            except Exception as e:
                logger.warning("CameraPipeline[%s] ZoneManager init failed: %s", self.cam_id, e)

        if self._anomaly_detector is None:
            try:
                from engine.vision.anomaly import AnomalyDetector
                self._anomaly_detector = AnomalyDetector()
            except Exception as e:
                logger.warning("CameraPipeline[%s] AnomalyDetector init failed: %s", self.cam_id, e)

        logger.info("CameraPipeline[%s] models ready", self.cam_id)

    def _process_frame_ai(self, frame: np.ndarray, track_to_global: dict, prev_track_ids: set) -> dict:
        """Run all AI models on a single frame and return results."""
        run_reid = (self._ai_frame_counter % self._reid_every_n == 0)
        run_face = (self._ai_frame_counter % self._face_every_n == 0)

        # 1. Detection
        if self._detector is None:
            logger.error("CameraPipeline[%s] detector is not initialized!", self.cam_id)
            detections = []
        else:
            detections = self._detector.detect(frame)

        person_dets = [d for d in detections if self._detector.is_person(d)]
        weapon_dets = [d for d in detections if self._detector.is_weapon(d)]

        # 2. Tracking
        if self._tracker is None:
            logger.error("CameraPipeline[%s] tracker is not initialized!", self.cam_id)
            tracks = []
        else:
            tracks = self._tracker.update(person_dets, frame)

        # 3. BBox Smoothing
        self._smooth_bboxes(tracks)
        current_track_ids = {t.track_id for t in tracks}

        # 4. Identity (Re-ID + Face)
        global_ids, names = self._process_identities(
            frame, tracks, track_to_global, prev_track_ids, current_track_ids, run_reid, run_face
        )

        # 5. Handle lost tracks
        self._handle_lost_tracks(prev_track_ids, current_track_ids, track_to_global)

        # 6. Periodic Maintenance
        self._periodic_maintenance(tracks, global_ids, track_to_global)

        # 7. Weapons
        weapon_alert = self._check_weapons(detections, tracks, global_ids, frame)

        # 8. Zones
        triggered_zone_ids, zone_events = self._process_zones(tracks, global_ids, frame)

        # 9. Modules
        module_results = self._process_modules(frame, detections, tracks, global_ids, zone_events)

        return {
            "tracks": tracks,
            "weapon_dets": weapon_dets,
            "weapon_alert": weapon_alert,
            "global_ids": global_ids,
            "names": names,
            "triggered_zone_ids": triggered_zone_ids,
            "module_results": module_results,
            "current_track_ids": current_track_ids
        }

    def _smooth_bboxes(self, tracks: list) -> None:
        """Apply EMA smoothing to bounding boxes."""
        for track in tracks:
            tid = track.track_id
            current_box = [float(v) for v in track.bbox]

            if tid in self._smoothed_boxes:
                stored_box = self._smoothed_boxes[tid]
                smoothed = [
                    self._SMOOTHING_ALPHA * c + (1.0 - self._SMOOTHING_ALPHA) * s
                    for c, s in zip(current_box, stored_box)
                ]
                self._smoothed_boxes[tid] = smoothed
                track.bbox = tuple(int(v) for v in smoothed)
            else:
                self._smoothed_boxes[tid] = current_box

        # Clean up smoothed boxes for tracks that disappeared
        current_tids = {t.track_id for t in tracks}
        lost_tids = set(self._smoothed_boxes.keys()) - current_tids
        for tid in lost_tids:
            self._smoothed_boxes.pop(tid, None)

    def _process_identities(
        self, frame: np.ndarray, tracks: list, track_to_global: dict, 
        prev_track_ids: set, current_track_ids: set, run_reid: bool, run_face: bool
    ) -> tuple[dict, dict]:
        """Run Re-ID and Face Recognition."""
        global_ids: dict[int, str] = {}
        names: dict[int, str] = {}

        # Carry forward cached results if not running models this frame
        if not run_reid and self._cached_global_ids:
            for track in tracks:
                if track.track_id in self._cached_global_ids:
                    global_ids[track.track_id] = self._cached_global_ids[track.track_id]
            if not run_face and self._cached_names:
                for track in tracks:
                    if track.track_id in self._cached_names:
                        names[track.track_id] = self._cached_names[track.track_id]

        if run_reid and self._reid_engine is not None:
            h, w = frame.shape[:2]
            for track in tracks:
                try:
                    res = self._process_single_track_identity(frame, track, h, w, run_face)
                    if res:
                        gid, name = res
                        global_ids[track.track_id] = gid
                        track_to_global[track.track_id] = gid
                        if name:
                            names[track.track_id] = name
                except Exception as exc:
                    logger.debug("Identity error for track %d: %s", track.track_id, exc)
        
        return global_ids, names

    def _process_single_track_identity(self, frame: np.ndarray, track, h: int, w: int, run_face: bool):
        """Extract embedding and run face recognition for one track."""
        x1, y1, x2, y2 = track.bbox
        x1c, y1c = max(0, x1), max(0, y1)
        x2c, y2c = min(w, x2), min(h, y2)
        if x2c <= x1c or y2c <= y1c:
            return None
        
        full_area = max(1, (x2 - x1) * (y2 - y1))
        visible_area = (x2c - x1c) * (y2c - y1c)
        visibility_ratio = visible_area / full_area
        if visibility_ratio < 0.6:
            return None
        
        crop_h, crop_w = y2c - y1c, x2c - x1c
        if crop_h < 40 or crop_w < 20 or crop_w > crop_h * 3:
            return None

        crop = frame[y1c:y2c, x1c:x2c]
        embedding, quality = self._reid_engine.extract_embedding(crop)
        gid = self._reid_engine.get_or_create_global_id(
            self.cam_id, track.track_id, embedding, quality
        )

        # Stabilized registration
        self._check_identity_registration(gid, track.track_id, crop, embedding, visible_area, visibility_ratio)

        name = None
        if run_face and self._face_recognizer is not None:
            face_results = self._face_recognizer.analyze(crop)
            if face_results:
                best = max(face_results, key=lambda f: f.quality_score)
                if best.global_id and best.quality_score > 0.7:
                    face_gid = best.global_id
                    # Fusion merge
                    if gid != face_gid:
                        if self._reid_engine.merge_identities(face_gid, gid):
                            gid = face_gid
                            self._reid_engine.mark_face_confirmed(face_gid)
                if best.name:
                    name = best.name
        
        return gid, name

    def _check_identity_registration(self, gid, tid, crop, embedding, area, ratio):
        """Check if identity should be registered to DB."""
        if gid not in self._db_registered and not self._reid_engine.is_db_saved(gid):
            crop_score = area * ratio
            stab = self._track_stability.get(tid)

            if stab is None or stab["gid"] != gid:
                self._track_stability[tid] = {
                    "gid": gid, "count": 1,
                    "best_crop": crop.copy(),
                    "best_score": crop_score,
                    "embedding": embedding.copy(),
                }
            else:
                stab["count"] += 1
                if crop_score > stab["best_score"]:
                    stab["best_crop"] = crop.copy()
                    stab["best_score"] = crop_score
                    stab["embedding"] = embedding.copy()

                if stab["count"] >= self._STABILITY_FRAMES:
                    self._db_registered.add(gid)
                    self._register_new_person(gid, stab["best_crop"], stab["embedding"])
                    self._track_stability.pop(tid, None)
        elif self._reid_engine.is_db_saved(gid):
            self._db_registered.add(gid)

    def _handle_lost_tracks(self, prev_track_ids: set, current_track_ids: set, track_to_global: dict):
        """Notify engine of lost tracks."""
        lost_ids = prev_track_ids - current_track_ids
        for lost_tid in lost_ids:
            self._track_stability.pop(lost_tid, None)
            gid = track_to_global.pop(lost_tid, None)
            if gid is not None and self._reid_engine:
                try:
                    self._reid_engine.move_to_lost(gid)
                except Exception as exc:
                    logger.debug("move_to_lost error for gid %s: %s", gid, exc)

    def _periodic_maintenance(self, tracks, global_ids, track_to_global):
        """Run periodic duplicate merge and logging."""
        if self._ai_frame_counter % 50 == 0:
            if self._reid_engine is not None:
                try:
                    n = self._reid_engine.merge_duplicates()
                    if n > 0:
                        logger.info("Pipeline[%s] merged %d duplicate identities", self.cam_id, n)
                        # Refresh global_ids after merge
                        for track in tracks:
                            key = (self.cam_id, track.track_id)
                            new_gid = self._reid_engine.local_to_global.get(key)
                            if new_gid:
                                global_ids[track.track_id] = new_gid
                                track_to_global[track.track_id] = new_gid
                except Exception as exc:
                    logger.debug("merge_duplicates error: %s", exc)
            
            logger.info(
                "Pipeline[%s] frame=%d ai_frame=%d tracks=%d reid=%s face=%s",
                self.cam_id, self._frame_count, self._ai_frame_counter,
                len(tracks), self._reid_engine is not None, self._face_recognizer is not None,
            )

    def _check_weapons(self, detections, tracks, global_ids, frame):
        """Run weapon detection."""
        weapon_alert = None
        if self._weapon_detector is not None:
            weapon_alert = self._weapon_detector.check(
                detections, self.cam_id,
                tracks=tracks, global_ids=global_ids or None,
            )
            if weapon_alert is not None:
                logger.warning(
                    "WEAPON DETECTED[%s] %s class=%s conf=%.2f holder=track#%s(%s)",
                    self.cam_id, weapon_alert.threat_level, weapon_alert.class_name,
                    weapon_alert.confidence, weapon_alert.holder_track_id,
                    weapon_alert.holder_global_id[:8] if weapon_alert.holder_global_id else "?",
                )
                self._dispatch_alert(weapon_alert, frame)
        return weapon_alert

    def _process_zones(self, tracks, global_ids, frame):
        """Run zone intrusion detection."""
        for track in tracks:
            track.global_id = global_ids.get(track.track_id, f"{self.cam_id}:{track.track_id}")

        triggered_zone_ids: set = set()
        zone_events: list = []
        if self._zone_manager is not None:
            intrusions = self._zone_manager.check_intrusions(tracks, self.cam_id)
            zone_events = list(intrusions)
            for intrusion in intrusions:
                triggered_zone_ids.add(intrusion.zone_id)
                self._dispatch_alert(intrusion, frame)
        return triggered_zone_ids, zone_events

    def _process_modules(self, frame, detections, tracks, global_ids, zone_events):
        """Run modular detection plugins."""
        module_results = []
        if self._module_registry is not None:
            ctx = FrameContext(
                frame=frame, detections=detections, tracks=tracks,
                global_ids=global_ids, cam_id=self.cam_id,
                frame_count=self._frame_count, zone_events=zone_events,
            )
            for module in self._module_registry.get_enabled_modules():
                try:
                    m_res = module.process(ctx)
                    module_results.append(m_res)
                    for alert in m_res.alerts:
                        self._dispatch_alert(alert, frame)
                except Exception as exc:
                    logger.error("Pipeline[%s] module %s error: %s", self.cam_id, module.module_id, exc)
        return module_results

    def _dispatch_alert(self, alert, frame):
        """Route alert to queue or manager."""
        if self._alert_queue:
            self._alert_queue.put((alert, frame, self.cam_id))
        elif self._alert_manager is not None:
            self._alert_manager.dispatch(alert, frame, self.cam_id)

    def _cache_results(self, ai_results: dict, fps: float) -> None:
        """Store AI results for frames where AI is skipped."""
        self._cached_tracks = ai_results["tracks"]
        self._cached_weapon_dets = ai_results["weapon_dets"]
        self._cached_weapon_alert = ai_results["weapon_alert"]
        self._cached_global_ids = ai_results["global_ids"]
        self._cached_names = ai_results["names"]
        self._cached_triggered_zone_ids = ai_results["triggered_zone_ids"]
        self._cached_module_results = ai_results["module_results"]
        self._cached_fps = fps

    def _annotate_and_push(
        self, frame, tracks, weapon_dets, global_ids, names, 
        triggered_zone_ids, weapon_alert, module_results, fps
    ) -> None:
        """Draw annotations and push to MJPEG buffer."""
        zones = (
            self._zone_manager.get_zones_for_camera(self.cam_id)
            if self._zone_manager is not None
            else None
        )
        annotated = _draw_annotations(
            frame, tracks, weapon_dets, self.cam_id, fps,
            zones=zones, triggered_zone_ids=triggered_zone_ids,
            global_ids=global_ids if self._reid_engine is not None else None,
            names=names if names else None,
            weapon_alert=weapon_alert,
            module_results=module_results,
        )
        self._mjpeg.push_frame(annotated)

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main pipeline loop — runs in a daemon thread."""
        self._init_models()

        fps_counter = _FPSCounter()
        last_frame_id: int = -1
        # track which track_ids are active to detect lost tracks
        prev_track_ids: set[int] = set()
        track_to_global: dict[int, str] = {}  # local track_id → global_id

        while not self._stop_event.is_set():
            frame = self._source.get_latest_frame()
            if frame is None:
                self._stop_event.wait(timeout=0.01)
                continue

            # Skip if this is the same frame object we already processed
            frame_id = id(frame)
            if frame_id == last_frame_id:
                self._stop_event.wait(timeout=0.005)
                continue
            last_frame_id = frame_id

            self._frame_count += 1

            # --- Frame skip logic ---
            run_ai = (self._frame_count % self._process_every_n == 0)

            if run_ai:
                self._ai_frame_counter += 1
                ai_results = self._process_frame_ai(frame, track_to_global, prev_track_ids)
                
                # Update loop state
                prev_track_ids = ai_results["current_track_ids"]
                fps = fps_counter.tick()
                
                # Cache results for skip frames
                self._cache_results(ai_results, fps)
                
                # Extract variables for annotation
                tracks = ai_results["tracks"]
                weapon_dets = ai_results["weapon_dets"]
                weapon_alert = ai_results["weapon_alert"]
                global_ids = ai_results["global_ids"]
                names = ai_results["names"]
                triggered_zone_ids = ai_results["triggered_zone_ids"]
                module_results = ai_results["module_results"]
            else:
                # Skip frame: reuse cached AI results, just tick FPS
                fps = fps_counter.tick()
                tracks = self._cached_tracks
                weapon_dets = self._cached_weapon_dets
                weapon_alert = self._cached_weapon_alert
                global_ids = self._cached_global_ids
                names = self._cached_names
                triggered_zone_ids = self._cached_triggered_zone_ids
                module_results = self._cached_module_results

            self._annotate_and_push(
                frame, tracks, weapon_dets, global_ids, names, 
                triggered_zone_ids, weapon_alert, module_results, fps
            )

        logger.info("CameraPipeline[%s] loop exited", self.cam_id)


class _FPSCounter:
    """Lightweight rolling FPS counter (last 30 frames)."""

    def __init__(self, window: int = 30) -> None:
        self._times: deque = deque(maxlen=window)

    def tick(self) -> float:
        now = time.monotonic()
        self._times.append(now)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0

