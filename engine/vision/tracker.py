"""
SENTINAL v2 — Tracker
Wraps BoT-SORT (via boxmot or Ultralytics) for stable per-camera track IDs.
Track IDs are local to one camera — Re-ID handles cross-camera identity.
"""

import logging
from dataclasses import dataclass

import numpy as np

from engine.vision.detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """A single tracked person with a stable local ID."""

    track_id: int
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float


class Tracker:
    """
    Wraps BoT-SORT tracking.
    Accepts Detection objects, returns Track objects.
    Filters to person detections only (class_id == 0).
    """

    def __init__(self) -> None:
        try:
            from boxmot import BoTSORT
            self._tracker = BoTSORT(
                reid_weights=None,
                device="cuda",
                half=False,
            )
            self._backend = "boxmot"
            logger.info("Tracker initialised — backend=boxmot/BoT-SORT")
        except Exception as e:
            logger.warning("boxmot unavailable (%s) — falling back to ultralytics tracker", e)
            self._tracker = None
            self._backend = "ultralytics"

    def update(self, detections: list[Detection], frame: np.ndarray) -> list[Track]:
        """
        Update tracker state with new detections for this frame.

        Args:
            detections: All Detection objects from the Detector for this frame.
            frame: The BGR frame (required by BoT-SORT for appearance features).

        Returns:
            List of active Track objects (persons only).
        """
        # Filter to persons only
        person_dets = [d for d in detections if d.class_id == 0]

        if not person_dets:
            if self._backend == "boxmot" and self._tracker is not None:
                # Keep tracker state alive with empty input
                try:
                    self._tracker.update(np.empty((0, 6), dtype=np.float32), frame)
                except Exception:
                    pass
            return []

        if self._backend == "boxmot" and self._tracker is not None:
            return self._update_boxmot(person_dets, frame)
        else:
            return self._update_fallback(person_dets)

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    def _update_boxmot(self, person_dets: list[Detection], frame: np.ndarray) -> list[Track]:
        """BoT-SORT via boxmot library."""
        # boxmot expects: [[x1, y1, x2, y2, conf, cls], ...]
        det_array = np.array(
            [
                [d.bbox[0], d.bbox[1], d.bbox[2], d.bbox[3], d.confidence, d.class_id]
                for d in person_dets
            ],
            dtype=np.float32,
        )

        try:
            tracks = self._tracker.update(det_array, frame)
        except Exception as exc:
            logger.error("BoT-SORT update failed: %s", exc)
            return []

        result: list[Track] = []
        if tracks is not None and len(tracks):
            for t in tracks:
                # boxmot output: [x1, y1, x2, y2, track_id, conf, cls, ...]
                x1, y1, x2, y2 = int(t[0]), int(t[1]), int(t[2]), int(t[3])
                tid = int(t[4])
                conf = float(t[5])
                result.append(Track(track_id=tid, bbox=(x1, y1, x2, y2), confidence=conf))
        return result

    def _update_fallback(self, person_dets: list[Detection]) -> list[Track]:
        """
        Minimal ID-assignment fallback when boxmot is unavailable.
        Assigns sequential IDs per frame (not stable across frames).
        This is only used when boxmot cannot be imported.
        """
        logger.debug("Using fallback tracker — track IDs are NOT stable across frames")
        return [
            Track(
                track_id=idx + 1,
                bbox=d.bbox,
                confidence=d.confidence,
            )
            for idx, d in enumerate(person_dets)
        ]
