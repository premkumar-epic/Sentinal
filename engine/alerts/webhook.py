"""
Webhook alert dispatcher for SENTINAL v2.

Sends alert events as JSON POST requests to a configured external URL.
Uses async httpx for non-blocking HTTP I/O. Silent fail on error.
"""

import logging
from datetime import datetime

import httpx

from engine.alerts.manager import Alert
from engine.config import settings

logger = logging.getLogger(__name__)


async def post_webhook(alert: Alert) -> None:
    """
    POST an alert to a webhook URL as JSON.

    Only sends if both alert_webhook_enabled and alert_webhook_url are configured.
    Serializes the alert dataclass to a dict with JSON-compatible types:
    - datetime fields converted to ISO 8601 strings
    - enum values converted to their string value
    - tuples converted to lists for JSON compatibility

    Catches all exceptions and logs them without raising — pipeline must never crash.

    Args:
        alert: Alert dataclass instance to dispatch.

    Returns:
        None. Silent fail on any error (logs ERROR, does not re-raise).
    """
    # Early return if webhook is disabled or URL not configured
    if not settings.alert_webhook_enabled or not settings.alert_webhook_url:
        return

    try:
        # Serialize alert to JSON-compatible dict
        payload = _serialize_alert(alert)

        # POST to webhook URL with 5 second timeout
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                settings.alert_webhook_url,
                json=payload,
            )
            response.raise_for_status()

        logger.debug(
            f"Webhook POST successful: {settings.alert_webhook_url}, "
            f"alert_id={alert.alert_id}, status={response.status_code}"
        )

    except httpx.TimeoutException:
        logger.error(
            f"Webhook POST timeout (5s): {settings.alert_webhook_url}, "
            f"alert_id={alert.alert_id}"
        )
    except httpx.HTTPError as e:
        logger.error(
            f"Webhook HTTP error: {settings.alert_webhook_url}, "
            f"alert_id={alert.alert_id}, error={e}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"Webhook POST failed unexpectedly: alert_id={alert.alert_id}, error={e}",
            exc_info=True,
        )


def _serialize_alert(alert: Alert) -> dict:
    """
    Convert Alert dataclass to JSON-serializable dict.

    Handles:
    - datetime → ISO 8601 string
    - enum → string value (via .value)
    - tuples → lists (for JSON compatibility)

    Args:
        alert: Alert dataclass instance.

    Returns:
        Dict with all fields converted to JSON-compatible types.
    """
    data = alert.__dict__.copy()

    # Convert timestamp (datetime) to ISO string
    if isinstance(data.get("timestamp"), datetime):
        data["timestamp"] = data["timestamp"].isoformat()

    # Convert alert_type enum to string
    if hasattr(data.get("alert_type"), "value"):
        data["alert_type"] = data["alert_type"].value

    return data
