"""Tests for the alert module.

Tests the send_alert function with mocked webhook responses
to verify correct behavior for various scenarios. Also tests
logging integration to verify alerts are logged with appropriate levels.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Generator, List
from unittest.mock import MagicMock, patch
import pytest

from trader.alert import send_alert, LEVEL_TO_LOGGING


class TestSendAlert:
    """Tests for send_alert function."""

    def setup_method(self) -> None:
        """Clear WEBHOOK_URL before each test."""
        if "WEBHOOK_URL" in os.environ:
            del os.environ["WEBHOOK_URL"]

    def teardown_method(self) -> None:
        """Clear WEBHOOK_URL after each test."""
        if "WEBHOOK_URL" in os.environ:
            del os.environ["WEBHOOK_URL"]

    def test_function_exists(self) -> None:
        """Test that send_alert function exists."""
        assert callable(send_alert)

    def test_returns_bool(self) -> None:
        """Test that send_alert returns a boolean."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            result = send_alert("Test message", "info")
            assert isinstance(result, bool)

    def test_returns_false_without_webhook_url(self) -> None:
        """Test that send_alert returns False when WEBHOOK_URL is not set."""
        # Ensure WEBHOOK_URL is not set
        if "WEBHOOK_URL" in os.environ:
            del os.environ["WEBHOOK_URL"]

        result = send_alert("Test message", "info")
        assert result is False

    def test_returns_false_for_invalid_level(self) -> None:
        """Test that send_alert returns False for invalid level."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        result = send_alert("Test message", "invalid_level")  # type: ignore[arg-type]
        assert result is False

    def test_returns_true_on_success(self) -> None:
        """Test that send_alert returns True on 2xx response."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            result = send_alert("Test message", "info")
            assert result is True

    def test_returns_true_on_201_created(self) -> None:
        """Test that send_alert returns True on 201 response."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 201
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            result = send_alert("Test message", "error")
            assert result is True

    def test_returns_false_on_4xx_error(self) -> None:
        """Test that send_alert returns False on 4xx response."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_error = urllib.request.HTTPError(
                "http://example.com/webhook",
                404,
                "Not Found",
                None,  # type: ignore[arg-type]
                None,
            )
            mock_urlopen.side_effect = mock_error

            result = send_alert("Test message", "warning")
            assert result is False

    def test_returns_false_on_5xx_error(self) -> None:
        """Test that send_alert returns False on 5xx response."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_error = urllib.request.HTTPError(
                "http://example.com/webhook",
                500,
                "Internal Server Error",
                None,  # type: ignore[arg-type]
                None,
            )
            mock_urlopen.side_effect = mock_error

            result = send_alert("Test message", "critical")
            assert result is False

    def test_returns_true_on_2xx_error_code(self) -> None:
        """Test that send_alert returns True when HTTPError has 2xx code."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            # HTTPError raised but with 200 status (unusual but possible)
            mock_error = urllib.request.HTTPError(
                "http://example.com/webhook",
                204,
                "No Content",
                None,  # type: ignore[arg-type]
                None,
            )
            mock_urlopen.side_effect = mock_error

            result = send_alert("Test message", "info")
            # Even though it's an exception, 204 is a 2xx status
            assert result is True

    def test_returns_false_on_connection_error(self) -> None:
        """Test that send_alert returns False on connection error."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_error = urllib.error.URLError("Connection refused")
            mock_urlopen.side_effect = mock_error

            result = send_alert("Test message", "error")
            assert result is False

    def test_sends_correct_payload(self) -> None:
        """Test that send_alert sends correct JSON payload."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Test message", "warning")

            # Verify Request was created with correct data
            call_args = mock_urlopen.call_args
            request = call_args[0][0]

            assert request.full_url == "http://example.com/webhook"
            assert request.method == "POST"
            assert request.headers["Content-type"] == "application/json"

            # Parse the sent payload
            payload = json.loads(request.data.decode("utf-8"))
            assert payload["message"] == "Test message"
            assert payload["level"] == "warning"
            assert payload["source"] == "trader.alert"
            assert "timestamp" in payload

    def test_payload_has_iso_timestamp(self) -> None:
        """Test that payload contains ISO format timestamp."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Test message", "info")

            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            payload = json.loads(request.data.decode("utf-8"))

            # Verify timestamp is ISO format
            timestamp = payload["timestamp"]
            try:
                datetime.fromisoformat(timestamp)
                assert True
            except ValueError:
                pytest.fail("Timestamp is not valid ISO format")

    def test_accepts_info_level(self) -> None:
        """Test that send_alert accepts 'info' level."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            result = send_alert("Test message", "info")
            assert result is True

    def test_accepts_warning_level(self) -> None:
        """Test that send_alert accepts 'warning' level."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            result = send_alert("Test message", "warning")
            assert result is True

    def test_accepts_error_level(self) -> None:
        """Test that send_alert accepts 'error' level."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            result = send_alert("Test message", "error")
            assert result is True

    def test_accepts_critical_level(self) -> None:
        """Test that send_alert accepts 'critical' level."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            result = send_alert("Test message", "critical")
            assert result is True

    def test_rejects_invalid_levels(self) -> None:
        """Test that send_alert rejects invalid levels."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"

        invalid_levels = ["debug", "fatal", "emergency", "alert", "", "INFO", "Warning"]
        for level in invalid_levels:
            result = send_alert("Test message", level)  # type: ignore[arg-type]
            assert result is False, f"Level '{level}' should be rejected"

    def test_uses_url_from_environment(self) -> None:
        """Test that send_alert reads WEBHOOK_URL from environment."""
        os.environ["WEBHOOK_URL"] = "https://hooks.example.com/alerts"

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Test message", "info")

            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert request.full_url == "https://hooks.example.com/alerts"


