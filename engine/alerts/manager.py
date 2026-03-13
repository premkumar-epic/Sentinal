import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional
from uuid import uuid4

import numpy as np

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Alert type enumeration for different surveillance events."""

    INTRUSION = "intrusion"
    WEAPON = "weapon"
    LOITERING = "loitering"
    CROWDING = "crowding"
    VIOLENCE = "violence"
    FACE_MATCH = "face_match"
    IDENTITY_REGISTERED = "identity_registered"


@dataclass
class Alert:
    """Data class representing an alert event."""

    alert_id: str = field(default_factory=lambda: str(uuid4()))
    alert_type: AlertType = AlertType.INTRUSION
    cam_id: str = ""
    zone_id: Optional[str] = None
    track_ids: list[int] = field(default_factory=list)
    global_ids: list[str] = field(default_factory=list)
    name: Optional[str] = None
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    snapshot_path: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class AlertManager:
    """
    Central alert dispatcher with deduplication and cooldown logic.

    Handles alert creation from pipeline events, applies cooldown rules,
    and dispatches to async handlers (DB, WebSocket, email/webhook) via daemon threads.
    """

    def __init__(
        self,
        ws_broadcaster: Optional[Callable] = None,
        db_insert_fn: Optional[Callable] = None,
        snapshot_fn: Optional[Callable] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize AlertManager.

        Args:
            ws_broadcaster: Async callable(payload_dict) to push WebSocket messages.
            db_insert_fn: Async callable(alert: Alert) to insert alert into database.
            snapshot_fn: Callable(frame, cam_id, alert_id) -> str to save JPEG snapshot.
            loop: Asyncio event loop for running async functions from threads.
                  If None, will try to get the running loop at dispatch time.
        """
        self.ws_broadcaster = ws_broadcaster
        self.db_insert_fn = db_insert_fn
        self.snapshot_fn = snapshot_fn
        self.loop = loop

        # Managed thread pool for dispatch (A1)
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="AlertDisp")

        # Thread-safe cooldown tracking
        self._cooldowns: dict[str, float] = {}
        self._lock = threading.RLock()

    def stop(self) -> None:
        """Shutdown the executor pool."""
        self._executor.shutdown(wait=True)
        logger.info("AlertManager executor shut down.")

    def dispatch(
        self, event: object, frame: Optional[np.ndarray], cam_id: str
    ) -> None:
        """
        Dispatch an alert event for handling.

        Builds an Alert from the event, checks cooldown, and spawns a daemon thread
        to handle I/O (snapshot, DB insert, WebSocket push). Never blocks the caller.

        Args:
            event: Event object with alert attributes (duck-typed).
            frame: Frame image (numpy array) or None.
            cam_id: Camera ID string.
        """
        # Build Alert from event using duck-typing
        alert = self._build_alert_from_event(event, cam_id)

        # Determine cooldown behavior
        if alert.alert_type == AlertType.WEAPON:
            # Weapon alerts bypass cooldown
            logger.debug(
                "Weapon alert from %s: %s", cam_id, getattr(event, 'class_name', 'unknown')
            )
            self._spawn_dispatch_thread(alert, event, frame, cam_id)
        elif alert.alert_type == AlertType.FACE_MATCH:
            # Face match alerts use 300s cooldown per global_id
            cooldown_key = f"{cam_id}:{alert.global_ids[0] if alert.global_ids else ''}:face_match"
            if self._check_and_update_cooldown(cooldown_key, 300):
                logger.debug(
                    "Face match alert: %s on %s, dispatching", alert.name, cam_id
                )
                self._spawn_dispatch_thread(alert, event, frame, cam_id)
            else:
                logger.info(
                    "Face match alert on cooldown for %s", cooldown_key
                )
        else:
            # Standard alerts use 60s cooldown per (cam_id, zone_id, track_id, alert_type)
            cooldown_key = f"{cam_id}:{alert.zone_id}:{alert.track_ids[0] if alert.track_ids else None}:{alert.alert_type.value}"
            if self._check_and_update_cooldown(cooldown_key, 60):
                logger.debug(
                    "%s alert from %s, dispatching", alert.alert_type.value, cam_id
                )
                self._spawn_dispatch_thread(alert, event, frame, cam_id)
            else:
                logger.info("Alert on cooldown for key: %s", cooldown_key)

    def _build_alert_from_event(self, event: object, cam_id: str) -> Alert:
        """
        Build an Alert dataclass from an event object using duck-typing.

        Args:
            event: Event object with arbitrary attributes.
            cam_id: Camera ID.

        Returns:
            Fully populated Alert instance.
        """
        # Detect alert type
        if hasattr(event, "alert_type"):
            alert_type = event.alert_type
        elif hasattr(event, "zone_id"):
            alert_type = AlertType.INTRUSION
        else:
            alert_type = AlertType.WEAPON

        # Extract fields from event
        zone_id = getattr(event, "zone_id", None)
        track_id = getattr(event, "track_id", None)
        global_id = getattr(event, "global_id", None)
        name = getattr(event, "name", None)
        confidence = getattr(event, "confidence", 0.0)
        metadata = getattr(event, "metadata", {})

        # Build track_ids and global_ids lists
        track_ids = [track_id] if track_id is not None else []
        global_ids = [global_id] if global_id is not None else []

        # Weapon-specific: extract holder info and threat level
        if alert_type == AlertType.WEAPON:
            holder_tid = getattr(event, "holder_track_id", None)
            holder_gid = getattr(event, "holder_global_id", None)
            threat_level = getattr(event, "threat_level", "UNKNOWN")
            track_ids = [holder_tid] if holder_tid is not None else []
            global_ids = [holder_gid] if holder_gid is not None else []
            metadata = {
                "threat_level": threat_level,
                "weapon_class": getattr(event, "class_name", ""),
                "holder_track_id": holder_tid,
                "holder_global_id": holder_gid,
            }

        return Alert(
            alert_type=alert_type,
            cam_id=cam_id,
            zone_id=zone_id,
            track_ids=track_ids,
            global_ids=global_ids,
            name=name,
            confidence=confidence,
            metadata=metadata,
        )

    def _check_and_update_cooldown(self, key: str, cooldown_seconds: int) -> bool:
        """
        Check if a cooldown key is active; update if not.

        Uses time.monotonic() for timing. Thread-safe via RLock.

        Args:
            key: Unique cooldown identifier.
            cooldown_seconds: Cooldown duration in seconds.

        Returns:
            True if not on cooldown (dispatch should proceed), False otherwise.
        """
        now = time.monotonic()
        with self._lock:
            # Prune expired entries when dict grows large
            if len(self._cooldowns) > 500:
                expired = [k for k, exp in self._cooldowns.items() if exp <= now]
                for k in expired:
                    del self._cooldowns[k]

            if key in self._cooldowns:
                if now < self._cooldowns[key]:
                    return False
            self._cooldowns[key] = now + cooldown_seconds
            return True

    def _spawn_dispatch_thread(
        self, alert: Alert, event: object, frame: Optional[np.ndarray], cam_id: str
    ) -> None:
        """
        Submit a task to the thread pool to handle alert I/O.

        Task handles snapshot saving, DB insert, and WebSocket push in order.
        Never blocks the caller.

        Args:
            alert: Alert instance to dispatch.
            event: Original event object (for extracting extra data like class_name).
            frame: Frame image or None.
            cam_id: Camera ID.
        """
        self._executor.submit(
            self._dispatch_async_handlers,
            alert, event, frame, cam_id
        )

    def _dispatch_async_handlers(
        self, alert: Alert, event: object, frame: Optional[np.ndarray], cam_id: str
    ) -> None:
        """
        Execute all async handlers for an alert in sequence.

        Runs in a daemon thread. Handles snapshot, DB insert, and WebSocket push.

        Args:
            alert: Alert instance.
            event: Original event object.
            frame: Frame image or None.
            cam_id: Camera ID.
        """
        try:
            # Step 1: Save snapshot
            if self.snapshot_fn is not None and frame is not None:
                try:
                    alert.snapshot_path = self.snapshot_fn(frame, cam_id, alert.alert_id)
                except Exception as e:
                    logger.warning("Failed to save snapshot: %s", e)

            # Step 2: Insert into database
            if self.db_insert_fn is not None:
                try:
                    loop = self.loop or asyncio.get_running_loop()
                    future = asyncio.run_coroutine_threadsafe(
                        self.db_insert_fn(alert), loop
                    )
                    future.result(timeout=5)
                except Exception as e:
                    logger.warning("Failed to insert alert into DB: %s", e)

            # Step 3: Push WebSocket message
            if self.ws_broadcaster is not None:
                try:
                    payload = self._build_websocket_payload(alert, event)
                    loop = self.loop or asyncio.get_running_loop()
                    future = asyncio.run_coroutine_threadsafe(
                        self.ws_broadcaster(payload), loop
                    )
                    future.result(timeout=5)
                except Exception as e:
                    logger.warning("Failed to broadcast alert to WebSocket: %s", e)

            # Step 4: Send Email (if enabled in settings)
            from engine.alerts.email import send_alert_email
            try:
                loop = self.loop or asyncio.get_running_loop()
                # send_alert_email handles settings check internally
                future = asyncio.run_coroutine_threadsafe(
                    send_alert_email(alert, alert.snapshot_path or ""), loop
                )
                # We don't wait for email to finish to avoid blocking the thread too long
            except Exception as e:
                logger.warning("Failed to initiate alert email: %s", e)

            # Step 5: Post Webhook (if enabled in settings)
            from engine.alerts.webhook import post_webhook
            try:
                loop = self.loop or asyncio.get_running_loop()
                # post_webhook handles settings check internally
                future = asyncio.run_coroutine_threadsafe(
                    post_webhook(alert), loop
                )
            except Exception as e:
                logger.warning("Failed to initiate alert webhook: %s", e)

            # Step 6: Send Telegram notification (if enabled in settings)
            from engine.alerts.telegram import send_telegram_alert
            try:
                loop = self.loop or asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    send_telegram_alert(alert, alert.snapshot_path or ""), loop
                )
            except Exception as e:
                logger.warning("Failed to initiate Telegram alert: %s", e)

        except Exception as e:
            logger.warning("Unexpected error in alert dispatch thread: %s", e)

    def _build_websocket_payload(self, alert: Alert, event: object) -> dict:
        """
        Build WebSocket payload for alert broadcast.

        Args:
            alert: Alert instance.
            event: Original event object.

        Returns:
            Dictionary payload for WebSocket broadcast.
        """
        if alert.alert_type == AlertType.WEAPON:
            return {
                "type": "weapon_alarm",
                "cam_id": alert.cam_id,
                "class_name": getattr(event, "class_name", ""),
                "confidence": alert.confidence,
                "threat_level": alert.metadata.get("threat_level", "UNKNOWN"),
                "holder_track_id": alert.metadata.get("holder_track_id"),
                "holder_global_id": alert.metadata.get("holder_global_id"),
                "timestamp": alert.timestamp.isoformat(),
                "snapshot_url": alert.snapshot_path,
            }
        else:
            return {
                "type": "alert",
                "alert_type": alert.alert_type.value,
                "cam_id": alert.cam_id,
                "zone_label": getattr(event, "zone_label", None),
                "global_id": alert.global_ids[0] if alert.global_ids else None,
                "name": alert.name,
                "timestamp": alert.timestamp.isoformat(),
                "snapshot_url": alert.snapshot_path,
            }
