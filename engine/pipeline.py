"""
SENTINAL v2 — CameraPipeline
Phase 1: per-camera loop — YOLO detection, BoT-SORT tracking, MJPEG output.
Phase 2: zone intrusion detection + alert dispatch + zone polygon annotation.
Phase 3: Re-ID (OSNet-AIN) + face recognition (InsightFace) wired in.
Phase 4: weapon detector + anomaly detector wired in.
"""

import logging
import os
import threading
import time
from typing import Optional

import cv2
import numpy as np

from engine.stream.source import VideoSource
from engine.stream.mjpeg import MJPEGBuffer
from engine.vision.detector import Detector, Detection
from engine.vision.tracker import Tracker, Track

logger = logging.getLogger(__name__)

# Annotation colours (BGR)
_GREEN = (0, 220, 0)
_RED = (0, 0, 220)
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)
_BAR_BG = (30, 30, 30)


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
) -> np.ndarray:
    """
    Draw zone polygons, tracking boxes, weapon boxes, and a status bar onto a copy of the frame.

    - Zone polygons: filled (0.2 alpha) + outline; triggered zones red, others use zone.color
    - Tracked persons: green box + "ID:{track_id}" label
    - Weapons: red box + class_name + confidence label
    - Status bar at top: camera name, FPS, active track count
    """
    out = frame.copy()
    h, w = out.shape[:2]

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
            # fill with alpha
            cv2.fillPoly(overlay, [pts], color_bgr)
        alpha = 0.3 if triggered_zone_ids else 0.2
        cv2.addWeighted(overlay, alpha, out, 1 - alpha, 0, out)

        # draw outlines and labels on top (no blending)
        for zone in zones:
            if not zone.active:
                continue
            is_triggered = zone.zone_id in triggered_zone_ids
            color_bgr = _RED if is_triggered else _hex_to_bgr(zone.color)
            pts = np.array([[int(x), int(y)] for x, y in zone.polygon], dtype=np.int32)
            cv2.polylines(out, [pts], isClosed=True, color=color_bgr, thickness=2)
            # label at polygon centroid
            cx = int(np.mean([p[0] for p in zone.polygon]))
            cy = int(np.mean([p[1] for p in zone.polygon]))
            cv2.putText(out, zone.label, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 1, cv2.LINE_AA)

    # --- status bar ---
    bar_height = 24
    cv2.rectangle(out, (0, 0), (w, bar_height), _BAR_BG, -1)
    status_text = f"{cam_id}  |  FPS: {fps:.1f}  |  Tracks: {len(tracks)}"
    cv2.putText(out, status_text, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, _WHITE, 1, cv2.LINE_AA)

    # --- tracked persons ---
    for track in tracks:
        x1, y1, x2, y2 = track.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), _GREEN, 2)
        # Build label: local ID + optional global_id prefix + optional name
        global_id = global_ids.get(track.track_id) if global_ids else None
        name = names.get(track.track_id) if names else None
        if name:
            label = f"{name} [{track.track_id}]"
        elif global_id:
            label = f"ID:{track.track_id} ({global_id[:8]})"
        else:
            label = f"ID:{track.track_id}"
        label_y = max(y1 - 6, bar_height + 12)
        cv2.putText(out, label, (x1, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, _GREEN, 2, cv2.LINE_AA)

    # --- weapons ---
    for det in weapon_detections:
        x1, y1, x2, y2 = det.bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), _RED, 2)
        label = f"{det.class_name} {det.confidence:.2f}"
        label_y = max(y1 - 6, bar_height + 12)
        cv2.putText(out, label, (x1, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, _RED, 2, cv2.LINE_AA)

    return out


class CameraPipeline:
    """
    Phase 1 per-camera pipeline.
    Runs in a background daemon thread (multiprocessing promoted in Phase 2).

    Responsibilities:
      1. Read frames from VideoSource
      2. Run YOLO detection (persons + weapons)
      3. Track persons with BoT-SORT
      4. Annotate frame and push to MJPEGBuffer
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
    ) -> None:
        self.cam_id = cam_id
        self.source_url = source_url

        self._source = VideoSource(url=source_url, cam_id=cam_id)
        self._mjpeg = MJPEGBuffer(cam_id=cam_id)
        self._detector: Optional[Detector] = None
        self._tracker: Optional[Tracker] = None

        # Phase 2 — optional zone/alert wiring (None = disabled for backward compat)
        self._zone_manager = zone_manager
        self._alert_manager = alert_manager

        # Phase 3 — optional Re-ID + face recognition (None = disabled for backward compat)
        self._reid_engine = reid_engine
        self._face_recognizer = face_recognizer

        # Phase 4 — optional weapon + anomaly detection (None = disabled for backward compat)
        self._weapon_detector = weapon_detector
        self._anomaly_detector = anomaly_detector

        # Phase 3 — diagnostic logging and debug flags
        self._frame_count: int = 0
        self._debug_reid: bool = os.getenv("SENTINAL_DEBUG_REID", "0") == "1"

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
    # Internal loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main pipeline loop — runs in a daemon thread."""
        # Lazy-init models inside the thread so __init__ stays fast
        logger.info("CameraPipeline[%s] loading models…", self.cam_id)
        self._detector = Detector()
        self._tracker = Tracker()
        logger.info("CameraPipeline[%s] models ready", self.cam_id)

        fps_counter = _FPSCounter()
        last_frame_id: int = -1
        # Phase 3: track which global_ids are active to detect lost tracks
        prev_track_ids: set[int] = set()
        track_to_global: dict[int, str] = {}  # local track_id → global_id

        while not self._stop_event.is_set():
            frame = self._source.get_latest_frame()
            if frame is None:
                # No frame yet — yield briefly without busy-spinning
                self._stop_event.wait(timeout=0.01)
                continue

            # Skip if this is the same frame object we already processed
            frame_id = id(frame)
            if frame_id == last_frame_id:
                self._stop_event.wait(timeout=0.005)
                continue
            last_frame_id = frame_id

            self._frame_count += 1

            # --- detection ---
            detections = self._detector.detect(frame)

            person_dets = [d for d in detections if self._detector.is_person(d)]
            weapon_dets = [d for d in detections if self._detector.is_weapon(d)]

            # --- Phase 4: weapon check (highest priority — bypasses all cooldowns) ---
            if self._weapon_detector is not None and self._alert_manager is not None:
                weapon_alert = self._weapon_detector.check(detections, self.cam_id)
                if weapon_alert is not None:
                    logger.warning(
                        "WEAPON DETECTED[%s] class=%s conf=%.2f",
                        self.cam_id, weapon_alert.class_name, weapon_alert.confidence,
                    )
                    self._alert_manager.dispatch(weapon_alert, frame, self.cam_id)

            # --- tracking (persons only) ---
            tracks = self._tracker.update(person_dets, frame)

            # --- Phase 3: Re-ID + face recognition ---
            global_ids: dict[int, str] = {}   # track_id → global_id
            names: dict[int, str] = {}         # track_id → name
            current_track_ids: set[int] = {t.track_id for t in tracks}

            if self._reid_engine is not None:
                h, w = frame.shape[:2]
                for track in tracks:
                    x1, y1, x2, y2 = track.bbox
                    # Clamp crop to frame bounds
                    x1c, y1c = max(0, x1), max(0, y1)
                    x2c, y2c = min(w, x2), min(h, y2)
                    if x2c <= x1c or y2c <= y1c:
                        continue
                    crop = frame[y1c:y2c, x1c:x2c]
                    try:
                        embedding = self._reid_engine.extract_embedding(crop)
                        gid = self._reid_engine.get_or_create_global_id(
                            self.cam_id, track.track_id, embedding
                        )
                        global_ids[track.track_id] = gid
                        track_to_global[track.track_id] = gid

                        # Log Re-ID distance if debug enabled
                        if self._debug_reid:
                            logger.debug(
                                "Re-ID[%s] track_id=%d global_id=%s embedding_norm=%.3f",
                                self.cam_id,
                                track.track_id,
                                gid,
                                float(np.linalg.norm(embedding)),
                            )

                        # Face recognition on same crop
                        if self._face_recognizer is not None:
                            face_results = self._face_recognizer.analyze(crop)
                            if face_results:
                                best = max(face_results, key=lambda f: f.quality_score)
                                # Re-ID + Face fusion: high-confidence face match overrides Re-ID
                                if best.global_id and best.quality_score > 0.7:
                                    global_ids[track.track_id] = best.global_id
                                    track_to_global[track.track_id] = best.global_id
                                    logger.debug(
                                        "Face fusion[%s] track_id=%d overrode Re-ID with face global_id=%s (quality=%.3f)",
                                        self.cam_id,
                                        track.track_id,
                                        best.global_id,
                                        best.quality_score,
                                    )
                                if best.name:
                                    names[track.track_id] = best.name
                    except Exception as exc:
                        logger.debug("Re-ID error for track %d: %s", track.track_id, exc)

                # Notify Re-ID engine of tracks that disappeared this frame
                lost_ids = prev_track_ids - current_track_ids
                for lost_tid in lost_ids:
                    gid = track_to_global.pop(lost_tid, None)
                    if gid is not None:
                        try:
                            self._reid_engine.move_to_lost(gid)
                        except Exception as exc:
                            logger.debug("move_to_lost error for gid %s: %s", gid, exc)

            prev_track_ids = current_track_ids

            # --- Phase 3: pipeline diagnostics (every 50 frames) ---
            if self._frame_count % 50 == 0:
                reid_active = self._reid_engine is not None
                face_active = self._face_recognizer is not None
                logger.info(
                    "Pipeline[%s] frame=%d tracks=%d reid_active=%s face_active=%s",
                    self.cam_id,
                    self._frame_count,
                    len(tracks),
                    reid_active,
                    face_active,
                )

            # --- Phase 2: zone intrusion detection + alert dispatch ---
            triggered_zone_ids: set = set()
            zone_events: list = []
            if self._zone_manager is not None:
                intrusions = self._zone_manager.check_intrusions(tracks, self.cam_id)
                zone_events = list(intrusions)
                for intrusion in intrusions:
                    triggered_zone_ids.add(intrusion.zone_id)
                    if self._alert_manager is not None:
                        self._alert_manager.dispatch(intrusion, frame, self.cam_id)

            # --- Phase 4: anomaly detection (loitering, crowding, violence) ---
            if self._anomaly_detector is not None and self._alert_manager is not None:
                anomalies = self._anomaly_detector.update(tracks, zone_events)
                for anomaly in anomalies:
                    self._alert_manager.dispatch(anomaly, frame, self.cam_id)

            # --- annotate and push ---
            zones = (
                self._zone_manager.get_zones_for_camera(self.cam_id)
                if self._zone_manager is not None
                else None
            )
            fps = fps_counter.tick()
            annotated = _draw_annotations(
                frame, tracks, weapon_dets, self.cam_id, fps,
                zones=zones,
                triggered_zone_ids=triggered_zone_ids,
                global_ids=global_ids if self._reid_engine is not None else None,
                names=names if names else None,
            )
            self._mjpeg.push_frame(annotated)

        logger.info("CameraPipeline[%s] loop exited", self.cam_id)


class _FPSCounter:
    """Lightweight rolling FPS counter (last 30 frames)."""

    def __init__(self, window: int = 30) -> None:
        self._times: list[float] = []
        self._window = window

    def tick(self) -> float:
        now = time.monotonic()
        self._times.append(now)
        if len(self._times) > self._window:
            self._times.pop(0)
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0
