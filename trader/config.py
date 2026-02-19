"""Logging configuration for the trader module.

This module centralizes logging configuration settings loaded from
environment variables with sensible defaults.
"""

import os
from typing import Optional

# Logging level - defaults to INFO if not set
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

# JSON log format configuration
# Includes timestamp, level, message, and context fields
LOG_FORMAT: str = os.environ.get(
    "LOG_FORMAT",
    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(name)s"}'
)

# Log retention period in days - defaults to 7
LOG_RETENTION_DAYS: int = int(os.environ.get("LOG_RETENTION_DAYS", "7"))

# Webhook URL for ERROR/CRITICAL log alerts
# Gracefully handles missing environment variable
WEBHOOK_URL: Optional[str] = os.environ.get("WEBHOOK_URL")

# Log file path
LOG_FILE_PATH: str = "logs/trader.log"
