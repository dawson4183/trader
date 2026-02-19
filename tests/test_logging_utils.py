"""Tests for trader.logging_utils module."""

import json
import logging
import urllib.request
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from trader.logging_utils import JsonFormatter, WebhookHandler


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


class TestWebhookHandlerBasics:
    """Test basic WebhookHandler functionality."""

    def test_webhook_handler_extends_logging_handler(self):
        """WebhookHandler should extend logging.Handler."""
        assert issubclass(WebhookHandler, logging.Handler)

    def test_webhook_handler_instantiates(self):
        """WebhookHandler should be instantiable."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        assert isinstance(handler, WebhookHandler)

    def test_webhook_handler_uses_config_webhook_url(self):
        """WebhookHandler should use config.WEBHOOK_URL when not provided."""
        with patch('trader.logging_utils.config.WEBHOOK_URL', 'http://config.com/webhook'):
            handler = WebhookHandler()
            assert handler.webhook_url == 'http://config.com/webhook'

    def test_webhook_handler_uses_provided_url_over_config(self):
        """WebhookHandler should prefer provided URL over config."""
        with patch('trader.logging_utils.config.WEBHOOK_URL', 'http://config.com/webhook'):
            handler = WebhookHandler(webhook_url="http://provided.com/webhook")
            assert handler.webhook_url == "http://provided.com/webhook"


class TestWebhookHandlerLevelFiltering:
    """Test that WebhookHandler only processes ERROR and CRITICAL logs."""

    def test_skips_debug_logs(self):
        """Should not process DEBUG level logs."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch.object(handler, '_build_payload') as mock_build:
            record = logging.LogRecord(
                name="test",
                level=logging.DEBUG,
                pathname="test.py",
                lineno=1,
                msg="Debug message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
            mock_build.assert_not_called()

    def test_skips_info_logs(self):
        """Should not process INFO level logs."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch.object(handler, '_build_payload') as mock_build:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Info message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
            mock_build.assert_not_called()

    def test_skips_warning_logs(self):
        """Should not process WARNING level logs."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch.object(handler, '_build_payload') as mock_build:
            record = logging.LogRecord(
                name="test",
                level=logging.WARNING,
                pathname="test.py",
                lineno=1,
                msg="Warning message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
            mock_build.assert_not_called()

    def test_processes_error_logs(self):
        """Should process ERROR level logs."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b'{}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
            mock_urlopen.assert_called_once()

    def test_processes_critical_logs(self):
        """Should process CRITICAL level logs."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b'{}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            record = logging.LogRecord(
                name="test",
                level=logging.CRITICAL,
                pathname="test.py",
                lineno=1,
                msg="Critical message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
            mock_urlopen.assert_called_once()


class TestWebhookHandlerNoUrl:
    """Test behavior when WEBHOOK_URL is not set."""

    def test_skips_when_no_webhook_url(self):
        """Should gracefully skip when WEBHOOK_URL is not set."""
        handler = WebhookHandler(webhook_url=None)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
            mock_urlopen.assert_not_called()

    def test_skips_when_empty_webhook_url(self):
        """Should gracefully skip when WEBHOOK_URL is empty string."""
        handler = WebhookHandler(webhook_url="")
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error message",
                args=(),
                exc_info=None,
            )
            handler.emit(record)
            mock_urlopen.assert_not_called()


class TestWebhookHandlerPayload:
    """Test webhook payload structure."""

    def test_payload_contains_timestamp(self):
        """Payload should contain ISO 8601 timestamp."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        
        payload = handler._build_payload(record)
        
        assert "timestamp" in payload
        assert "T" in payload["timestamp"]  # ISO 8601 separator
        # Verify it's a valid ISO timestamp
        dt = datetime.fromisoformat(payload["timestamp"])
        assert dt.tzinfo is not None

    def test_payload_contains_level(self):
        """Payload should contain uppercase level."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        
        payload = handler._build_payload(record)
        
        assert payload["level"] == "ERROR"

    def test_payload_contains_message(self):
        """Payload should contain message."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test error message",
            args=(),
            exc_info=None,
        )
        
        payload = handler._build_payload(record)
        
        assert payload["message"] == "Test error message"

    def test_payload_contains_context(self):
        """Payload should contain context with extra fields."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        record.user_id = "123"
        record.action = "buy"
        
        payload = handler._build_payload(record)
        
        assert "context" in payload
        assert payload["context"]["user_id"] == "123"
        assert payload["context"]["action"] == "buy"

    def test_payload_no_context_without_extra_fields(self):
        """Payload should not have context when no extra fields."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        
        payload = handler._build_payload(record)
        
        assert "context" not in payload


class TestWebhookHandlerErrorHandling:
    """Test error handling - should not crash the app."""

    def test_suppresses_connection_error(self):
        """Should suppress connection errors."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch('urllib.request.urlopen', side_effect=ConnectionError("Connection failed")):
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error message",
                args=(),
                exc_info=None,
            )
            # Should not raise
            handler.emit(record)

    def test_suppresses_timeout_error(self):
        """Should suppress timeout errors."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch('urllib.request.urlopen', side_effect=TimeoutError("Request timed out")):
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error message",
                args=(),
                exc_info=None,
            )
            # Should not raise
            handler.emit(record)

    def test_suppresses_http_error(self):
        """Should suppress HTTP errors."""
        import urllib.error
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError(
            url="http://example.com/webhook",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None
        )):
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error message",
                args=(),
                exc_info=None,
            )
            # Should not raise
            handler.emit(record)

    def test_suppresses_url_error(self):
        """Should suppress URL errors."""
        import urllib.error
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("URL error")):
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error message",
                args=(),
                exc_info=None,
            )
            # Should not raise
            handler.emit(record)


class TestWebhookHandlerIntegration:
    """Test integration with actual HTTP requests."""

    def test_sends_post_request_with_json_payload(self):
        """Should send POST request with correct JSON headers and payload."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b'{"status": "ok"}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error message",
                args=(),
                exc_info=None,
            )
            record.user_id = "456"
            
            handler.emit(record)
            
            # Verify urlopen was called
            assert mock_urlopen.called
            
            # Get the Request object that was passed
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            
            # Verify it's a Request object
            assert isinstance(request, urllib.request.Request)
            assert request.get_full_url() == "http://example.com/webhook"
            assert request.get_method() == "POST"
            
            # Verify headers
            assert request.get_header('Content-type') == 'application/json'

    def test_payload_json_structure(self):
        """Verify the actual JSON payload structure."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Critical database failure",
            args=(),
            exc_info=None,
        )
        record.user_id = "789"
        record.operation = "database_write"
        
        payload = handler._build_payload(record)
        
        # Verify structure matches expected format
        assert "timestamp" in payload
        assert payload["level"] == "ERROR"
        assert payload["message"] == "Critical database failure"
        assert payload["context"]["user_id"] == "789"
        assert payload["context"]["operation"] == "database_write"
        
        # Verify it's valid JSON
        json_str = json.dumps(payload)
        parsed = json.loads(json_str)
        assert parsed == payload
