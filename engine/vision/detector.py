"""
SENTINAL v2 — Detector
Wraps YOLO11n for person and weapon detection.
Model is loaded once at init, never per-frame.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from engine.config import settings

logger = logging.getLogger(__name__)

# Weapon-related class names to flag (case-insensitive substring match)
_WEAPON_KEYWORDS = {"knife", "gun", "pistol", "rifle", "weapon"}


@dataclass
class Detection:
    """A single detection result from YOLO."""

    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    class_id: int
    class_name: str


class Detector:
    """
    Runs YOLO11n inference on a frame and returns Detection objects.
    Separates persons (class_id=0) from weapons automatically.
    Falls back to CPU if CUDA is unavailable.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "cuda",
    ) -> None:
        from ultralytics import YOLO

        if model_path is None:
            model_path = f"{settings.models_dir}{settings.yolo_model}"

        self._conf = settings.yolo_conf
        self._iou = settings.yolo_iou

        try:
            import torch
            if device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA not available — falling back to CPU")
                device = "cpu"
        except ImportError:
            device = "cpu"

        self._device = device
        self._model = YOLO(model_path)
        logger.info(
            "Detector loaded model=%s device=%s conf=%.2f",
            model_path, device, self._conf,
        )

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Run inference on a single BGR frame.
        Returns all detections filtered by confidence threshold.
        """
        results = self._model.predict(
            source=frame,
            conf=self._conf,
            iou=self._iou,
            device=self._device,
            verbose=False,
        )

        detections: list[Detection] = []
        if not results:
            return detections

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                conf = float(box.conf[0])
                if conf < self._conf:
                    continue
                cls_id = int(box.cls[0])
                cls_name = result.names.get(cls_id, str(cls_id))
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                detections.append(
                    Detection(
                        bbox=(x1, y1, x2, y2),
                        confidence=conf,
                        class_id=cls_id,
                        class_name=cls_name,
                    )
                )

        return detections

    @staticmethod
    def is_weapon(detection: Detection) -> bool:
        """Return True if this detection is a weapon class."""
        return any(kw in detection.class_name.lower() for kw in _WEAPON_KEYWORDS)

    @staticmethod
    def is_person(detection: Detection) -> bool:
        """Return True if this detection is a person (COCO class 0)."""
        return detection.class_id == 0 or detection.class_name.lower() == "person"
