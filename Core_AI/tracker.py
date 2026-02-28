from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from ultralytics import YOLO

from Core_AI.config import ModelConfig


Track = Dict[str, object]
BBox = Tuple[float, float, float, float]


@dataclass
class TrackerError(Exception):
    message: str


class ObjectTracker:
    """ByteTrack-based multi-object tracker using ultralytics YOLO tracking."""

    def __init__(self, config: ModelConfig) -> None:
        try:
            self._model = YOLO(config.model_name)
        except Exception as exc:  # noqa: BLE001
            raise TrackerError(f"Failed to load YOLO model for tracking: {exc}") from exc
        self._conf = config.confidence_threshold
        self._iou = config.iou_threshold
        self._max_det = max(1, int(getattr(config, "max_det", 20)))
        self._imgsz = int(getattr(config, "imgsz", 640))

        # Auto-detect hardware acceleration
        import torch
        self._device_str = "cuda" if torch.cuda.is_available() else "cpu"

        # Fuse layers for faster CPU inference when supported.
        try:
            self._model.fuse()
        except Exception:  # noqa: BLE001
            pass

        # Warmup: run a dummy frame to trigger JIT so the first real frame isn't slow
        try:
            dummy = np.zeros((360, 640, 3), dtype=np.uint8)
            self._model.track(source=dummy, conf=self._conf, classes=[0],
                              persist=False, verbose=False, device=self._device_str)
        except Exception:  # noqa: BLE001
            pass

    def track(self, frame: np.ndarray) -> List[Track]:
        """Run tracking on a frame and return tracked person objects."""
        results = self._model.track(
            source=frame,
            conf=self._conf,
            iou=self._iou,
            classes=[0],  # person
            persist=True,
            verbose=False,
            device=self._device_str,
            imgsz=self._imgsz,
            max_det=self._max_det,
        )
        tracks: List[Track] = []
        if not results:
            return tracks

        result = results[0]
        if result.boxes is None or result.boxes.id is None:
            return tracks

        for box in result.boxes:
            xyxy = box.xyxy[0].tolist()
            track_id_tensor = box.id
            if track_id_tensor is None:
                continue
            track_id = int(track_id_tensor.item())
            conf = float(box.conf[0])
            tracks.append(
                {
                    "track_id": track_id,
                    "bbox": (float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])),
                    "conf": conf,
                }
            )
        return tracks

