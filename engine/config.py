"""
SENTINAL v2 — Configuration System
Loads all settings from .env via Pydantic BaseSettings.
Never hardcode values — everything goes through this module.
"""

import secrets
from typing import ClassVar

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All runtime configuration for SENTINAL v2, loaded from .env."""

    # Internal constants
    _MAX_CAMERAS: ClassVar[int] = 16

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175"
    cors_allow_origin_regex: str = r"^https?://192\.168\.\d+\.\d+(:\d+)?$"

    # Models
    yolo_model: str = "yolo11l.pt"
    yolo_conf: float = 0.45
    yolo_iou: float = 0.50
    reid_model: str = "osnet_ain_x1_0_msmt17_256x128_amsgrad_ep50_lr0.0015_coslr_b64_fb10_softmax_labsmth_flip_jitter.pth"
    reid_threshold: float = 0.62
    face_model: str = "buffalo_l"
    face_quality_threshold: float = 0.6
    face_match_threshold: float = 0.68  # Cosine similarity threshold for ArcFace
    tracker_device: str = "cuda"        # "cuda" or "cpu"

    # Paths
    models_dir: str = "models/"
    snapshots_dir: str = "data/snapshots/"
    zones_file: str = "data/zones.json"
    logs_dir: str = "data/logs/"

    # Database
    db_url: str = "sqlite:///data/sentinal.db"

    # Alerts
    alert_cooldown_seconds: int = 60
    alert_email_enabled: bool = False
    alert_email_smtp_host: str = ""
    alert_email_smtp_port: int = 587
    alert_email_sender: str = ""
    alert_email_password: str = ""
    alert_email_recipient: str = ""
    alert_webhook_enabled: bool = False
    alert_webhook_url: str = ""
    alert_telegram_enabled: bool = False
    alert_telegram_bot_token: str = ""
    alert_telegram_chat_id: str = ""

    # Anomaly thresholds
    loitering_seconds: int = 30
    crowd_threshold: int = 5
    violence_velocity_threshold: float = 0.4  # Movement magnitude relative to person height
    violence_proximity_threshold: float = 1.2 # Normalized distance (center-to-center / avg_height)
    violence_cooldown_seconds: int = 30

    # Stream
    stream_fps_target: int = 15
    stream_reconnect_error_threshold: int = 5

    # Performance tuning
    pipeline_process_every_n: int = 3     # Run AI on every Nth frame (1=every frame, 3=skip 2, etc.)
    pipeline_reid_every_n: int = 3        # Run Re-ID every Nth AI frame (saves GPU on heavy model)
    pipeline_face_every_n: int = 5        # Run face recognition every Nth AI frame
    yolo_imgsz: int = 480                 # YOLO input resolution (lower = faster, 480 is good balance)
    mjpeg_jpeg_quality: int = 70          # JPEG encoding quality (60-85 range)

    # Startup cameras — JSON array string loaded from .env
    # Example .env entry (no quotes around the array):
    #   STARTUP_CAMERAS=[{"cam_id":"cam_0","url":"http://192.168.1.x:8080/video","label":"Front Door"}]
    # Leave empty (default) to add cameras only via the UI or cameras.json restore.
    startup_cameras: str = ""

    # Auth (JWT)
    auth_username: str = "admin"
    auth_password_hash: str = "$2b$12$x37lhM/Khg6Yli1gFgEmDeMhLjPWCfj55jCnY33CLdE8NCDDBR35u" # hash of 'sentinal'
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Raise error if default insecure key is used."""
        if v == "change-me-in-production":
            # In a production-ready system, we should either raise an error
            # or auto-generate a secure random one for this session only.
            # We raise an error to force the user to be explicit in their .env.
            raise ValueError(
                "SECURITY ERROR: 'jwt_secret_key' must be changed from the default value in .env. "
                "You can generate a new one with: python -c 'import secrets; print(secrets.token_urlsafe(64))'"
            )
        return v

    # Module defaults
    module_weapon_enabled: bool = True
    module_weapon_model: str = "yolov8s_weapons.pt"
    module_weapon_confidence: float = 0.45

    module_ppe_enabled: bool = False
    module_ppe_model: str = "yolov8s_ppe.pt"
    module_ppe_confidence: float = 0.50
    module_ppe_required_items: str = "helmet,vest"

    module_anomaly_enabled: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
