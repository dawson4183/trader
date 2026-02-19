"""Logging utilities for the trader module.

This module provides custom logging formatters and handlers for structured logging.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Dict, Optional

import trader.config as config_module


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging.
    
    Formats log records as JSON with the following fields:
    - timestamp: ISO 8601 formatted timestamp
    - level: Uppercase log level name
    - message: The log message
    - context: Extra fields passed to the logger
    
    Example output:
    {
        "timestamp": "2024-01-15T10:30:45.123456+00:00",
        "level": "ERROR",
        "message": "Something went wrong",
        "context": {"user_id": "123", "action": "buy"}
    }
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON string.
        
        Args:
            record: The log record to format.
            
        Returns:
            A JSON string representation of the log record.
        """
        # Build the base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": self._get_iso_timestamp(record),
            "level": record.levelname.upper(),
            "message": record.getMessage(),
        }
        
        # Extract context from extra fields
        context = self._extract_context(record)
        if context:
            log_entry["context"] = context
        
        return json.dumps(log_entry, default=str)
    
    def _get_iso_timestamp(self, record: logging.LogRecord) -> str:
        """Generate ISO 8601 formatted timestamp from log record.
        
        Args:
            record: The log record containing the timestamp.
            
        Returns:
            ISO 8601 formatted timestamp string.
        """
        # Use the record's created timestamp (Unix timestamp in seconds)
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.isoformat()
    
    def _extract_context(self, record: logging.LogRecord) -> Optional[Dict[str, Any]]:
        """Extract extra context fields from the log record.
        
        This method identifies fields that were passed as 'extra' kwargs
        to the logging call, excluding standard LogRecord attributes.
        
        Args:
            record: The log record to extract context from.
            
        Returns:
            Dictionary of extra context fields, or None if no extra fields.
        """
        # Standard LogRecord attributes to exclude from context
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "asctime", "taskName",  # Python 3.12+ has taskName
        }
        
        # Collect non-standard attributes as context
        context: Dict[str, Any] = {}
        for attr_name in dir(record):
            # Skip private attributes, standard attributes, and methods
            if attr_name.startswith("_") or attr_name in standard_attrs:
                continue
            
            # Get the attribute value
            try:
                value = getattr(record, attr_name)
                # Skip callable attributes (methods)
                if callable(value):
                    continue
                context[attr_name] = value
            except AttributeError:
                continue
        
        return context if context else None


