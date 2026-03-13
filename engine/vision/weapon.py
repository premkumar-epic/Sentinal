"""
SENTINAL v2 — Weapon & Threat Detector
Filters YOLO detections for weapon/threat classes, associates them with
the nearest tracked person, classifies threat level, and triggers alarms.
Temporal confirmation reduces single-frame false positives.
"""

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from engine.vision.detector import Detection
from engine.vision.tracker import Track

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Threat classification
# ---------------------------------------------------------------------------

# CRITICAL: firearms — immediate lockdown
_CRITICAL_KEYWORDS = {"gun", "pistol", "rifle", "firearm", "handgun", "shotgun", "revolver"}

# HIGH: bladed weapons — serious bodily harm
_HIGH_KEYWORDS = {"knife", "sword", "machete", "dagger", "blade", "axe"}

# MEDIUM: blunt / improvised weapons — potential harm
_MEDIUM_KEYWORDS = {"baseball bat", "bat", "rod", "stick", "club", "hammer", "scissors"}

# Union of all threat keywords (for filtering YOLO detections)
_ALL_WEAPON_KEYWORDS = _CRITICAL_KEYWORDS | _HIGH_KEYWORDS | _MEDIUM_KEYWORDS | {"weapon"}

# Minimum confidence threshold for weapon detection
_WEAPON_CONFIDENCE_THRESHOLD = 0.45

# Temporal confirmation settings
_CONFIRMATION_WINDOW = 5   # Look at last 5 frames
_CONFIRMATION_REQUIRED = 2  # Must see at least 2 detections (lowered for responsiveness)

# Max pixel distance to associate a weapon bbox with a person bbox
_ASSOCIATION_MAX_DISTANCE = 300


def _classify_threat(class_name: str) -> str:
    """Classify threat level from detection class name."""
    name = class_name.lower()
    if any(kw in name for kw in _CRITICAL_KEYWORDS):
        return "CRITICAL"
    if any(kw in name for kw in _HIGH_KEYWORDS):
        return "HIGH"
    if any(kw in name for kw in _MEDIUM_KEYWORDS):
        return "MEDIUM"
    return "UNKNOWN"


