"""Alert module for sending notifications.

Provides functions to send alerts via webhooks and log them.
"""

import logging
import os
from typing import Optional

import requests


logger = logging.getLogger(__name__)


def send_alert(message: str, level: str = "error") -> bool:
    """Send an alert notification via webhook and log it.

    Sends the alert to a configured webhook URL if available,
    and logs the alert at the appropriate level.

    Args:
        message: The alert message to send.
        level: Alert level - 'warning', 'error', or 'critical'.
               Defaults to 'error'.

    Returns:
        True if the alert was sent successfully (webhook returned 2xx),
        False otherwise.
    """
    # Log the alert
    log_level = level.lower()
    if log_level == "critical":
        logger.critical(message)
    elif log_level == "warning":
        logger.warning(message)
    else:
        logger.error(message)

    # Send webhook if configured
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
    if not webhook_url:
        return False

    try:
        response = requests.post(
            webhook_url,
            json={
                "message": message,
                "level": level,
            },
            timeout=10,
        )
        return response.status_code >= 200 and response.status_code < 300
    except Exception as e:
        logger.error(f"Failed to send alert webhook: {e}")
        return False