class WebhookHandler(logging.Handler):
    """Custom logging handler that POSTs ERROR and CRITICAL logs to a webhook.
    
    This handler filters logs to only send ERROR and CRITICAL level messages
to a configured webhook URL. Network errors are gracefully suppressed to
    prevent the application from crashing due to logging failures.
    
    The webhook payload is JSON formatted with:
    - timestamp: ISO 8601 formatted timestamp
    - level: Uppercase log level name
    - message: The log message
    - context: Extra fields passed to the logger
    
    Example payload:
    {
        "timestamp": "2024-01-15T10:30:45.123456+00:00",
        "level": "ERROR",
        "message": "Database connection failed",
        "context": {"user_id": "123", "action": "buy"}
    }
    """
    
    def __init__(self, webhook_url: Optional[str] = None, level: int = logging.ERROR) -> None:
        """Initialize the webhook handler.
        
        Args:
            webhook_url: URL to POST log messages to. If None, uses config.WEBHOOK_URL.
            level: Minimum log level to process. Defaults to ERROR.
        """
        super().__init__(level=level)
        self.webhook_url = webhook_url or config_module.WEBHOOK_URL
    
    def emit(self, record: logging.LogRecord) -> None:
        """Send the log record to the webhook if level is ERROR or CRITICAL.
        
        Only processes ERROR (40) and CRITICAL (50) level logs.
        Silently skips if webhook URL is not configured.
        Catches and suppresses all network errors to prevent app crashes.
        
        Args:
            record: The log record to process.
        """
        # Only process ERROR and CRITICAL level logs
        if record.levelno < logging.ERROR:
            return
        
        # Skip if no webhook URL is configured
        if not self.webhook_url:
            return
        
        try:
            # Build the webhook payload
            payload = self._build_payload(record)
            
            # Create the request
            data = json.dumps(payload, default=str).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(data))
                },
                method='POST'
            )
            
            # Send the request and close the response
            with urllib.request.urlopen(req, timeout=10) as response:
                # Just consume the response to ensure it completes
                response.read()
                
        except Exception:
            # Suppress all errors - logging should never crash the app
            # This includes network errors, timeout errors, JSON encoding errors, etc.
            pass
    
    def _build_payload(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Build the JSON payload for the webhook.
        
        Args:
            record: The log record to convert to payload.
            
        Returns:
            Dictionary containing timestamp, level, message, and context.
        """
        # Generate ISO 8601 timestamp
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        
        payload: Dict[str, Any] = {
            "timestamp": dt.isoformat(),
            "level": record.levelname.upper(),
            "message": record.getMessage(),
        }
        
        # Extract context using the same logic as JsonFormatter
        context = self._extract_context(record)
        if context:
            payload["context"] = context
        
        return payload
    
    def _extract_context(self, record: logging.LogRecord) -> Optional[Dict[str, Any]]:
        """Extract extra context fields from the log record.
        
        This method identifies fields that were passed as 'extra' kwargs
        to the logging call, excluding standard LogRecord attributes.
        
        Args:
            record: The log record to extract context from.
            
        Returns:
            Dictionary of extra context fields, or None if no extra fields.
        """
        # Standard LogRecord attributes to exclude from context
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "asctime", "taskName",
        }
        
        # Collect non-standard attributes as context
        context: Dict[str, Any] = {}
        for attr_name in dir(record):
            # Skip private attributes, standard attributes, and methods
            if attr_name.startswith("_") or attr_name in standard_attrs:
                continue
            
            try:
                value = getattr(record, attr_name)
                # Skip callable attributes (methods)
                if callable(value):
                    continue
                context[attr_name] = value
            except AttributeError:
                continue
        
        return context if context else None


def setup_logging() -> logging.Logger:
    """Configure the root logger with JSON formatter and multiple handlers.
    
    This function sets up a comprehensive logging configuration with:
    - JSON formatting for all log output
    - TimedRotatingFileHandler (daily rotation, 7 day retention)
    - Console handler for stdout
    - WebhookHandler for ERROR/CRITICAL level logs
    
    The function is idempotent - calling it multiple times will not add
    duplicate handlers to the logger.
    
    The 'logs' directory is created automatically if it doesn't exist.
    
    Returns:
        The configured root logger instance.
    
    Example:
        >>> logger = setup_logging()
        >>> logger.info("Application started", extra={"version": "1.0.0"})
    """
    # Get the root logger
    logger = logging.getLogger()
    
    # Check if already configured (idempotency check)
    # We check by looking for JsonFormatter in existing handlers
    for handler in logger.handlers:
        if isinstance(handler.formatter, JsonFormatter):
            return logger
    
    # Set log level based on config
    log_level = getattr(logging, config_module.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(config_module.LOG_FILE_PATH)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Create JSON formatter for all handlers
    json_formatter = JsonFormatter()
    
    # Set up TimedRotatingFileHandler (daily rotation, 7 day retention)
    file_handler = TimedRotatingFileHandler(
        filename=config_module.LOG_FILE_PATH,
        when='D',  # Daily rotation
        interval=1,  # Every day
        backupCount=config_module.LOG_RETENTION_DAYS,  # Keep 7 days of logs
        encoding='utf-8'
    )
    file_handler.setFormatter(json_formatter)
    logger.addHandler(file_handler)
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)
    logger.addHandler(console_handler)
    
    # Set up webhook handler for ERROR/CRITICAL only
    webhook_handler = WebhookHandler(level=logging.ERROR)
    # WebhookHandler has built-in level filtering, but we set it explicitly
    webhook_handler.setFormatter(json_formatter)
    logger.addHandler(webhook_handler)
    
    return logger