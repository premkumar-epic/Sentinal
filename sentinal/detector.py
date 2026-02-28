from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from ultralytics import YOLO

from config import ModelConfig


Detection = Dict[str, object]
BBox = Tuple[float, float, float, float]


@dataclass
class DetectorError(Exception):
    message: str


class PersonDetector:
    """YOLOv8n-based person detector."""

    def __init__(self, config: ModelConfig) -> None:
        try:
            self._model = YOLO(config.model_name)
        except Exception as exc:  # noqa: BLE001
            raise DetectorError(f"Failed to load YOLO model: {exc}") from exc
        self._conf = config.confidence_threshold
        self._iou = config.iou_threshold
        self._imgsz = int(getattr(config, "imgsz", 640))

        try:
            self._model.fuse()
        except Exception:  # noqa: BLE001
            pass

    def predict(self, frame: np.ndarray) -> List[Detection]:
        """Run person detection on a single frame."""
        results = self._model.predict(
            source=frame,
            conf=self._conf,
            iou=self._iou,
            classes=[0],  # person
            verbose=False,
            device="cpu",
            imgsz=self._imgsz,
        )
        detections: List[Detection] = []
        if not results:
            return detections

        result = results[0]
        if result.boxes is None:
            return detections

        for box in result.boxes:
            xyxy = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            detections.append(
                {
                    "bbox": (float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])),
                    "conf": conf,
                    "class_id": cls_id,
                    "class_name": "person",
                }
            )
        return detections

