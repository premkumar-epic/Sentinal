"""
SENTINAL v2 — Anomaly Detection Module.
Wraps the existing rule-based AnomalyDetector as a DetectionModule.
No model required — purely rule-based (loitering, crowding, etc.).
"""

import logging

from engine.vision.modules.base import DetectionModule, FrameContext, ModuleResult

logger = logging.getLogger(__name__)


class AnomalyModule(DetectionModule):
    """
    Rule-based anomaly detection module.
    Wraps engine.vision.anomaly.AnomalyDetector — no GPU model needed.
    """

    module_id = "anomaly"
    display_name = "Anomaly Detection"
    description = "Rule-based detection of loitering, crowding, and unusual behavior patterns."

    @property
    def requires_model(self) -> bool:
        return False

    def __init__(self) -> None:
        super().__init__()
        self._detector = None

    def load(self) -> None:
        """Create the AnomalyDetector instance."""
        try:
            from engine.vision.anomaly import AnomalyDetector
            self._detector = AnomalyDetector()
            self._loaded = True
            logger.info("AnomalyModule: loaded (rule-based, no GPU)")
        except Exception as exc:
            logger.error("AnomalyModule: failed to load: %s", exc)
            self._loaded = False

    def unload(self) -> None:
        """Destroy the AnomalyDetector instance."""
        self._detector = None
        self._loaded = False

    def process(self, ctx: FrameContext) -> ModuleResult:
        """Run anomaly detection on current tracks and zone events."""
        result = ModuleResult(module_id=self.module_id)

        if not self._loaded or self._detector is None:
            return result

        try:
            anomalies = self._detector.update(ctx.tracks, ctx.zone_events)
            for anomaly in anomalies:
                result.alerts.append(anomaly)
        except Exception as exc:
            logger.error("AnomalyModule: process error: %s", exc)

        return result
