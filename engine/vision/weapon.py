"""
SENTINAL v2 — Weapon Detector
Filters YOLO detections for weapon classes and triggers highest-priority alarm.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from engine.vision.detector import Detection

logger = logging.getLogger(__name__)

# Weapon class names to detect (case-insensitive substring match)
_WEAPON_KEYWORDS = {"knife", "gun", "pistol", "rifle", "weapon"}

# Minimum confidence threshold for weapon detection (higher than person to reduce false positives)
_WEAPON_CONFIDENCE_THRESHOLD = 0.55


@dataclass
class WeaponAlert:
    """
    Represents a detected weapon alert.

    Attributes:
        cam_id: Camera identifier where weapon was detected
        class_name: Weapon class name (e.g., "knife", "gun", "pistol", "rifle")
        confidence: Detection confidence score (0.0–1.0)
        bbox: Bounding box as (x1, y1, x2, y2) in pixel coordinates
        snapshot_path: Path to saved JPEG snapshot (set by AlertManager, not here)
    """
    cam_id: str
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]
    snapshot_path: str


class WeaponDetector:
    """
    Weapon detection filter for SENTINAL v2.

    Filters YOLO detections to identify weapons and returns the highest-confidence
    weapon alert if any detection exceeds the confidence threshold.

    CRITICAL: Weapon alerts are the highest priority in the system and BYPASS ALL
    COOLDOWNS. A weapon detection fires immediately regardless of the 60-second
    alert cooldown applied to other alert types. This ensures rapid response to
    critical threats.
    """

    def __init__(self) -> None:
        """
        Initialize the WeaponDetector.
        No model loading required — weapon detection uses YOLO detections from Detector.
        """
        logger.info("WeaponDetector initialized")

    def check(
        self,
        detections: list[Detection],
        cam_id: str
    ) -> Optional[WeaponAlert]:
        """
        Check detections for weapons and return the highest-confidence alert.

        Args:
            detections: List of Detection objects from YOLO (includes persons and weapons)
            cam_id: Camera identifier

        Returns:
            WeaponAlert if any weapon detection exceeds threshold, else None
            The returned alert has the highest confidence among all weapon detections.
        """
        weapon_detections = [
            d for d in detections
            if self._is_weapon(d) and d.confidence >= _WEAPON_CONFIDENCE_THRESHOLD
        ]

        if not weapon_detections:
            return None

        # Return the highest-confidence weapon detection
        best_detection = max(weapon_detections, key=lambda d: d.confidence)

        alert = WeaponAlert(
            cam_id=cam_id,
            class_name=best_detection.class_name,
            confidence=best_detection.confidence,
            bbox=best_detection.bbox,
            snapshot_path=""  # AlertManager will populate this
        )

        logger.warning(
            "WEAPON ALERT: cam_id=%s class=%s confidence=%.2f",
            cam_id, best_detection.class_name, best_detection.confidence
        )

        return alert

    @staticmethod
    def _is_weapon(detection: Detection) -> bool:
        """
        Check if a detection is a weapon class.

        Args:
            detection: Detection object to check

        Returns:
            True if detection class_name contains a weapon keyword (case-insensitive)
        """
        return any(kw in detection.class_name.lower() for kw in _WEAPON_KEYWORDS)
