"""Integration tests for alert module.

Tests the send_alert function with a real HTTP server to verify webhook
calls and logging in realistic scenarios.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional, Generator

import pytest

from trader.alert import send_alert


class WebhookRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler that captures incoming webhook requests."""
    
    received_requests: List[Dict[str, Any]] = []
    response_status: int = 200
    response_delay: float = 0.0
    
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default request logging."""
        pass
    
    def do_POST(self) -> None:
        """Handle POST requests to the webhook endpoint."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        
        # Store the received request
        WebhookRequestHandler.received_requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": body,
            "payload": json.loads(body) if body else None,
        })
        
        # Simulate delay if configured
        if WebhookRequestHandler.response_delay > 0:
            time.sleep(WebhookRequestHandler.response_delay)
        
        # Send response
        self.send_response(WebhookRequestHandler.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')


class TestAlertWebhookIntegration:
    """Integration tests for alert webhook functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_webhook(self) -> Generator[None, None, None]:
        """Set up and tear down the webhook server."""
        # Clear any previous requests
        WebhookRequestHandler.received_requests = []
        WebhookRequestHandler.response_status = 200
        WebhookRequestHandler.response_delay = 0.0
        
        # Start server on a random available port
        self.server = HTTPServer(("127.0.0.1", 0), WebhookRequestHandler)
        self.server_port = self.server.server_address[1]
        self.webhook_url = f"http://127.0.0.1:{self.server_port}/webhook"
        
        # Start server in a separate thread
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Set the webhook URL environment variable
        os.environ["WEBHOOK_URL"] = self.webhook_url
        
        yield
        
        # Cleanup
        self.server.shutdown()
        self.server_thread.join(timeout=5)
        if "WEBHOOK_URL" in os.environ:
            del os.environ["WEBHOOK_URL"]
    
    def test_webhook_receives_request(self) -> None:
        """Test that send_alert sends a request to the webhook server."""
        result = send_alert("Test webhook message", "info")
        
        # Wait briefly for request to arrive
        time.sleep(0.1)
        
        assert result is True
        assert len(WebhookRequestHandler.received_requests) == 1
    
    def test_webhook_receives_correct_payload_structure(self) -> None:
        """Test that webhook receives correct JSON payload structure."""
        send_alert("Test message", "warning")
        
        # Wait briefly for request to arrive
        time.sleep(0.1)
        
        assert len(WebhookRequestHandler.received_requests) == 1
        payload = WebhookRequestHandler.received_requests[0]["payload"]
        
        # Verify payload structure
        assert "message" in payload
        assert "level" in payload
        assert "timestamp" in payload
        assert "source" in payload
    
    def test_webhook_payload_has_correct_values(self) -> None:
        """Test that webhook receives correct values in payload."""
        send_alert("Critical database failure", "critical")
        
        # Wait briefly for request to arrive
        time.sleep(0.1)
        
        payload = WebhookRequestHandler.received_requests[0]["payload"]
        
        assert payload["message"] == "Critical database failure"
        assert payload["level"] == "critical"
        assert payload["source"] == "trader.alert"
    
    def test_webhook_payload_has_iso_timestamp(self) -> None:
        """Test that webhook receives ISO format timestamp."""
        send_alert("Test message", "info")
        
        # Wait briefly for request to arrive
        time.sleep(0.1)
        
        payload = WebhookRequestHandler.received_requests[0]["payload"]
        timestamp = payload["timestamp"]
        
        # Verify ISO format
        assert isinstance(timestamp, str)
        try:
            datetime.fromisoformat(timestamp.replace("+00:00", ""))
        except ValueError:
            pytest.fail(f"Timestamp '{timestamp}' is not valid ISO format")
        
        # Verify it's a recent timestamp (within last minute)
        timestamp_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = (now - timestamp_dt.replace(tzinfo=timezone.utc)).total_seconds()
        assert abs(diff) < 60, f"Timestamp {timestamp} is not recent"
    
    def test_webhook_receives_different_levels(self) -> None:
        """Test that webhook receives different alert levels."""
        levels = ["info", "warning", "error", "critical"]
        
        for level in levels:
            WebhookRequestHandler.received_requests.clear()
            send_alert(f"Test {level}", level)  # type: ignore[arg-type]
            time.sleep(0.1)
            
            assert len(WebhookRequestHandler.received_requests) == 1
            assert WebhookRequestHandler.received_requests[0]["payload"]["level"] == level
    
    def test_webhook_custom_path(self) -> None:
        """Test that webhook calls the correct path."""
        send_alert("Test message", "info")
        
        # Wait briefly for request to arrive
        time.sleep(0.1)
        
        assert WebhookRequestHandler.received_requests[0]["path"] == "/webhook"


class TestAlertWebhookFailureHandling:
    """Tests for webhook failure handling."""
    
    @pytest.fixture(autouse=True)
    def setup_webhook(self) -> Generator[None, None, None]:
        """Set up and tear down the webhook server."""
        # Clear any previous requests
        WebhookRequestHandler.received_requests = []
        WebhookRequestHandler.response_status = 200
        WebhookRequestHandler.response_delay = 0.0
        
        # Start server on a random available port
        self.server = HTTPServer(("127.0.0.1", 0), WebhookRequestHandler)
        self.server_port = self.server.server_address[1]
        self.webhook_url = f"http://127.0.0.1:{self.server_port}/webhook"
        
        # Start server in a separate thread
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Set the webhook URL environment variable
        os.environ["WEBHOOK_URL"] = self.webhook_url
        
        yield
        
        # Cleanup
        self.server.shutdown()
        self.server_thread.join(timeout=5)
        if "WEBHOOK_URL" in os.environ:
            del os.environ["WEBHOOK_URL"]
    
    def test_returns_false_on_4xx_error(self) -> None:
        """Test that send_alert returns False on 4xx response."""
        WebhookRequestHandler.response_status = 404
        
        result = send_alert("Test message", "info")
        
        assert result is False
    
    def test_returns_false_on_400_bad_request(self) -> None:
        """Test that send_alert returns False on 400 response."""
        WebhookRequestHandler.response_status = 400
        
        result = send_alert("Test message", "info")
        
        assert result is False
    
    def test_returns_false_on_5xx_error(self) -> None:
        """Test that send_alert returns False on 5xx response."""
        WebhookRequestHandler.response_status = 500
        
        result = send_alert("Test message", "info")
        
        assert result is False
    
    def test_returns_false_on_503_service_unavailable(self) -> None:
        """Test that send_alert returns False on 503 response."""
        WebhookRequestHandler.response_status = 503
        
        result = send_alert("Test message", "info")
        
        assert result is False
    
    def test_returns_true_on_2xx_success(self) -> None:
        """Test that send_alert returns True on 2xx response."""
        WebhookRequestHandler.response_status = 201
        
        result = send_alert("Test message", "info")
        
        assert result is True
    
    def test_returns_true_on_204_no_content(self) -> None:
        """Test that send_alert returns True on 204 response."""
        WebhookRequestHandler.response_status = 204
        
        result = send_alert("Test message", "info")
        
        assert result is True


class TestAlertWebhookTimeout:
    """Tests for webhook timeout handling."""
    
    @pytest.fixture(autouse=True)
    def setup_webhook(self) -> Generator[None, None, None]:
        """Set up and tear down the webhook server."""
        # Clear any previous requests
        WebhookRequestHandler.received_requests = []
        WebhookRequestHandler.response_status = 200
        WebhookRequestHandler.response_delay = 0.0
        
        # Start server on a random available port
        self.server = HTTPServer(("127.0.0.1", 0), WebhookRequestHandler)
        self.server_port = self.server.server_address[1]
        self.webhook_url = f"http://127.0.0.1:{self.server_port}/webhook"
        
        # Start server in a separate thread
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Set the webhook URL environment variable
        os.environ["WEBHOOK_URL"] = self.webhook_url
        
        yield
        
        # Cleanup
        self.server.shutdown()
        self.server_thread.join(timeout=5)
        if "WEBHOOK_URL" in os.environ:
            del os.environ["WEBHOOK_URL"]
    
    def test_returns_false_on_timeout(self) -> None:
        """Test that send_alert returns False when webhook times out."""
        # Set a long delay to trigger timeout (default timeout is 30s, we'll set 35s)
        WebhookRequestHandler.response_delay = 35.0
        
        start_time = time.time()
        result = send_alert("Test message", "info")
        elapsed = time.time() - start_time
        
        # Should return False due to timeout
        assert result is False
        # Should complete before the 35 second delay
        assert elapsed < 35.0, f"Request took {elapsed}s, should timeout before 35s"


class TestAlertWebhookLogging:
    """Tests for alert logging in integration scenarios."""
    
    @pytest.fixture(autouse=True)
    def setup_webhook(self) -> Generator[None, None, None]:
        """Set up and tear down the webhook server."""
        # Clear any previous requests
        WebhookRequestHandler.received_requests = []
        WebhookRequestHandler.response_status = 200
        WebhookRequestHandler.response_delay = 0.0
        
        # Start server on a random available port
        self.server = HTTPServer(("127.0.0.1", 0), WebhookRequestHandler)
        self.server_port = self.server.server_address[1]
        self.webhook_url = f"http://127.0.0.1:{self.server_port}/webhook"
        
        # Start server in a separate thread
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Set the webhook URL environment variable
        os.environ["WEBHOOK_URL"] = self.webhook_url
        
        yield
        
        # Cleanup
        self.server.shutdown()
        self.server_thread.join(timeout=5)
        if "WEBHOOK_URL" in os.environ:
            del os.environ["WEBHOOK_URL"]
    
    def test_logs_alert_before_webhook_call(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that alert is logged before webhook call completes."""
        caplog.set_level(logging.INFO)
        
        # Add a small delay to make race condition more detectable
        WebhookRequestHandler.response_delay = 0.1
        
        send_alert("Test message", "info")
        
        # Wait for webhook to complete
        time.sleep(0.2)
        
        # Verify log was created
        assert len(caplog.records) == 1
        assert "[ALERT INFO]" in caplog.records[0].message
        assert "trader.alert" in caplog.records[0].name
    
    def test_logs_even_on_webhook_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that alert is logged even when webhook fails."""
        caplog.set_level(logging.INFO)
        
        WebhookRequestHandler.response_status = 500
        
        send_alert("Test failure message", "error")
        
        time.sleep(0.1)
        
        # Log should still be created even though webhook returned 500
        assert len(caplog.records) == 1
        assert "[ALERT ERROR]" in caplog.records[0].message
    
    def test_logs_critical_at_critical_level(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that critical alerts log at CRITICAL level."""
        caplog.set_level(logging.CRITICAL)
        
        send_alert("Critical test", "critical")
        
        time.sleep(0.1)
        
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.CRITICAL
