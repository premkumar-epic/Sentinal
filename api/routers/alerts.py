"""
SENTINAL v2 — Alerts Configuration Router

Provides endpoints for managing alert settings (email and webhook) and testing alert channels.
All endpoints return JSON responses with current configuration state.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from engine.alerts.email import send_alert_email
from engine.alerts.manager import Alert, AlertType
from engine.alerts.webhook import post_webhook
from engine.config import settings

logger = logging.getLogger(__name__)

# Create router with /api/alerts prefix and tag
router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class AlertConfigResponse(BaseModel):
    """Alert configuration response schema."""

    email_enabled: bool
    email_smtp_host: str
    email_smtp_port: int
    email_sender: str
    email_recipient: str
    email_password: str  # always "***" or "" (masked)
    webhook_enabled: bool
    webhook_url: str


class AlertConfigUpdate(BaseModel):
    """Alert configuration update schema (all fields optional)."""

    email_enabled: Optional[bool] = None
    email_smtp_host: Optional[str] = None
    email_smtp_port: Optional[int] = None
    email_sender: Optional[str] = None
    email_recipient: Optional[str] = None
    email_password: Optional[str] = None
    webhook_enabled: Optional[bool] = None
    webhook_url: Optional[str] = None


class AlertTestResponse(BaseModel):
    """Alert test endpoint response schema."""

    email: str  # "sent" | "disabled" | "error: <message>"
    webhook: str  # "sent" | "disabled" | "error: <message>"


# ============================================================================
# Helper Functions
# ============================================================================


def _get_current_config() -> AlertConfigResponse:
    """
    Build the current alert configuration response.

    Masks the email password: returns "***" if non-empty, else "".

    Returns:
        AlertConfigResponse with current settings.
    """
    password_mask = "***" if settings.alert_email_password else ""

    return AlertConfigResponse(
        email_enabled=settings.alert_email_enabled,
        email_smtp_host=settings.alert_email_smtp_host,
        email_smtp_port=settings.alert_email_smtp_port,
        email_sender=settings.alert_email_sender,
        email_recipient=settings.alert_email_recipient,
        email_password=password_mask,
        webhook_enabled=settings.alert_webhook_enabled,
        webhook_url=settings.alert_webhook_url,
    )


def _build_dummy_alert() -> Alert:
    """
    Build a dummy Alert object for testing purposes.

    Returns:
        Alert instance with test data.
    """
    return Alert(
        alert_id=str(uuid4()),
        alert_type=AlertType.INTRUSION,
        cam_id="test",
        zone_id=None,
        track_ids=[],
        global_ids=[],
        name=None,
        confidence=1.0,
        timestamp=datetime.now(timezone.utc),
        snapshot_path=None,
        metadata={"test": True},
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/config", response_model=AlertConfigResponse)
async def get_alert_config() -> AlertConfigResponse:
    """
    Get current alert configuration.

    Returns the current email and webhook alert settings, with the email
    password field masked for security.

    Returns:
        AlertConfigResponse with current settings.
    """
    return _get_current_config()


@router.put("/config", response_model=AlertConfigResponse)
async def update_alert_config(body: AlertConfigUpdate) -> AlertConfigResponse:
    """
    Update alert configuration.

    Accepts an AlertConfigUpdate with optional fields. Only provided fields
    are updated in the settings object. The email password is handled specially:
    if provided in the request, it updates the actual password in settings
    (not masked in storage).

    Args:
        body: AlertConfigUpdate with optional fields to update.

    Returns:
        AlertConfigResponse with updated settings.
    """
    # Update email settings if provided
    if body.email_enabled is not None:
        settings.alert_email_enabled = body.email_enabled
    if body.email_smtp_host is not None:
        settings.alert_email_smtp_host = body.email_smtp_host
    if body.email_smtp_port is not None:
        settings.alert_email_smtp_port = body.email_smtp_port
    if body.email_sender is not None:
        settings.alert_email_sender = body.email_sender
    if body.email_recipient is not None:
        settings.alert_email_recipient = body.email_recipient
    if body.email_password is not None:
        settings.alert_email_password = body.email_password

    # Update webhook settings if provided
    if body.webhook_enabled is not None:
        settings.alert_webhook_enabled = body.webhook_enabled
    if body.webhook_url is not None:
        settings.alert_webhook_url = body.webhook_url

    logger.debug("Alert configuration updated")
    return _get_current_config()


@router.post("/test", response_model=AlertTestResponse)
async def test_alert_channels() -> AlertTestResponse:
    """
    Test alert channels (email and webhook).

    Sends a test email (if enabled) and/or test webhook (if enabled) to verify
    that the alert configuration is working correctly. Catches all exceptions
    and returns error messages instead of raising.

    Returns:
        AlertTestResponse with status for each channel:
        - "sent": alert was sent successfully
        - "disabled": alert channel is disabled
        - "error: <message>": exception occurred while sending
    """
    email_status = "disabled"
    webhook_status = "disabled"

    # Test email channel
    if settings.alert_email_enabled:
        try:
            dummy_alert = _build_dummy_alert()
            await send_alert_email(dummy_alert, "")
            email_status = "sent"
            logger.info("Test email sent successfully")
        except Exception as e:
            email_status = f"error: {str(e)}"
            logger.error(f"Test email failed: {e}", exc_info=True)
    else:
        logger.debug("Email alerts disabled; skipping test email")

    # Test webhook channel
    if settings.alert_webhook_enabled:
        try:
            dummy_alert = _build_dummy_alert()
            await post_webhook(dummy_alert)
            webhook_status = "sent"
            logger.info("Test webhook sent successfully")
        except Exception as e:
            webhook_status = f"error: {str(e)}"
            logger.error(f"Test webhook failed: {e}", exc_info=True)
    else:
        logger.debug("Webhook alerts disabled; skipping test webhook")

    return AlertTestResponse(email=email_status, webhook=webhook_status)
