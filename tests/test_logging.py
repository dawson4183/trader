"""Comprehensive tests for structured logging system.

This module provides integration and comprehensive tests for all logging components:
- JsonFormatter: JSON structure validation
- TimedRotatingFileHandler: File rotation behavior
- WebhookHandler: URL filtering and error handling
- setup_logging(): Idempotency and configuration
- Integration with trader module functions
"""

import json
import logging
import os
import shutil
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from unittest.mock import Mock, patch

import pytest

import trader.config as config_module
from trader.logging_utils import JsonFormatter, WebhookHandler, setup_logging


class TestJsonFormatterStructure:
    """Test JsonFormatter JSON structure validation."""

    def test_json_structure_has_required_fields(self):
        """JSON output must contain timestamp, level, and message fields."""
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
        assert "level" in parsed
        assert "message" in parsed

    def test_json_structure_timestamp_iso8601(self):
        """Timestamp must be valid ISO 8601 format with timezone."""
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

        timestamp = parsed["timestamp"]
        # Should have ISO 8601 format with T separator
        assert "T" in timestamp
        # Should end with +00:00 or Z for UTC
        assert "+00:00" in timestamp or timestamp.endswith("Z")
        # Should be parseable
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert dt.tzinfo is not None

    def test_json_structure_level_uppercase(self):
        """Level field must be uppercase string."""
        formatter = JsonFormatter()

        test_levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for level, expected in test_levels:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["level"] == expected
            assert parsed["level"].isupper()

    def test_json_structure_message_string(self):
        """Message field must be a string."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message content",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert isinstance(parsed["message"], str)
        assert parsed["message"] == "Test message content"

    def test_json_structure_context_optional(self):
        """Context field should only appear when extra fields provided."""
        formatter = JsonFormatter()

        # Without extra fields - no context
        record1 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        output1 = formatter.format(record1)
        parsed1 = json.loads(output1)
        assert "context" not in parsed1

        # With extra fields - has context
        record2 = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record2.user_id = "123"
        output2 = formatter.format(record2)
        parsed2 = json.loads(output2)
        assert "context" in parsed2
        assert parsed2["context"]["user_id"] == "123"

    def test_json_structure_valid_json_output(self):
        """Output must always be valid JSON."""
        formatter = JsonFormatter()

        test_cases = [
            "Simple message",
            'Message with "quotes"',
            "Message with \n newlines",
            "Message with \t tabs",
            "Message with unicode: 你好世界 🌍",
            "Message with special: {} [] <>",
            "",
        ]

        for msg in test_cases:
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
            # Should not raise JSONDecodeError
            parsed = json.loads(output)
            assert isinstance(parsed, dict)


class TestTimedRotatingFileHandlerRotation:
    """Test TimedRotatingFileHandler file rotation behavior."""

    def test_rotation_creates_new_file(self):
        """Rotation should create a new log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                handler = TimedRotatingFileHandler(
                    filename=log_file,
                    when="S",  # Rotate every second for testing
                    interval=1,
                    backupCount=3,
                    encoding="utf-8",
                )
                handler.setFormatter(JsonFormatter())
                root_logger.addHandler(handler)
                root_logger.setLevel(logging.INFO)

                # Log first message
                root_logger.info("First message")
                handler.flush()

                # Wait for rotation interval
                time.sleep(1.1)

                # Log second message (should trigger rotation)
                root_logger.info("Second message")
                handler.flush()

                # Check that rotated file exists
                rotated_files = [f for f in os.listdir(tmpdir) if f.startswith("test.log.")]
                assert len(rotated_files) >= 1

                handler.close()
            finally:
                root_logger.handlers = original_handlers

    def test_rotation_respects_backup_count(self):
        """Rotation should respect backupCount and delete old files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                handler = TimedRotatingFileHandler(
                    filename=log_file,
                    when="S",  # Rotate every second for testing
                    interval=1,
                    backupCount=2,  # Keep only 2 backups
                    encoding="utf-8",
                )
                handler.setFormatter(JsonFormatter())
                root_logger.addHandler(handler)
                root_logger.setLevel(logging.INFO)

                # Create multiple rotations
                for i in range(5):
                    root_logger.info(f"Message {i}")
                    handler.flush()
                    time.sleep(1.1)

                handler.close()

                # Check backup count
                rotated_files = [f for f in os.listdir(tmpdir) if f.startswith("test.log.")]
                assert len(rotated_files) <= 2
            finally:
                root_logger.handlers = original_handlers

    def test_rotation_preserves_json_format(self):
        """Rotated files should maintain JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                handler = TimedRotatingFileHandler(
                    filename=log_file,
                    when="S",
                    interval=1,
                    backupCount=3,
                    encoding="utf-8",
                )
                handler.setFormatter(JsonFormatter())
                root_logger.addHandler(handler)
                root_logger.setLevel(logging.INFO)

                # Log a message
                root_logger.info("Test message", extra={"test_key": "test_value"})
                handler.flush()
                time.sleep(1.1)

                # Trigger rotation
                root_logger.info("Second message")
                handler.flush()
                handler.close()

                # Check rotated file content
                rotated_files = [f for f in os.listdir(tmpdir) if f.startswith("test.log.")]
                if rotated_files:
                    rotated_file = os.path.join(tmpdir, rotated_files[0])
                    with open(rotated_file, "r") as f:
                        for line in f:
                            if line.strip():
                                parsed = json.loads(line)
                                assert "timestamp" in parsed
                                assert "level" in parsed
                                assert "message" in parsed
            finally:
                root_logger.handlers = original_handlers

    def test_rotation_daily_interval(self):
        """Daily rotation interval should be properly configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "daily.log")

            handler = TimedRotatingFileHandler(
                filename=log_file,
                when="D",  # Daily
                interval=1,
                backupCount=7,
                encoding="utf-8",
            )

            assert handler.when == "D"
            assert handler.interval == 86400  # 1 day in seconds
            assert handler.backupCount == 7

            handler.close()


class TestWebhookHandlerFilteringAndErrors:
    """Test WebhookHandler URL filtering and error handling."""

    def test_url_filtering_skips_without_url(self):
        """Should skip sending when WEBHOOK_URL is not set."""
        handler = WebhookHandler(webhook_url=None)

        with patch("urllib.request.urlopen") as mock_urlopen:
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

    def test_url_filtering_skips_with_empty_url(self):
        """Should skip sending when WEBHOOK_URL is empty string."""
        handler = WebhookHandler(webhook_url="")

        with patch("urllib.request.urlopen") as mock_urlopen:
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

    def test_url_filtering_sends_with_valid_url(self):
        """Should send POST when WEBHOOK_URL is valid."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen") as mock_urlopen:
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

    def test_level_filtering_skips_info(self):
        """Should skip INFO level logs."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen") as mock_urlopen:
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
            mock_urlopen.assert_not_called()

    def test_level_filtering_skips_warning(self):
        """Should skip WARNING level logs."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen") as mock_urlopen:
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
            mock_urlopen.assert_not_called()

    def test_level_filtering_sends_error(self):
        """Should send ERROR level logs."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen") as mock_urlopen:
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

    def test_level_filtering_sends_critical(self):
        """Should send CRITICAL level logs."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen") as mock_urlopen:
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

    def test_error_handling_suppresses_connection_error(self):
        """Should suppress ConnectionError without crashing."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen", side_effect=ConnectionError("Connection failed")):
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

    def test_error_handling_suppresses_timeout_error(self):
        """Should suppress TimeoutError without crashing."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
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

    def test_error_handling_suppresses_http_error(self):
        """Should suppress HTTPError without crashing."""
        import urllib.error
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            url="http://example.com/webhook",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=None,
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

    def test_error_handling_suppresses_url_error(self):
        """Should suppress URLError without crashing."""
        import urllib.error
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("URL error")):
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

    def test_error_handling_suppresses_json_encode_error(self):
        """Should suppress JSON encoding errors."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("json.dumps", side_effect=TypeError("Cannot serialize")):
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

    def test_request_has_correct_headers(self):
        """POST request should have correct Content-Type header."""
        handler = WebhookHandler(webhook_url="http://example.com/webhook")

        with patch("urllib.request.urlopen") as mock_urlopen:
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

            # Verify request was made with correct headers
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert isinstance(request, urllib.request.Request)
            assert request.get_header("Content-type") == "application/json"


class TestSetupLoggingIdempotency:
    """Test setup_logging() idempotency."""

    def test_multiple_calls_same_handler_count(self):
        """Multiple calls should not add duplicate handlers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    # First call
                    setup_logging()
                    handler_count_1 = len(root_logger.handlers)

                    # Second call
                    setup_logging()
                    handler_count_2 = len(root_logger.handlers)

                    # Third call
                    setup_logging()
                    handler_count_3 = len(root_logger.handlers)

                    assert handler_count_1 == handler_count_2 == handler_count_3
            finally:
                root_logger.handlers = original_handlers

    def test_multiple_calls_same_logger_instance(self):
        """Multiple calls should return the same logger instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    logger1 = setup_logging()
                    logger2 = setup_logging()
                    logger3 = setup_logging()

                    assert logger1 is logger2 is logger3
            finally:
                root_logger.handlers = original_handlers

    def test_idempotency_checks_json_formatter(self):
        """Idempotency check should detect existing JsonFormatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    # First call sets up handlers
                    setup_logging()
                    handlers_after_first = len(root_logger.handlers)

                    # Verify we have handlers
                    assert handlers_after_first > 0

                    # Second call should detect existing JsonFormatter and not add more
                    setup_logging()
                    handlers_after_second = len(root_logger.handlers)

                    assert handlers_after_first == handlers_after_second
            finally:
                root_logger.handlers = original_handlers


