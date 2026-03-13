"""
SENTINAL v2 — Telegram Alert Sender

Sends alert notifications to a Telegram chat via the Bot API.
Supports text messages with optional snapshot photo attachments.
Uses async httpx for non-blocking HTTP I/O. Silent fail on error.
"""

import logging
import os
from typing import Optional

import httpx

from engine.alerts.manager import Alert, AlertType
from engine.config import settings

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}"

# Severity emoji mapping
_SEVERITY_ICON = {
    AlertType.WEAPON: "\U0001f6a8",       # rotating light
    AlertType.VIOLENCE: "\U0001f6a8",
    AlertType.INTRUSION: "\u26a0\ufe0f",   # warning
    AlertType.CROWDING: "\U0001f465",       # busts in silhouette
    AlertType.LOITERING: "\U0001f440",      # eyes
    AlertType.FACE_MATCH: "\U0001f464",     # bust in silhouette
    AlertType.IDENTITY_REGISTERED: "\U0001f195",  # NEW
}


def _format_message(alert: Alert) -> str:
    """Build a Telegram-formatted alert message using MarkdownV2."""
    icon = _SEVERITY_ICON.get(alert.alert_type, "\u26a0\ufe0f")
    alert_label = alert.alert_type.value.upper().replace("_", " ")

    lines = [
        f"{icon} *{_escape_md(alert_label)}*",
        "",
        f"\U0001f4f9 *Camera:* `{_escape_md(alert.cam_id)}`",
    ]

    if alert.zone_id:
        lines.append(f"\U0001f4cd *Zone:* `{_escape_md(alert.zone_id)}`")

    if alert.name:
        lines.append(f"\U0001f464 *Person:* {_escape_md(alert.name)}")
    elif alert.global_ids:
        lines.append(f"\U0001f194 *ID:* `{_escape_md(alert.global_ids[0])}`")

    if alert.confidence > 0:
        lines.append(f"\U0001f3af *Confidence:* {alert.confidence * 100:.0f}%")

    # Weapon-specific details
    if alert.alert_type == AlertType.WEAPON:
        weapon_class = alert.metadata.get("weapon_class", "")
        threat_level = alert.metadata.get("threat_level", "")
        if weapon_class:
            lines.append(f"\U0001f52b *Weapon:* {_escape_md(weapon_class)}")
        if threat_level:
            lines.append(f"\u2622\ufe0f *Threat:* {_escape_md(threat_level)}")

    lines.append("")
    lines.append(f"\U0001f552 `{_escape_md(alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'))}`")

    return "\n".join(lines)


def _escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"_*[]()~`>#+-=|{}.!\\"
    result = ""
    for ch in str(text):
        if ch in special:
            result += "\\" + ch
        else:
            result += ch
    return result


async def send_telegram_alert(alert: Alert, snapshot_path: Optional[str] = None) -> None:
    """
    Send an alert notification to Telegram.

    Sends a photo with caption if a snapshot exists, otherwise a text message.
    Returns silently on any error (pipeline must never crash).

    Args:
        alert: Alert dataclass containing event details.
        snapshot_path: Path to JPEG snapshot file (may be empty or non-existent).
    """
    if not settings.alert_telegram_enabled:
        return

    if not settings.alert_telegram_bot_token or not settings.alert_telegram_chat_id:
        logger.warning("Telegram config incomplete (missing bot_token or chat_id); skipping")
        return

    base_url = _TELEGRAM_API.format(token=settings.alert_telegram_bot_token)
    message_text = _format_message(alert)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # If snapshot exists, send as photo with caption
            if snapshot_path and os.path.isfile(snapshot_path):
                with open(snapshot_path, "rb") as f:
                    photo_data = f.read()

                response = await client.post(
                    f"{base_url}/sendPhoto",
                    data={
                        "chat_id": settings.alert_telegram_chat_id,
                        "caption": message_text,
                        "parse_mode": "MarkdownV2",
                    },
                    files={"photo": ("alert.jpg", photo_data, "image/jpeg")},
                )
            else:
                # Text-only message
                response = await client.post(
                    f"{base_url}/sendMessage",
                    json={
                        "chat_id": settings.alert_telegram_chat_id,
                        "text": message_text,
                        "parse_mode": "MarkdownV2",
                    },
                )

            if response.status_code == 200:
                logger.info(
                    "Telegram alert sent: %s (cam=%s, alert_id=%s)",
                    alert.alert_type.value, alert.cam_id, alert.alert_id,
                )
            else:
                logger.error(
                    "Telegram API error %d: %s",
                    response.status_code, response.text,
                )

    except httpx.TimeoutException:
        logger.error("Telegram send timeout (10s) for alert_id=%s", alert.alert_id)
    except Exception as e:
        logger.error(
            "Telegram send failed for alert_id=%s: %s",
            alert.alert_id, e, exc_info=True,
        )
