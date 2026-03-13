"""
SENTINAL v2 — PPE Compliance Detection Module.
Detects Personal Protective Equipment (helmet, vest, gloves, goggles, boots)
and alerts when tracked persons are missing required items.
"""

import logging
import math
import os
from typing import Optional

from engine.config import settings
from engine.vision.modules.base import (
    DetectionModule,
    FrameContext,
    ModuleDetection,
    ModuleResult,
)

logger = logging.getLogger(__name__)

_PPE_COLORS = {
    "helmet": (0, 200, 0),     # green
    "vest": (200, 200, 0),     # cyan
    "gloves": (200, 100, 0),   # blue-ish
    "goggles": (0, 200, 200),  # yellow
    "boots": (150, 100, 50),   # teal
}

_VIOLATION_COLOR = (0, 0, 220)  # red for missing PPE


class PPEModule(DetectionModule):
    """
    PPE compliance module.
    Loads a dedicated YOLO model trained on PPE classes and checks
    each tracked person for missing required items.
    """

    module_id = "ppe"
    display_name = "PPE Compliance"
    description = "Detects PPE items (helmet, vest, gloves, goggles, boots) and flags violations."

    @property
    def requires_model(self) -> bool:
        return True

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence: float = 0.50,
        required_items: Optional[list[str]] = None,
    ) -> None:
        super().__init__()
        self._config = {
            "model_path": model_path or os.path.join(settings.models_dir, "yolov8s_ppe.pt"),
            "confidence": confidence,
            "required_items": required_items or ["helmet", "vest"],
        }
        self._model = None

    def load(self) -> None:
        """Load the PPE YOLO model."""
        model_path = self._config["model_path"]
        if not os.path.isfile(model_path):
            logger.warning("PPEModule: model not found at %s — module will be inactive", model_path)
            self._loaded = True  # Mark loaded but model=None; process() will return empty
            return

        try:
            from ultralytics import YOLO
            import torch
            import numpy as np

            self._model = YOLO(model_path)
            if torch.cuda.is_available():
                self._model.predict(
                    source=np.zeros((640, 640, 3), dtype=np.uint8),
                    device="cuda",
                    half=True,
                    verbose=False,
                )
            self._loaded = True
            logger.info("PPEModule: loaded model from %s", model_path)
        except Exception as exc:
            logger.error("PPEModule: failed to load model: %s", exc)
            self._model = None
            self._loaded = True

    def unload(self) -> None:
        """Release model and free VRAM."""
        self._model = None
        self._loaded = False

    def process(self, ctx: FrameContext) -> ModuleResult:
        """Run PPE detection and check compliance for each tracked person."""
        result = ModuleResult(module_id=self.module_id)

        if not self._loaded or self._model is None or not ctx.tracks:
            return result

        import torch

        try:
            preds = self._model.predict(
                source=ctx.frame,
                conf=self._config["confidence"],
                device="cuda" if torch.cuda.is_available() else "cpu",
                half=torch.cuda.is_available(),
                verbose=False,
            )
        except Exception as exc:
            logger.error("PPEModule: inference error: %s", exc)
            return result

        if not preds or len(preds[0].boxes) == 0:
            # No PPE detected — everyone is in violation
            return self._check_violations(ctx, {}, result)

        # Map detected PPE items to nearest person
        # person_ppe: {track_id: set of detected PPE class names}
        person_ppe: dict[int, set[str]] = {t.track_id: set() for t in ctx.tracks}

        boxes = preds[0].boxes
        for i in range(len(boxes)):
            bbox = tuple(int(v) for v in boxes.xyxy[i].tolist())
            conf = float(boxes.conf[i])
            cls_id = int(boxes.cls[i])
            class_name = preds[0].names.get(cls_id, "unknown").lower()

            # Annotate PPE detection
            color = _PPE_COLORS.get(class_name, (0, 200, 0))
            result.detections.append(ModuleDetection(
                bbox=bbox,
                label=f"{class_name} {conf:.2f}",
                confidence=conf,
                color_bgr=color,
            ))

            # Associate with nearest person
            best_tid = self._find_nearest_person(bbox, ctx.tracks)
            if best_tid is not None:
                person_ppe[best_tid].add(class_name)

        return self._check_violations(ctx, person_ppe, result)

    def _check_violations(
        self,
        ctx: FrameContext,
        person_ppe: dict[int, set[str]],
        result: ModuleResult,
    ) -> ModuleResult:
        """Check each person for missing required PPE items."""
        required = set(self._config["required_items"])

        for track in ctx.tracks:
            detected = person_ppe.get(track.track_id, set())
            missing = required - detected
            if missing:
                missing_str = ", ".join(sorted(missing))
                global_id = ctx.global_ids.get(track.track_id)
                label = f"PPE: missing {missing_str}"

                result.detections.append(ModuleDetection(
                    bbox=track.bbox,
                    label=label,
                    confidence=1.0,
                    color_bgr=_VIOLATION_COLOR,
                ))

                # Generate alert
                from engine.vision.weapon import WeaponAlert  # Reuse alert structure

                alert = WeaponAlert(
                    cam_id=ctx.cam_id,
                    class_name=f"PPE violation: missing {missing_str}",
                    confidence=1.0,
                    bbox=track.bbox,
                    threat_level="MEDIUM",
                    holder_track_id=track.track_id,
                    holder_global_id=global_id,
                )
                result.alerts.append(alert)

        return result

    @staticmethod
    def _find_nearest_person(
        ppe_bbox: tuple[int, int, int, int],
        tracks: list,
    ) -> Optional[int]:
        """Find the track_id of the person nearest to a PPE detection."""
        cx = (ppe_bbox[0] + ppe_bbox[2]) / 2
        cy = (ppe_bbox[1] + ppe_bbox[3]) / 2

        best_tid = None
        best_dist = float("inf")
        for track in tracks:
            px = (track.bbox[0] + track.bbox[2]) / 2
            py = (track.bbox[1] + track.bbox[3]) / 2
            dist = math.hypot(cx - px, cy - py)
            # PPE should be near/within the person bbox
            if dist < best_dist:
                best_dist = dist
                best_tid = track.track_id

        # Only associate if reasonably close
        if best_dist > 400:
            return None
        return best_tid

    def update_config(self, new_config: dict) -> None:
        """Update config — handles required_items as either list or comma-separated string."""
        if "required_items" in new_config and isinstance(new_config["required_items"], str):
            new_config["required_items"] = [
                item.strip() for item in new_config["required_items"].split(",") if item.strip()
            ]
        self._config.update(new_config)
