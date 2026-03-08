"""
SENTINAL v2 — Configuration System
Loads all settings from .env via Pydantic BaseSettings.
Never hardcode values — everything goes through this module.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All runtime configuration for SENTINAL v2, loaded from .env."""

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Models
    yolo_model: str = "yolo11m.pt"
    yolo_conf: float = 0.50
    yolo_iou: float = 0.45
    reid_model: str = "osnet_ain_x1_0_msmt17.pth"
    reid_threshold: float = 0.80
    face_model: str = "buffalo_l"
    face_quality_threshold: float = 0.6

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

    # Anomaly thresholds
    loitering_seconds: int = 30
    crowd_threshold: int = 5

    # Stream
    stream_fps_target: int = 15
    stream_reconnect_error_threshold: int = 5

    # Startup cameras — JSON array string loaded from .env
    # Example .env entry (no quotes around the array):
    #   STARTUP_CAMERAS=[{"cam_id":"cam_0","url":"http://192.168.1.x:8080/video","label":"Front Door"}]
    # Leave empty (default) to add cameras only via the UI or cameras.json restore.
    startup_cameras: str = ""

    # Auth (JWT)
    auth_username: str = "admin"
    auth_password: str = "sentinal"
    jwt_secret_key: str = "change-me-in-production"
    jwt_expire_minutes: int = 1440  # 24 hours

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
