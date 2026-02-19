"""Tests for trader.logging_utils module."""

import json
import logging
from datetime import datetime, timezone

import pytest

from trader.logging_utils import JsonFormatter


class TestJsonFormatterBasics:
    """Test basic JsonFormatter functionality."""

    def test_json_formatter_extends_logging_formatter(self):
        """JsonFormatter should extend logging.Formatter."""
        assert issubclass(JsonFormatter, logging.Formatter)

    def test_json_formatter_instantiates(self):
        """JsonFormatter should be instantiable."""
        formatter = JsonFormatter()
        assert isinstance(formatter, JsonFormatter)


class TestJsonFormatterOutput:
    """Test JSON output format and fields."""

    def test_output_contains_timestamp(self):
        """Output JSON should contain 'timestamp' field in ISO 8601 format."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert "timestamp" in parsed
        # Verify ISO 8601 format (should end with +00:00 or Z for UTC)
        timestamp = parsed["timestamp"]
        assert "T" in timestamp  # ISO 8601 separator
        # Parse to verify it's a valid ISO timestamp
        dt = datetime.fromisoformat(timestamp)
        assert dt.tzinfo is not None  # Should have timezone info

    def test_output_contains_level_uppercase(self):
        """Output JSON should contain 'level' field with uppercase level name."""
        formatter = JsonFormatter()
        
        test_cases = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]
        
        for level, expected in test_cases:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            
            output = formatter.format(record)
            parsed = json.loads(output)
            
            assert parsed["level"] == expected, f"Expected {expected} for level {level}"

    def test_output_contains_message(self):
        """Output JSON should contain 'message' field with log message."""
        formatter = JsonFormatter()
        test_message = "This is a test log message"
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=test_message,
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["message"] == test_message

    def test_output_message_with_formatting(self):
        """Message field should handle printf-style formatting."""
        formatter = JsonFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="User %s logged in from %s",
            args=("alice", "192.168.1.1"),
            exc_info=None,
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["message"] == "User alice logged in from 192.168.1.1"


class TestJsonFormatterContext:
    """Test context field handling."""

    def test_output_contains_context_with_extra_fields(self):
        """Output JSON should contain 'context' field with extra fields."""
        formatter = JsonFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        # Add extra fields as if passed via extra={...}
        record.user_id = "123"
        record.action = "buy"
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert "context" in parsed
        assert parsed["context"]["user_id"] == "123"
        assert parsed["context"]["action"] == "buy"

    def test_no_context_when_no_extra_fields(self):
        """Context field should not be present when no extra fields provided."""
        formatter = JsonFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert "context" not in parsed

    def test_context_with_various_types(self):
        """Context should handle various data types."""
        formatter = JsonFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.string_val = "text"
        record.int_val = 42
        record.float_val = 3.14
        record.bool_val = True
        record.list_val = [1, 2, 3]
        record.dict_val = {"nested": "value"}
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        context = parsed["context"]
        assert context["string_val"] == "text"
        assert context["int_val"] == 42
        assert context["float_val"] == 3.14
        assert context["bool_val"] is True
        assert context["list_val"] == [1, 2, 3]
        assert context["dict_val"] == {"nested": "value"}


class TestJsonFormatterIntegration:
    """Test integration with Python logging system."""

    def test_integration_with_logger(self):
        """JsonFormatter works with actual Logger instance."""
        import io
        
        # Set up a logger with our formatter
        logger = logging.getLogger("test_json_logger")
        logger.setLevel(logging.DEBUG)
        
        # Create a string buffer to capture output
        log_capture = io.StringIO()
        
        # Create a handler with our formatter
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(JsonFormatter())
        
        # Clear existing handlers and add ours
        logger.handlers = []
        logger.addHandler(handler)
        
        # Suppress propagation to avoid duplicate logs
        logger.propagate = False
        
        # Log a message with extra fields
        logger.info("Test message", extra={"user_id": "456", "operation": "test"})
        
        # Get the formatted output
        output = log_capture.getvalue()
        
        # Verify the output is valid JSON with expected fields
        parsed = json.loads(output)
        assert parsed["message"] == "Test message"
        assert parsed["context"]["user_id"] == "456"
        assert parsed["context"]["operation"] == "test"

    def test_json_output_is_valid(self):
        """Formatted output should always be valid JSON."""
        formatter = JsonFormatter()
        
        # Test with various message types
        test_messages = [
            "Simple message",
            "Message with \"quotes\"",
            "Message with \n newlines",
            "Message with \t tabs",
            "Message with unicode: 你好",
            "Message with special chars: {}",
        ]
        
        for msg in test_messages:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg=msg,
                args=(),
                exc_info=None,
            )
            
            output = formatter.format(record)
            # Should not raise
            parsed = json.loads(output)
            assert parsed["message"] == msg


class TestJsonFormatterEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_message(self):
        """Should handle empty message."""
        formatter = JsonFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["message"] == ""

    def test_none_in_context(self):
        """Should handle None values in context."""
        formatter = JsonFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.null_field = None
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert parsed["context"]["null_field"] is None

    def test_exception_info_not_in_context(self):
        """Exception info should not appear in context."""
        formatter = JsonFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = (type, type, type)
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        # Standard LogRecord attrs should not be in context
        assert "exc_info" not in parsed.get("context", {})
        assert "exc_text" not in parsed.get("context", {})
