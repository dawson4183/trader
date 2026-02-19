"""Alert module for sending webhook notifications.

Provides functionality to send alerts to a configured webhook endpoint
for monitoring and notification purposes. Also logs all alerts to the
standard Python logging system.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Literal

# Module-level logger
logger = logging.getLogger(__name__)


AlertLevelType = Literal["info", "warning", "error", "critical"]

VALID_LEVELS = {"info", "warning", "error", "critical"}

# Map alert levels to logging levels
LEVEL_TO_LOGGING: dict[AlertLevelType, int] = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
}


def send_alert(message: str, level: AlertLevelType) -> bool:
    """Send an alert to the configured webhook endpoint.

    Sends a POST request to the webhook URL configured via the
    WEBHOOK_URL environment variable with a JSON payload containing
    the alert details.

    Args:
        message: The alert message to send.
        level: The severity level of the alert. Must be one of:
               'info', 'warning', 'error', 'critical'

    Returns:
        True if the webhook returns a 2xx status code, False otherwise.
        Returns False if WEBHOOK_URL is not configured or if the level
        is invalid.

    Example:
        >>> success = send_alert("Database connection failed", "critical")
        >>> print(f"Alert sent: {success}")
    """
    # Validate level
    if level not in VALID_LEVELS:
        return False

    # Get webhook URL from environment
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        return False

    # Build payload
    payload = {
        "message": message,
        "level": level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "trader.alert",
    }

    # Log the alert before attempting webhook call
    # Log format includes timestamp (added by logging), level, message, and source module
    log_level = LEVEL_TO_LOGGING[level]
    logger.log(log_level, "[ALERT %s] %s", level.upper(), message)

    # Send POST request
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            # Check for 2xx status code
            status: int = response.status
            return 200 <= status < 300

    except urllib.error.HTTPError as e:
        # HTTP error (non-2xx status code)
        code: int = e.code
        return 200 <= code < 300
    except urllib.error.URLError:
        # Connection error, invalid URL, etc.
        return False
    except Exception:
        # Any other error (timeout, etc.)
        return False
