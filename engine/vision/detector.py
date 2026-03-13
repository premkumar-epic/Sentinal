"""
SENTINAL v2 — Detector
Wraps YOLO11l for person and weapon detection with FP16 inference.
Model is loaded once at init, never per-frame.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from engine.config import settings

logger = logging.getLogger(__name__)

# Weapon-related class names to flag (case-insensitive substring match).
# Covers both dedicated weapon model classes AND COCO threat objects.
_WEAPON_KEYWORDS = {
    # Firearms
    "gun", "pistol", "rifle", "firearm", "handgun", "shotgun", "revolver",
    # Bladed
    "knife", "sword", "machete", "dagger", "blade",
    # Blunt / impact
    "baseball bat", "bat", "rod", "stick", "club", "hammer", "axe",
    # Other threats
    "weapon", "scissors",
}


@dataclass
class Detection:
    """A single detection result from YOLO."""

    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    class_id: int
    class_name: str


class Detector:
    """
    Runs YOLO11l inference on a frame and returns Detection objects.
    Separates persons (class_id=0) from weapons automatically.
    Uses FP16 on CUDA for faster inference with no accuracy loss.
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

        # Class-specific thresholds for higher accuracy
        self._conf_person = settings.yolo_conf  # default 0.45
        self._conf_weapon = 0.55  # Strict for weapons but not too high
        self._iou = settings.yolo_iou  # 0.50 — higher NMS IoU keeps more overlapping boxes
        self._min_size = 32  # Minimum width/height in pixels (lowered for distant detections)
        self._min_aspect_ratio = 0.2  # Filter out extremely thin/wide false positive boxes
        self._max_aspect_ratio = 5.0

        self._use_half = False
        try:
            import torch
            if device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA not available — falling back to CPU")
                device = "cpu"
            elif device == "cuda":
                self._use_half = True  # FP16 on GPU — same accuracy, ~2x faster
        except ImportError:
            device = "cpu"

        self._device = device
        self._model = YOLO(model_path)

        # CLAHE for preprocessing under poor lighting
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        logger.info(
            "Detector loaded model=%s device=%s half=%s conf_person=%.2f conf_weapon=%.2f iou=%.2f",
            model_path, device, self._use_half, self._conf_person, self._conf_weapon, self._iou,
        )

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Apply adaptive CLAHE only under poor/uneven lighting (cheap grayscale check first)."""
        # Quick brightness check on grayscale — avoids full LAB conversion when not needed
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_l = gray.mean()
        if mean_l > 100:
            # Well-lit — skip expensive LAB path entirely
            return frame
        std_l = gray.std()
        if std_l > 40:
            return frame
        # Dark or low-contrast: apply CLAHE via LAB
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = self._clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Run inference on a single BGR frame.
        Returns all detections filtered by confidence and geometry checks.
        """
        processed = self._preprocess(frame)

        results = self._model.predict(
            source=processed,
            conf=min(self._conf_person, self._conf_weapon),
            iou=self._iou,
            device=self._device,
            half=self._use_half,
            imgsz=settings.yolo_imgsz,
            verbose=False,
        )

        detections: list[Detection] = []
        if not results:
            return detections

        frame_h, frame_w = frame.shape[:2]

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = result.names.get(cls_id, str(cls_id))

                # Apply class-specific confidence thresholds
                is_weapon = any(kw in cls_name.lower() for kw in _WEAPON_KEYWORDS)
                is_person = cls_id == 0 or cls_name.lower() == "person"

                # Only keep persons and weapons — ignore other COCO classes
                if not is_person and not is_weapon:
                    continue

                target_conf = self._conf_weapon if is_weapon else self._conf_person
                if conf < target_conf:
                    continue

                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                w, h = x2 - x1, y2 - y1

                # Minimum size filter to ignore distant noise
                if w < self._min_size or h < self._min_size:
                    continue

                # Aspect ratio filter — reject anomalous shapes
                aspect = h / max(w, 1)
                if aspect < self._min_aspect_ratio or aspect > self._max_aspect_ratio:
                    continue

                # Edge filter — reject detections that are >90% clipped by frame edge
                visible_x1 = max(0, x1)
                visible_y1 = max(0, y1)
                visible_x2 = min(frame_w, x2)
                visible_y2 = min(frame_h, y2)
                visible_area = max(0, visible_x2 - visible_x1) * max(0, visible_y2 - visible_y1)
                full_area = max(1, w * h)
                if visible_area / full_area < 0.3:
                    continue

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
