"""Alert module for sending notifications via webhooks.

This module provides functionality to send alerts with different severity
levels via webhook calls. Alerts are also logged for audit purposes.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Union

# Create module-level logger
logger = logging.getLogger("trader.alert")

# Alert level type
AlertLevel = Literal["info", "warning", "error", "critical"]

# Default webhook timeout in seconds
DEFAULT_WEBHOOK_TIMEOUT = 30


def send_alert(
    message: str,
    level: AlertLevel = "info"
) -> bool:
    """Send an alert via webhook and log it.

    Sends a POST request to the configured webhook URL with a JSON
    payload containing the alert message, level, timestamp, and source.
    The alert is also logged at the appropriate level.

    Args:
        message: The alert message to send.
        level: The alert level (info, warning, error, critical).
            Defaults to "info".

    Returns:
        True if the webhook request was successful (2xx response),
        False otherwise (4xx, 5xx, network errors, or timeouts).

    Example:
        >>> send_alert("Database connection established", "info")
        True
        >>> send_alert("Failed to connect to database", "critical")
        True
    """
    # Get webhook URL from environment
    webhook_url = os.environ.get("WEBHOOK_URL")
    
    # Log the alert at the appropriate level
    log_alert(message, level)
    
    # If no webhook URL configured, just logging is sufficient
    if not webhook_url:
        return True
    
    # Build the webhook payload
    payload: Dict[str, Any] = {
        "message": message,
        "level": level,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "trader.alert",
    }
    
    try:
        # Create the request
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(data)),
            },
            method="POST",
        )
        
        # Send the request with timeout
        with urllib.request.urlopen(req, timeout=DEFAULT_WEBHOOK_TIMEOUT) as response:
            # Check if response is 2xx (200-299)
            if 200 <= response.status < 300:
                return True
            return False
            
    except urllib.error.HTTPError as e:
        # HTTP errors (4xx, 5xx) return False
        return False
    except urllib.error.URLError:
        # Network errors return False
        return False
    except TimeoutError:
        # Timeout errors return False
        return False
    except Exception:
        # Any other error returns False
        return False


def log_alert(message: str, level: AlertLevel) -> None:
    """Log an alert at the appropriate level.

    Args:
        message: The alert message to log.
        level: The alert level.
    """
    log_message = f"[ALERT {level.upper()}] {message}"
    
    if level == "info":
        logger.info(log_message)
    elif level == "warning":
        logger.warning(log_message)
    elif level == "error":
        logger.error(log_message)
    elif level == "critical":
        logger.critical(log_message)
