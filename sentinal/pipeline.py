from __future__ import annotations

from typing import Generator, List, Tuple

import cv2
import numpy as np

from config import AlertConfig, AppConfig, ModelConfig, VideoConfig
from sentinal.alerts import AlertEvent, AlertManager
from sentinal.id_stitcher import StitcherConfig, TrackIdStitcher
from sentinal.tracker import ObjectTracker
from sentinal.video_source import Frame, VideoSource
from sentinal.zones import ZoneEvent, ZoneManager
from sentinal.utils.drawing import draw_overlays
from sentinal.utils.logging_utils import get_logger


logger = get_logger(__name__)


class SurveillancePipeline:
    """End-to-end surveillance pipeline for a single video source."""

    def __init__(self, config: AppConfig) -> None:
        self._video_cfg: VideoConfig = config.video
        self._model_cfg: ModelConfig = config.model
        self._alert_cfg: AlertConfig = config.alert

        self._source = VideoSource(self._video_cfg)
        self._tracker = ObjectTracker(self._model_cfg)
        self._stitcher = TrackIdStitcher(
            StitcherConfig(
                enabled=getattr(self._model_cfg, "reid_stitch_enabled", True),
                ttl_seconds=float(getattr(self._model_cfg, "reid_ttl_seconds", 15.0)),
                min_similarity=float(getattr(self._model_cfg, "reid_min_similarity", 0.60)),
                ema_alpha=float(getattr(self._model_cfg, "reid_ema_alpha", 0.90)),
            )
        )
        self._zones = ZoneManager(config.zones)
        self._alerts = AlertManager(self._alert_cfg)
        self._frame_skip = max(0, self._video_cfg.frame_skip)
        
        from sentinal.db import init_db
        init_db(self._alert_cfg.database_url)

    def frames(self) -> Generator[Tuple[Frame, List[dict], List[ZoneEvent]], None, None]:
        """Generator yielding processed frames, tracks, and new zone events."""
        import time
        frame_index = 0
        target_w = self._video_cfg.frame_width
        target_h = self._video_cfg.frame_height
        t_last = time.monotonic()
        smooth_fps = 0.0
        _ALPHA = 0.1  # EMA smoothing factor

        with self._source:
            while True:
                ok, frame = self._source.read()
                if not ok or frame is None:
                    logger.info("End of video or failed to read frame.")
                    break

                if self._frame_skip and frame_index % (self._frame_skip + 1) != 0:
                    frame_index += 1
                    continue

                if target_w is not None and target_h is not None:
                    if frame.shape[1] != target_w or frame.shape[0] != target_h:
                        frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

                tracks = self._tracker.track(frame)
                tracks = self._stitcher.assign(frame, tracks)
                events = self._zones.update(tracks)
                self._alerts.handle_alerts(
                    [
                        AlertEvent(
                            timestamp=e.timestamp,
                            track_id=e.track_id,
                            zone_id=e.zone_id,
                            zone_label=e.zone_label,
                        )
                        for e in events
                    ],
                    frame,
                )

                t_now = time.monotonic()
                instant_fps = 1.0 / max(1e-5, t_now - t_last)
                t_last = t_now
                # Exponential Moving Average for smooth FPS display
                smooth_fps = _ALPHA * instant_fps + (1.0 - _ALPHA) * smooth_fps if smooth_fps > 0 else instant_fps

                display_frame = draw_overlays(frame.copy(), tracks, self._zones, fps=smooth_fps)

                # Push encoded frame to shared MJPEG buffer (backend stream)
                try:
                    from backend.services.video_service import push_frame
                    ret, buf = cv2.imencode(".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        push_frame(buf.tobytes())
                except Exception:  # noqa: BLE001
                    pass  # Running standalone without backend — skip silently

                yield display_frame, tracks, events
                frame_index += 1

