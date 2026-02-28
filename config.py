from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


SourceType = Literal["webcam", "video"]
Point = Tuple[int, int]


@dataclass
class VideoConfig:
    source_type: SourceType = field(
        default_factory=lambda: os.getenv("VIDEO_SOURCE_TYPE", "webcam")
    )
    webcam_index: int = field(
        default_factory=lambda: int(os.getenv("VIDEO_WEBCAM_INDEX", "0"))
    )
    video_path: Path | None = field(
        default_factory=lambda: Path(os.getenv("VIDEO_PATH")) if os.getenv("VIDEO_PATH") else None
    )
    frame_width: int | None = field(
        default_factory=lambda: int(os.getenv("VIDEO_FRAME_WIDTH", "640"))
    )
    frame_height: int | None = field(
        default_factory=lambda: int(os.getenv("VIDEO_FRAME_HEIGHT", "360"))
    )
    frame_skip: int = field(
        default_factory=lambda: int(os.getenv("VIDEO_FRAME_SKIP", "0"))
    )


@dataclass
class ZoneConfig:
    id: str
    label: str
    polygon: List[Point]


@dataclass
class ModelConfig:
    model_name: str = field(
        default_factory=lambda: os.getenv("MODEL_NAME", "yolov8n.pt")
    )
    confidence_threshold: float = field(
        default_factory=lambda: float(os.getenv("MODEL_CONFIDENCE", "0.4"))
    )
    iou_threshold: float = field(
        default_factory=lambda: float(os.getenv("MODEL_IOU", "0.45"))
    )
    max_det: int = field(
        default_factory=lambda: int(os.getenv("MODEL_MAX_DET", "20"))
    )
    imgsz: int = field(
        default_factory=lambda: int(os.getenv("MODEL_IMGSZ", "640"))
    )
    reid_stitch_enabled: bool = field(
        default_factory=lambda: os.getenv("REID_STITCH_ENABLED", "True").lower() == "true"
    )
    reid_ttl_seconds: float = field(
        default_factory=lambda: float(os.getenv("REID_TTL_SECONDS", "15.0"))
    )
    reid_min_similarity: float = field(
        default_factory=lambda: float(os.getenv("REID_MIN_SIMILARITY", "0.60"))
    )


@dataclass
class AlertConfig:
    log_dir: Path = field(
        default_factory=lambda: Path(os.getenv("ALERT_LOG_DIR", "logs"))
    )
    snapshots_dir: Path = field(
        default_factory=lambda: Path(os.getenv("ALERT_SNAPSHOTS_DIR", "snapshots"))
    )
    duplicate_suppression_seconds: int = field(
        default_factory=lambda: int(os.getenv("ALERT_COOLDOWN_SECONDS", "10"))
    )
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "")
    )
    camera_id: str = field(
        default_factory=lambda: os.getenv("CAMERA_ID", "cam_01")
    )


@dataclass
class AppConfig:
    video: VideoConfig = field(default_factory=VideoConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    alert: AlertConfig = field(default_factory=AlertConfig)
    zones: List[ZoneConfig] = field(default_factory=list)


def _load_zones() -> List[ZoneConfig]:
    """Load zones from zones.json in the project root, or return the default zone."""
    import json
    zones_file = Path(__file__).parent / "zones.json"
    if zones_file.exists():
        try:
            with open(zones_file, encoding="utf-8") as f:
                data = json.load(f)
            return [
                ZoneConfig(id=z["id"], label=z["label"], polygon=[(p[0], p[1]) for p in z["polygon"]])
                for z in data
            ]
        except Exception:
            pass  # Fall through to default on any parse error
    # Hardcoded fallback
    return [
        ZoneConfig(id="zone_1", label="Entrance", polygon=[(100, 80), (540, 80), (540, 300), (100, 300)])
    ]


def load_config() -> AppConfig:
    """Return configured settings loaded from env vars mapping directly to dataclasses."""
    return AppConfig(zones=_load_zones())
