from __future__ import annotations

import csv
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import cv2

from Core_AI.config import AlertConfig
from Core_AI.db import init_db, insert_event
from Core_AI.utils.logging_utils import get_logger


logger = get_logger(__name__)


@dataclass
class AlertEvent:
    timestamp: datetime
    track_id: int
    zone_id: str
    zone_label: str


@dataclass
class AlertManager:
    config: AlertConfig
    _last_alerts: Dict[Tuple[int, str], datetime] = field(default_factory=dict)
    _log_file: Path = field(init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.config.log_dir.mkdir(parents=True, exist_ok=True)
        self.config.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self.config.log_dir / "alerts.csv"

        # Write CSV header if file doesn't exist yet
        if not self._log_file.exists():
            with open(self._log_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Track_ID", "Zone_ID", "Zone_Label", "Snapshot_Path"])

    def handle_alerts(self, events: Iterable[AlertEvent], frame) -> None:
        rows_to_write: List[list] = []
        
        for event in events:
            key = (event.track_id, event.zone_id)
            now = event.timestamp
            with self._lock:
                last = self._last_alerts.get(key)
                if last and now - last < timedelta(seconds=self.config.duplicate_suppression_seconds):
                    continue
                self._last_alerts[key] = now

            timestamp_str = now.strftime("%Y%m%d_%H%M%S")
            snapshot_name = f"alert_{event.zone_id}_id{event.track_id}_{timestamp_str}.jpg"
            snapshot_path = self.config.snapshots_dir / snapshot_name

            # CLI Log
            logger.info(
                "Intrusion detected | zone=%s (%s) track_id=%s snapshot=%s",
                event.zone_id,
                event.zone_label,
                event.track_id,
                snapshot_path,
            )

            # Save visual snapshot in background thread to avoid blocking
            _frame_copy = frame.copy()
            _sp = str(snapshot_path)
            threading.Thread(
                target=_save_snapshot,
                args=(_frame_copy, _sp),
                daemon=True,
            ).start()

            rows_to_write.append([
                now.isoformat(),
                event.track_id,
                event.zone_id,
                event.zone_label,
                str(snapshot_path),
            ])

            # DB insert in background thread
            threading.Thread(
                target=insert_event,
                kwargs=dict(
                    db_url=self.config.database_url,
                    camera_id=self.config.camera_id,
                    object_id=event.track_id,
                    zone=event.zone_label,
                    ts=now,
                    snapshot_path=str(snapshot_path),
                ),
                daemon=True,
            ).start()

            # Windows Desktop Notification (IMP-14)
            def _show_toast():
                try:
                    from win10toast import ToastNotifier
                    toaster = ToastNotifier()
                    toaster.show_toast(
                        "SENTINAL Intrusion Alert",
                        f"Movement detected in {event.zone_label} (ID: {event.track_id})",
                        icon_path=None,
                        duration=5,
                        threaded=True
                    )
                except ImportError:
                    pass
                except Exception as exc:
                    logger.debug("Desktop notification failed: %s", exc)

            threading.Thread(target=_show_toast, daemon=True).start()

        # Batch write all rows to CSV in a single open()
        if rows_to_write:
            try:
                with open(self._log_file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows_to_write)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to write to alert log CSV: %s", exc)


def _save_snapshot(frame, path: str) -> None:
    try:
        cv2.imwrite(path, frame)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write snapshot %s: %s", path, exc)
