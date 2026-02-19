"""Logging utilities for the trader module.

This module provides custom logging formatters and handlers for structured logging.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional


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