class TestTraderModuleIntegration:
    """Test integration with trader module functions."""

    def test_validators_import_without_error(self):
        """validators module should import without errors with logging setup."""
        # Reset and setup logging
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        root_logger.handlers = []

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                log_file = os.path.join(tmpdir, "test.log")
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    setup_logging()

                    # Import should work
                    from trader.validators import validate_price, validate_html_structure, deduplicate_items
                    assert callable(validate_price)
                    assert callable(validate_html_structure)
                    assert callable(deduplicate_items)
        finally:
            root_logger.handlers = original_handlers

    def test_validation_logs_to_file(self):
        """Validation functions should log to configured file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    setup_logging()

                    from trader.validators import validate_price
                    from trader.exceptions import ValidationError

                    # Trigger a validation error that should be logged
                    with pytest.raises(ValidationError):
                        validate_price(-5.0)

                    # Flush handlers
                    for handler in root_logger.handlers:
                        handler.flush()

                    # Check log file
                    with open(log_file, "r") as f:
                        content = f.read()
                        assert "price must be greater than 0" in content or "price" in content
            finally:
                root_logger.handlers = original_handlers

    def test_log_output_is_valid_json(self):
        """All log output should be valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    setup_logging()

                    from trader.validators import deduplicate_items

                    # Trigger logging
                    items = [
                        {"item_hash": "abc", "name": "Item 1"},
                        {"item_hash": "abc", "name": "Item 1 Dup"},
                    ]
                    deduplicate_items(items)

                    # Flush handlers
                    for handler in root_logger.handlers:
                        handler.flush()

                    # Verify all lines are valid JSON
                    with open(log_file, "r") as f:
                        for line in f:
                            if line.strip():
                                parsed = json.loads(line)
                                assert "timestamp" in parsed
                                assert "level" in parsed
                                assert "message" in parsed
            finally:
                root_logger.handlers = original_handlers

    def test_context_passed_to_logs(self):
        """Extra context should be included in log output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    setup_logging()

                    # Log with extra context
                    root_logger.info("Test message", extra={"test_context": "test_value"})

                    # Flush handlers
                    for handler in root_logger.handlers:
                        handler.flush()

                    # Verify context in output
                    with open(log_file, "r") as f:
                        content = f.read()
                        parsed = json.loads(content)
                        assert "context" in parsed
                        assert parsed["context"]["test_context"] == "test_value"
            finally:
                root_logger.handlers = original_handlers


class TestConfigurationIntegration:
    """Test integration with config module."""

    def test_uses_log_level_from_config(self):
        """Should use LOG_LEVEL from config module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    with patch.object(config_module, "LOG_LEVEL", "DEBUG"):
                        setup_logging()
                        assert root_logger.level == logging.DEBUG

                    root_logger.handlers = []

                    with patch.object(config_module, "LOG_LEVEL", "WARNING"):
                        setup_logging()
                        assert root_logger.level == logging.WARNING
            finally:
                root_logger.handlers = original_handlers

    def test_uses_retention_days_from_config(self):
        """Should use LOG_RETENTION_DAYS from config module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    with patch.object(config_module, "LOG_RETENTION_DAYS", 14):
                        setup_logging()

                        # Find TimedRotatingFileHandler
                        file_handlers = [h for h in root_logger.handlers if isinstance(h, TimedRotatingFileHandler)]
                        assert len(file_handlers) == 1
                        assert file_handlers[0].backupCount == 14
            finally:
                root_logger.handlers = original_handlers

    def test_uses_webhook_url_from_config(self):
        """Should use WEBHOOK_URL from config module."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    with patch.object(config_module, "WEBHOOK_URL", "http://config-webhook.com/alert"):
                        setup_logging()

                        # Find WebhookHandler
                        webhook_handlers = [h for h in root_logger.handlers if isinstance(h, WebhookHandler)]
                        assert len(webhook_handlers) == 1
                        assert webhook_handlers[0].webhook_url == "http://config-webhook.com/alert"
            finally:
                root_logger.handlers = original_handlers


