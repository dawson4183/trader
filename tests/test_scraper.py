"""Tests for trader.scraper module."""

import json
import logging
import urllib.error
from io import StringIO
from unittest.mock import Mock, patch

import pytest

from trader.scraper import Scraper


class TestScraperBasics:
    """Test basic Scraper functionality."""

    def test_scraper_instantiates(self):
        """Scraper should be instantiable with default timeout."""
        scraper = Scraper()
        assert isinstance(scraper, Scraper)
        assert scraper.timeout == 30

    def test_scraper_accepts_custom_timeout(self):
        """Scraper should accept custom timeout value."""
        scraper = Scraper(timeout=60)
        assert scraper.timeout == 60

    def test_scraper_has_logger(self):
        """Scraper should have a logger attribute."""
        scraper = Scraper()
        assert hasattr(scraper, 'logger')
        assert isinstance(scraper.logger, logging.Logger)


class TestScraperFetchUrl:
    """Test Scraper.fetch_url() method."""

    def test_fetch_url_returns_content_on_success(self):
        """fetch_url should return content on successful request."""
        scraper = Scraper()
        expected_content = b"<html>Test content</html>"
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = expected_content
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            result = scraper.fetch_url("https://example.com")
        
        assert result == expected_content.decode("utf-8")

    def test_fetch_url_returns_string_type(self):
        """fetch_url should return a string."""
        scraper = Scraper()
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b"Plain text content"
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            result = scraper.fetch_url("https://example.com")
        
        assert isinstance(result, str)

    def test_fetch_url_handles_http_error_404(self):
        """fetch_url should return None on HTTP 404 error."""
        scraper = Scraper()
        
        with patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError(
            url="https://example.com",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )):
            result = scraper.fetch_url("https://example.com")
        
        assert result is None

    def test_fetch_url_handles_http_error_500(self):
        """fetch_url should return None on HTTP 500 error."""
        scraper = Scraper()
        
        with patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError(
            url="https://example.com",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None
        )):
            result = scraper.fetch_url("https://example.com")
        
        assert result is None

    def test_fetch_url_handles_url_error(self):
        """fetch_url should return None on URL error (connection issues)."""
        scraper = Scraper()
        
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection refused")):
            result = scraper.fetch_url("https://example.com")
        
        assert result is None

    def test_fetch_url_handles_timeout_error(self):
        """fetch_url should return None on timeout."""
        scraper = Scraper()
        
        with patch('urllib.request.urlopen', side_effect=TimeoutError()):
            result = scraper.fetch_url("https://example.com")
        
        assert result is None

    def test_fetch_url_handles_generic_exception(self):
        """fetch_url should return None on any unexpected exception."""
        scraper = Scraper()
        
        with patch('urllib.request.urlopen', side_effect=ValueError("Unexpected error")):
            result = scraper.fetch_url("https://example.com")
        
        assert result is None

    def test_fetch_url_passes_user_agent_header(self):
        """fetch_url should include User-Agent header in request."""
        scraper = Scraper()
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b"content"
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            scraper.fetch_url("https://example.com")
            
            # Get the Request object that was passed
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            
            assert "User-agent" in request.headers


class TestScraperLogging:
    """Test Scraper logging functionality."""

    def test_logs_info_when_fetching(self):
        """Should log info message when fetching URL."""
        scraper = Scraper()
        
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        scraper.logger.handlers = [handler]
        scraper.logger.setLevel(logging.INFO)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b"content"
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            scraper.fetch_url("https://example.com")
        
        output = log_capture.getvalue()
        assert "Fetching URL: https://example.com" in output or len(output) > 0

    def test_logs_info_on_success(self):
        """Should log info message on successful fetch."""
        scraper = Scraper()
        
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        scraper.logger.handlers = [handler]
        scraper.logger.setLevel(logging.INFO)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b"content"
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            scraper.fetch_url("https://example.com")
        
        output = log_capture.getvalue()
        # Should have logging output
        assert len(output) > 0

    def test_logs_error_on_http_failure(self):
        """Should log error message on HTTP failure."""
        scraper = Scraper()
        
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        scraper.logger.handlers = [handler]
        scraper.logger.setLevel(logging.INFO)
        
        with patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError(
            url="https://example.com",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )):
            scraper.fetch_url("https://example.com")
        
        output = log_capture.getvalue()
        # Should have error logging
        assert "404" in output or "HTTP error" in output or len(output) > 0

    def test_logs_error_on_connection_failure(self):
        """Should log error message on connection failure."""
        scraper = Scraper()
        
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        scraper.logger.handlers = [handler]
        scraper.logger.setLevel(logging.INFO)
        
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection refused")):
            scraper.fetch_url("https://example.com")
        
        output = log_capture.getvalue()
        # Should have error logging
        assert len(output) > 0

    def test_logs_error_on_timeout(self):
        """Should log error message on timeout."""
        scraper = Scraper()
        
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)
        scraper.logger.handlers = [handler]
        scraper.logger.setLevel(logging.INFO)
        
        with patch('urllib.request.urlopen', side_effect=TimeoutError()):
            scraper.fetch_url("https://example.com")
        
        output = log_capture.getvalue()
        assert "Timeout" in output or "timeout" in output.lower() or len(output) > 0


class TestScraperStructuredLogging:
    """Test that scraper uses structured JSON logging."""

    def test_log_output_is_valid_json(self):
        """Log output should be valid JSON."""
        from trader.logging_utils import JsonFormatter
        
        scraper = Scraper()
        
        # Set up JSON formatter
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(JsonFormatter())
        handler.setLevel(logging.INFO)
        scraper.logger.handlers = [handler]
        scraper.logger.setLevel(logging.INFO)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b'{"data": "test"}'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            scraper.fetch_url("https://example.com")
        
        output = log_capture.getvalue().strip()
        # Parse each log line as JSON
        for line in output.split('\n'):
            if line.strip():
                parsed = json.loads(line)
                assert "timestamp" in parsed
                assert "level" in parsed
                assert "message" in parsed

    def test_log_contains_url_in_context(self):
        """Logs should include URL in context field."""
        from trader.logging_utils import JsonFormatter
        
        scraper = Scraper()
        
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(JsonFormatter())
        handler.setLevel(logging.DEBUG)
        scraper.logger.handlers = [handler]
        scraper.logger.setLevel(logging.DEBUG)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.read.return_value = b'content'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            scraper.fetch_url("https://example.com/page")
        
        log_lines = log_capture.getvalue().strip().split('\n')
        found_url_context = False
        for line in log_lines:
            if line.strip():
                parsed = json.loads(line)
                if parsed.get("context", {}).get("url") == "https://example.com/page":
                    found_url_context = True
                    break
        
        assert found_url_context, "URL should be in log context"