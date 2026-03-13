"""
SENTINAL v2 — Asynchronous Email Alert Sender

Sends alert notifications via SMTP to configured recipients.
Uses aiosmtplib for non-blocking async SMTP operations.
Silent error handling ensures pipeline never crashes due to email failures.
"""

import logging
import os
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import aiosmtplib

from engine.alerts.manager import Alert
from engine.config import settings

logger = logging.getLogger(__name__)


async def send_alert_email(alert: Alert, snapshot_path: str) -> None:
    """
    Send an alert notification email asynchronously.

    Args:
        alert: Alert dataclass containing event details.
        snapshot_path: Path to JPEG snapshot file (may be empty or non-existent).

    Returns:
        None. Errors are logged but never raised (silent fail).

    Behavior:
        - Returns immediately with WARNING log if alert_email_enabled is False.
        - Sends email with subject: [SENTINAL] {ALERT_TYPE} — {CAM_ID} — {TIMESTAMP}
        - Includes plain text body with alert details.
        - Attaches JPEG snapshot if file exists and path is non-empty.
        - On SMTP/IO error: logs ERROR with exc_info but never raises (pipeline safe).
    """
    # Early return if email alerts are disabled
    if not settings.alert_email_enabled:
        logger.warning("Email alerts are disabled; skipping send_alert_email()")
        return

    # Validate SMTP configuration
    if not all(
        [
            settings.alert_email_smtp_host,
            settings.alert_email_sender,
            settings.alert_email_password,
            settings.alert_email_recipient,
        ]
    ):
        logger.warning(
            "Email configuration incomplete (missing SMTP host, sender, password, or recipient); skipping"
        )
        return

    try:
        # Build email message
        msg = MIMEMultipart()
        msg["Subject"] = (
            f"[SENTINAL] {str(alert.alert_type).upper()} — "
            f"{alert.cam_id} — {alert.timestamp.isoformat()}"
        )
        msg["From"] = settings.alert_email_sender
        msg["To"] = settings.alert_email_recipient

        # Build plain text body with alert details
        body_lines = [
            f"ALERT TYPE: {alert.alert_type.value.upper()}",
            f"CAMERA ID: {alert.cam_id}",
            f"TIMESTAMP: {alert.timestamp.isoformat()}",
            f"ZONE ID: {alert.zone_id if alert.zone_id else 'N/A'}",
            f"TRACK IDS: {', '.join(map(str, alert.track_ids)) if alert.track_ids else 'N/A'}",
            f"GLOBAL IDS: {', '.join(alert.global_ids) if alert.global_ids else 'N/A'}",
            f"PERSON NAME: {alert.name if alert.name else 'Unknown'}",
            f"CONFIDENCE: {alert.confidence:.2f}",
            f"ALERT ID: {alert.alert_id}",
        ]
        body_text = "\n".join(body_lines)
        msg.attach(MIMEText(body_text, "plain"))

        # Attach snapshot if it exists and path is non-empty
        if snapshot_path and os.path.isfile(snapshot_path):
            try:
                with open(snapshot_path, "rb") as f:
                    image_data = f.read()
                image = MIMEImage(image_data, name=Path(snapshot_path).name)
                msg.attach(image)
                logger.debug("Attached snapshot: %s", snapshot_path)
            except OSError as e:
                logger.warning("Failed to attach snapshot %s: %s", snapshot_path, e)

        # Send email via aiosmtplib (non-blocking)
        async with aiosmtplib.SMTP(
            hostname=settings.alert_email_smtp_host,
            port=settings.alert_email_smtp_port,
        ) as smtp:
            await smtp.login(settings.alert_email_sender, settings.alert_email_password)
            await smtp.send_message(msg)

        logger.info(
            "Alert email sent for %s (cam_id=%s, alert_id=%s)",
            alert.alert_type.value, alert.cam_id, alert.alert_id
        )

    except Exception as e:
        logger.error(
            "Failed to send alert email for %s (cam_id=%s): %s",
            alert.alert_type.value, alert.cam_id, e,
            exc_info=True,
        )
        # Never raise — pipeline must not crash due to email failures
