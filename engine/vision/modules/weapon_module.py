"""
SENTINAL v2 — Weapon Detection Module.
Uses a dedicated YOLOv8s weapon model if available, otherwise falls back
to filtering main YOLO detections (COCO keyword matching via WeaponDetector).
"""

import logging
import os
from typing import Optional

from engine.config import settings
from engine.vision.modules.base import DetectionModule, FrameContext, ModuleResult

logger = logging.getLogger(__name__)


class WeaponModule(DetectionModule):
    """
    Weapon detection module with dual-mode support:
    1. Dedicated YOLO model (yolov8s_weapons.pt) — best accuracy
    2. COCO fallback — filters main YOLO detections for weapon keywords
    """

    module_id = "weapon"
    display_name = "Weapon Detection"
    description = "Detects weapons (firearms, knives, blunt objects) and classifies threat level."

    @property
    def requires_model(self) -> bool:
        return True

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence: float = 0.45,
        confirmation_frames: int = 2,
    ) -> None:
        super().__init__()
        self._config = {
            "model_path": model_path or os.path.join(settings.models_dir, "yolov8s_weapons.pt"),
            "confidence": confidence,
            "confirmation_frames": confirmation_frames,
        }
        self._dedicated_model = None
        self._fallback_detector = None  # WeaponDetector instance for COCO fallback
        self._use_dedicated: bool = False

    def load(self) -> None:
        """Load weapon model. Tries dedicated model first, falls back to COCO filtering."""
        model_path = self._config["model_path"]

        if os.path.isfile(model_path):
            try:
                from ultralytics import YOLO
                self._dedicated_model = YOLO(model_path)
                # Warm up on CUDA with FP16
                import torch
                if torch.cuda.is_available():
                    self._dedicated_model.predict(
                        source=__import__("numpy").zeros((640, 640, 3), dtype=__import__("numpy").uint8),
                        device="cuda",
                        half=True,
                        verbose=False,
                    )
                self._use_dedicated = True
                logger.info("WeaponModule: loaded dedicated model from %s", model_path)
            except Exception as exc:
                logger.warning("WeaponModule: dedicated model failed (%s), using COCO fallback", exc)
                self._dedicated_model = None
                self._use_dedicated = False
        else:
            logger.info(
                "WeaponModule: dedicated model not found at %s — using COCO fallback",
                model_path,
            )
            self._use_dedicated = False

        # Always init fallback (used when dedicated model absent or for COCO-based detection)
        from engine.vision.weapon import WeaponDetector
        self._fallback_detector = WeaponDetector()

        self._loaded = True

    def unload(self) -> None:
        """Release model and free VRAM."""
        self._dedicated_model = None
        self._fallback_detector = None
        self._use_dedicated = False
        self._loaded = False

    def process(self, ctx: FrameContext) -> ModuleResult:
        """
        Run weapon detection on the frame.

        Dedicated model: runs separate inference on the frame.
        COCO fallback: filters ctx.detections for weapon keywords.
        """
        result = ModuleResult(module_id=self.module_id)

        if not self._loaded:
            return result

        if self._use_dedicated and self._dedicated_model is not None:
            return self._process_dedicated(ctx, result)
        elif self._fallback_detector is not None:
            return self._process_fallback(ctx, result)

        return result

    def _process_dedicated(self, ctx: FrameContext, result: ModuleResult) -> ModuleResult:
        """Run dedicated weapon YOLO model on the frame."""
        import torch

        try:
            preds = self._dedicated_model.predict(
                source=ctx.frame,
                conf=self._config["confidence"],
                device="cuda" if torch.cuda.is_available() else "cpu",
                half=torch.cuda.is_available(),
                verbose=False,
            )
            if preds and len(preds[0].boxes) > 0:
                boxes = preds[0].boxes
                for i in range(len(boxes)):
                    bbox = tuple(int(v) for v in boxes.xyxy[i].tolist())
                    conf = float(boxes.conf[i])
                    cls_id = int(boxes.cls[i])
                    class_name = preds[0].names.get(cls_id, "weapon")

                    from engine.vision.modules.base import ModuleDetection
                    from engine.vision.weapon import WeaponAlert, _classify_threat, _bbox_overlap, _bbox_center, _ASSOCIATION_MAX_DISTANCE
                    import math

                    threat = _classify_threat(class_name)
                    color = {
                        "CRITICAL": (0, 0, 255),
                        "HIGH": (0, 80, 255),
                        "MEDIUM": (0, 140, 255),
                    }.get(threat, (0, 220, 255))

                    result.detections.append(ModuleDetection(
                        bbox=bbox,
                        label=f"[{threat}] {class_name} {conf:.2f}",
                        confidence=conf,
                        color_bgr=color,
                    ))

                    # Associate with nearest person
                    holder_tid, holder_gid = None, None
                    if ctx.tracks:
                        for track in ctx.tracks:
                            if _bbox_overlap(bbox, track.bbox):
                                holder_tid = track.track_id
                                holder_gid = ctx.global_ids.get(track.track_id)
                                break
                        if holder_tid is None:
                            best_dist = float("inf")
                            for track in ctx.tracks:
                                cx1 = (bbox[0] + bbox[2]) / 2
                                cy1 = (bbox[1] + bbox[3]) / 2
                                cx2 = (track.bbox[0] + track.bbox[2]) / 2
                                cy2 = (track.bbox[1] + track.bbox[3]) / 2
                                dist = math.hypot(cx1 - cx2, cy1 - cy2)
                                if dist < best_dist:
                                    best_dist = dist
                                    holder_tid = track.track_id
                                    holder_gid = ctx.global_ids.get(track.track_id)
                            if best_dist > _ASSOCIATION_MAX_DISTANCE:
                                holder_tid, holder_gid = None, None

                    alert = WeaponAlert(
                        cam_id=ctx.cam_id,
                        class_name=class_name,
                        confidence=conf,
                        bbox=bbox,
                        threat_level=threat,
                        holder_track_id=holder_tid,
                        holder_global_id=holder_gid,
                    )
                    result.alerts.append(alert)

        except Exception as exc:
            logger.error("WeaponModule: dedicated model inference error: %s", exc)

        return result

    def _process_fallback(self, ctx: FrameContext, result: ModuleResult) -> ModuleResult:
        """Use existing WeaponDetector (COCO keyword filtering) on main YOLO detections."""
        alert = self._fallback_detector.check(
            ctx.detections, ctx.cam_id,
            tracks=ctx.tracks, global_ids=ctx.global_ids or None,
        )
        if alert is not None:
            result.alerts.append(alert)
            from engine.vision.modules.base import ModuleDetection
            threat_colors = {
                "CRITICAL": (0, 0, 255),
                "HIGH": (0, 80, 255),
                "MEDIUM": (0, 140, 255),
            }
            result.detections.append(ModuleDetection(
                bbox=alert.bbox,
                label=f"[{alert.threat_level}] {alert.class_name} {alert.confidence:.2f}",
                confidence=alert.confidence,
                color_bgr=threat_colors.get(alert.threat_level, (0, 220, 255)),
            ))
        return result

    def update_config(self, new_config: dict) -> None:
        """Update config. If model_path changes while loaded, a reload is needed."""
        self._config.update(new_config)