def _bbox_center(bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
    """Return the center (cx, cy) of a bounding box."""
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _bbox_distance(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    """Euclidean distance between centers of two bounding boxes."""
    ca, cb = _bbox_center(a), _bbox_center(b)
    return math.hypot(ca[0] - cb[0], ca[1] - cb[1])


def _bbox_overlap(weapon_bbox: Tuple[int, int, int, int],
                  person_bbox: Tuple[int, int, int, int]) -> bool:
    """Check if the weapon bbox overlaps with or is inside the person bbox."""
    wx1, wy1, wx2, wy2 = weapon_bbox
    px1, py1, px2, py2 = person_bbox
    # Check if weapon center is inside (or near) person bbox
    wcx, wcy = _bbox_center(weapon_bbox)
    # Expand person bbox by 20% for near-overlap
    pw, ph = px2 - px1, py2 - py1
    ex1 = px1 - pw * 0.1
    ey1 = py1 - ph * 0.1
    ex2 = px2 + pw * 0.1
    ey2 = py2 + ph * 0.1
    return ex1 <= wcx <= ex2 and ey1 <= wcy <= ey2


@dataclass
class WeaponAlert:
    """
    Represents a detected weapon/threat alert.

    Attributes:
        cam_id: Camera identifier where weapon was detected.
        class_name: Weapon class name (e.g., "knife", "gun").
        confidence: Detection confidence score (0.0-1.0).
        bbox: Bounding box as (x1, y1, x2, y2).
        snapshot_path: Populated by AlertManager after snapshot is saved.
        threat_level: "CRITICAL", "HIGH", or "MEDIUM".
        holder_track_id: Track ID of the person holding/nearest to the weapon, or None.
        holder_global_id: Global Re-ID of the holder, or None.
    """
    cam_id: str
    class_name: str
    confidence: float
    bbox: tuple
    snapshot_path: str = ""
    threat_level: str = "UNKNOWN"
    holder_track_id: Optional[int] = None
    holder_global_id: Optional[str] = None


class WeaponDetector:
    """
    Weapon and threat detection filter for SENTINAL v2.

    Filters YOLO detections to identify weapons/threats, associates each
    weapon with the nearest person, classifies threat level, and returns
    alerts after temporal confirmation.

    Weapon alerts are HIGHEST PRIORITY and BYPASS ALL COOLDOWNS.
    """

    def __init__(self) -> None:
        # {cam_id: deque([bool, ...])} — weapon presence per frame
        self._history: Dict[str, deque] = {}
        # {cam_id: (best_detection, threat_level, holder_track_id, holder_global_id)}
        self._best_detections: Dict[str, Tuple[Detection, str, Optional[int], Optional[str]]] = {}
        logger.info(
            "WeaponDetector initialized — temporal confirmation %d/%d frames, "
            "threat levels: CRITICAL/HIGH/MEDIUM, confidence >= %.2f",
            _CONFIRMATION_REQUIRED, _CONFIRMATION_WINDOW, _WEAPON_CONFIDENCE_THRESHOLD,
        )

    def check(
        self,
        detections: List[Detection],
        cam_id: str,
        tracks: Optional[List[Track]] = None,
        global_ids: Optional[Dict[int, str]] = None,
    ) -> Optional[WeaponAlert]:
        """
        Check detections for weapons/threats and return alert after confirmation.

        Args:
            detections: All Detection objects from YOLO for this frame.
            cam_id: Camera identifier.
            tracks: Active person tracks (for weapon-person association).
            global_ids: Mapping of track_id -> global Re-ID (for identifying holder).

        Returns:
            WeaponAlert if threat is confirmed, else None.
        """
        if cam_id not in self._history:
            self._history[cam_id] = deque(maxlen=_CONFIRMATION_WINDOW)

        # 1. Find weapon detections in current frame
        weapon_dets = [
            d for d in detections
            if self._is_weapon(d) and d.confidence >= _WEAPON_CONFIDENCE_THRESHOLD
        ]

        has_weapon = len(weapon_dets) > 0
        self._history[cam_id].append(has_weapon)

        if has_weapon:
            # Pick highest confidence weapon detection
            best = max(weapon_dets, key=lambda d: d.confidence)
            threat = _classify_threat(best.class_name)

            # Associate with nearest person
            holder_tid, holder_gid = self._find_holder(best, tracks, global_ids)

            # Keep the best detection seen in this window
            prev = self._best_detections.get(cam_id)
            if prev is None or best.confidence > prev[0].confidence:
                self._best_detections[cam_id] = (best, threat, holder_tid, holder_gid)
        elif not any(self._history[cam_id]):
            self._best_detections.pop(cam_id, None)

        # 2. Check temporal confirmation
        confirmed_count = sum(self._history[cam_id])

        if confirmed_count >= _CONFIRMATION_REQUIRED:
            entry = self._best_detections.get(cam_id)
            if not entry:
                return None

            det, threat, holder_tid, holder_gid = entry

            alert = WeaponAlert(
                cam_id=cam_id,
                class_name=det.class_name,
                confidence=det.confidence,
                bbox=det.bbox,
                threat_level=threat,
                holder_track_id=holder_tid,
                holder_global_id=holder_gid,
            )

            holder_info = ""
            if holder_tid is not None:
                holder_info = f" holder=track#{holder_tid}"
                if holder_gid:
                    holder_info += f"({holder_gid[:8]})"

            logger.warning(
                "THREAT CONFIRMED [%s]: %s %s conf=%.2f (%d/%d frames)%s",
                cam_id, threat, det.class_name, det.confidence,
                confirmed_count, _CONFIRMATION_WINDOW, holder_info,
            )
            return alert

        return None

    def _find_holder(
        self,
        weapon_det: Detection,
        tracks: Optional[List[Track]],
        global_ids: Optional[Dict[int, str]],
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        Find the person most likely holding the detected weapon.

        Strategy: first check for bbox overlap (weapon inside person bbox),
        then fall back to nearest person by distance.

        Returns:
            (track_id, global_id) of the holder, or (None, None).
        """
        if not tracks:
            return None, None

        # First pass: check overlap (weapon inside/touching person bbox)
        for track in tracks:
            if _bbox_overlap(weapon_det.bbox, track.bbox):
                gid = global_ids.get(track.track_id) if global_ids else None
                return track.track_id, gid

        # Second pass: nearest person by center distance
        best_track = None
        best_dist = float("inf")
        for track in tracks:
            dist = _bbox_distance(weapon_det.bbox, track.bbox)
            if dist < best_dist:
                best_dist = dist
                best_track = track

        if best_track and best_dist < _ASSOCIATION_MAX_DISTANCE:
            gid = global_ids.get(best_track.track_id) if global_ids else None
            return best_track.track_id, gid

        return None, None

    @staticmethod
    def _is_weapon(detection: Detection) -> bool:
        """Check if a detection is a weapon/threat class."""
        name = detection.class_name.lower()
        return any(kw in name for kw in _ALL_WEAPON_KEYWORDS)