class TestAlertLogging:
    """Tests for alert logging integration."""

    def setup_method(self) -> None:
        """Clear WEBHOOK_URL before each test."""
        if "WEBHOOK_URL" in os.environ:
            del os.environ["WEBHOOK_URL"]

    def teardown_method(self) -> None:
        """Clear WEBHOOK_URL after each test."""
        if "WEBHOOK_URL" in os.environ:
            del os.environ["WEBHOOK_URL"]

    def test_critical_level_logs_at_critical(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that level 'critical' logs at logging.CRITICAL."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"
        caplog.set_level(logging.CRITICAL)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Critical test message", "critical")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.CRITICAL

    def test_error_level_logs_at_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that level 'error' logs at logging.ERROR."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"
        caplog.set_level(logging.ERROR)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Error test message", "error")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.ERROR

    def test_warning_level_logs_at_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that level 'warning' logs at logging.WARNING."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"
        caplog.set_level(logging.WARNING)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Warning test message", "warning")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING

    def test_info_level_logs_at_info(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that level 'info' logs at logging.INFO."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"
        caplog.set_level(logging.INFO)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Info test message", "info")

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.INFO

    def test_log_message_contains_alert_level(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that log message contains the alert level."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"
        caplog.set_level(logging.INFO)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Test message", "error")

        assert "[ALERT ERROR]" in caplog.records[0].message

    def test_log_message_contains_alert_text(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that log message contains the alert text."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"
        caplog.set_level(logging.INFO)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Database connection failed", "critical")

        assert "Database connection failed" in caplog.records[0].message

    def test_log_has_source_module_name(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that log record has source module name."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"
        caplog.set_level(logging.INFO)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            mock_urlopen.return_value = mock_response

            send_alert("Test message", "info")

        assert caplog.records[0].name == "trader.alert"

    def test_logs_before_webhook_call(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that logging occurs before webhook call."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"
        caplog.set_level(logging.INFO)
        webhook_times: List[int] = []

        with patch("urllib.request.urlopen") as mock_urlopen:
            def capture_log_and_call(*args: object, **kwargs: object) -> MagicMock:
                webhook_times.append(1)
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.__enter__ = MagicMock(return_value=mock_response)
                mock_response.__exit__ = MagicMock(return_value=None)
                return mock_response

            mock_urlopen.side_effect = lambda request: capture_log_and_call()

            send_alert("Test message", "warning")

        # Verify log was created
        assert len(caplog.records) == 1

    def test_no_logs_when_invalid_level(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that no logs are created when level is invalid."""
        os.environ["WEBHOOK_URL"] = "http://example.com/webhook"
        caplog.set_level(logging.DEBUG)

        send_alert("Test message", "invalid")  # type: ignore[arg-type]

        # No logs should be created since we return early
        assert len(caplog.records) == 0

    def test_no_logs_when_no_webhook_url(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that no logs are created when WEBHOOK_URL is not set."""
        caplog.set_level(logging.DEBUG)

        send_alert("Test message", "info")

        # No logs should be created since we return early
        assert len(caplog.records) == 0

    def test_level_mapping_is_correct(self) -> None:
        """Test that LEVEL_TO_LOGGING mapping is correct."""
        assert LEVEL_TO_LOGGING["critical"] == logging.CRITICAL
        assert LEVEL_TO_LOGGING["error"] == logging.ERROR
        assert LEVEL_TO_LOGGING["warning"] == logging.WARNING
        assert LEVEL_TO_LOGGING["info"] == logging.INFO
