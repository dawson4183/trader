"""Tests for the alert module.

Tests the send_alert function with mocked webhook responses
to verify correct behavior for various scenarios.
"""

import json
import os
import urllib.request
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import MagicMock, patch
import pytest

from trader.alert import send_alert


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
                {},
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
                {},
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
                {},
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
            mock_error = urllib.request.URLError("Connection refused")
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
            assert payload["source"] == "trader"
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