class TestEndToEndLogging:
    """End-to-end integration tests for the logging system."""

    def test_full_logging_pipeline(self):
        """Test the complete logging pipeline from logger to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "pipeline.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    # Setup logging
                    logger = setup_logging()

                    # Log messages at different levels
                    logger.debug("Debug message", extra={"debug_info": "value"})
                    logger.info("Info message", extra={"user_id": "123"})
                    logger.warning("Warning message", extra={"alert_type": "threshold"})
                    logger.error("Error message", extra={"error_code": 500})
                    logger.critical("Critical message", extra={"system": "database"})

                    # Flush all handlers
                    for handler in logger.handlers:
                        handler.flush()

                    # Read and verify log file
                    with open(log_file, "r") as f:
                        lines = [line for line in f if line.strip()]

                    # Should have at least some messages
                    assert len(lines) >= 4  # INFO, WARNING, ERROR, CRITICAL

                    # Verify all are valid JSON
                    for line in lines:
                        parsed = json.loads(line)
                        assert "timestamp" in parsed
                        assert "level" in parsed
                        assert "message" in parsed

                    # Verify levels
                    levels = [json.loads(line)["level"] for line in lines]
                    assert "INFO" in levels
                    assert "WARNING" in levels
                    assert "ERROR" in levels
                    assert "CRITICAL" in levels
            finally:
                root_logger.handlers = original_handlers

    def test_log_levels_respect_configuration(self):
        """Log output should respect configured log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "levels.log")

            # Reset root logger
            root_logger = logging.getLogger()
            original_handlers = root_logger.handlers[:]
            root_logger.handlers = []

            try:
                with patch.object(config_module, "LOG_FILE_PATH", log_file):
                    with patch.object(config_module, "LOG_LEVEL", "WARNING"):
                        logger = setup_logging()

                        # These should not be logged
                        logger.debug("Debug - should not appear")
                        logger.info("Info - should not appear")

                        # These should be logged
                        logger.warning("Warning - should appear")
                        logger.error("Error - should appear")

                        # Flush
                        for handler in logger.handlers:
                            handler.flush()

                        # Read and verify
                        with open(log_file, "r") as f:
                            content = f.read()

                        assert "Debug - should not appear" not in content
                        assert "Info - should not appear" not in content
                        assert "Warning - should appear" in content
                        assert "Error - should appear" in content
            finally:
                root_logger.handlers = original_handlers
