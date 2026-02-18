"""Tests for the trader module structure."""

import unittest
from unittest.mock import patch, MagicMock, Mock, call
import urllib.error
import io

from trader import Scraper
from trader.scraper import HTTPClient


class TestHTTPClient(unittest.TestCase):
    """Test cases for HTTPClient."""

    def test_init_default_timeout(self) -> None:
        """Test HTTPClient initializes with default timeout."""
        client = HTTPClient()
        self.assertEqual(client.timeout, 30)

    def test_init_custom_timeout(self) -> None:
        """Test HTTPClient initializes with custom timeout."""
        client = HTTPClient(timeout=60)
        self.assertEqual(client.timeout, 60)

    @patch("urllib.request.urlopen")
    def test_get_success(self, mock_urlopen: MagicMock) -> None:
        """Test HTTPClient.get returns response content."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"test content"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = HTTPClient()
        result = client.get("http://example.com")

        self.assertEqual(result, "test content")
        mock_urlopen.assert_called_once_with("http://example.com", timeout=30)

    @patch("urllib.request.urlopen")
    def test_get_raises_on_error(self, mock_urlopen: MagicMock) -> None:
        """Test HTTPClient.get raises on URL error."""
        mock_urlopen.side_effect = urllib.error.URLError("Connection failed")

        client = HTTPClient()
        with self.assertRaises(urllib.error.URLError):
            client.get("http://example.com")


class TestScraper(unittest.TestCase):
    """Test cases for Scraper class."""

    def test_init_with_default_client(self) -> None:
        """Test Scraper initializes with default HTTPClient."""
        scraper = Scraper()
        self.assertIsInstance(scraper.client, HTTPClient)

    def test_init_with_custom_client(self) -> None:
        """Test Scraper initializes with custom client."""
        custom_client = HTTPClient(timeout=10)
        scraper = Scraper(client=custom_client)
        self.assertEqual(scraper.client, custom_client)

    @patch("trader.scraper.HTTPClient.get")
    def test_fetch_calls_client_get(self, mock_get: MagicMock) -> None:
        """Test Scraper.fetch delegates to client.get."""
        mock_get.return_value = "content"
        scraper = Scraper()

        result = scraper.fetch("http://example.com")

        self.assertEqual(result, "content")
        mock_get.assert_called_once_with("http://example.com")

    @patch("trader.scraper.HTTPClient.get")
    def test_scrape_returns_dict(self, mock_get: MagicMock) -> None:
        """Test Scraper.scrape returns structured data."""
        mock_get.return_value = "page content"
        scraper = Scraper()

        result = scraper.scrape("http://example.com")

        self.assertEqual(result["url"], "http://example.com")
        self.assertEqual(result["content"], "page content")
        self.assertEqual(result["status"], "fetched")


class TestModuleStructure(unittest.TestCase):
    """Test cases for module structure and exports."""

    def test_trader_package_exports_scraper(self) -> None:
        """Test that trader package exports Scraper class."""
        import trader
        self.assertTrue(hasattr(trader, "Scraper"))
        self.assertEqual(trader.Scraper, Scraper)

    def test_scraper_module_has_httpclient(self) -> None:
        """Test that scraper module has HTTPClient class."""
        from trader.scraper import HTTPClient as ImportedClient
        self.assertTrue(callable(ImportedClient))

    def test_all_exports_defined(self) -> None:
        """Test that __all__ is properly defined."""
        import trader
        self.assertEqual(trader.__all__, ["Scraper"])


class TestScraperRetryBehavior(unittest.TestCase):
    """Test cases for Scraper retry decorator integration."""

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")  # Speed up tests by mocking sleep
    def test_fetch_retries_on_500_error_then_succeeds(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that fetch retries on HTTP 500 and succeeds on next attempt."""
        # First call raises 500, second call succeeds
        mock_get.side_effect = [
            urllib.error.HTTPError(
                "http://example.com", 500, "Internal Server Error", {}, io.BytesIO(b"")
            ),
            "success content"
        ]
        scraper = Scraper()

        result = scraper.fetch("http://example.com")

        self.assertEqual(result, "success content")
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()  # Should have one backoff delay

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")
    def test_fetch_retries_on_429_error(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that fetch retries on HTTP 429 Too Many Requests."""
        mock_get.side_effect = [
            urllib.error.HTTPError(
                "http://example.com", 429, "Too Many Requests", {}, io.BytesIO(b"")
            ),
            urllib.error.HTTPError(
                "http://example.com", 429, "Too Many Requests", {}, io.BytesIO(b"")
            ),
            "success content"
        ]
        scraper = Scraper()

        result = scraper.fetch("http://example.com")

        self.assertEqual(result, "success content")
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")
    def test_fetch_retries_on_connection_error(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that fetch retries on ConnectionError."""
        mock_get.side_effect = [
            ConnectionError("Connection refused"),
            ConnectionError("Connection reset"),
            "success content"
        ]
        scraper = Scraper()

        result = scraper.fetch("http://example.com")

        self.assertEqual(result, "success content")
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")
    def test_fetch_retries_on_timeout_error(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that fetch retries on TimeoutError."""
        mock_get.side_effect = [
            TimeoutError("Request timed out"),
            "success content"
        ]
        scraper = Scraper()

        result = scraper.fetch("http://example.com")

        self.assertEqual(result, "success content")
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")
    def test_fetch_raises_non_retryable_404_immediately(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that fetch raises 404 immediately without retrying."""
        mock_get.side_effect = urllib.error.HTTPError(
            "http://example.com", 404, "Not Found", {}, io.BytesIO(b"")
        )
        scraper = Scraper()

        with self.assertRaises(urllib.error.HTTPError) as context:
            scraper.fetch("http://example.com")

        self.assertEqual(context.exception.code, 404)
        self.assertEqual(mock_get.call_count, 1)  # No retries
        mock_sleep.assert_not_called()

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")
    def test_fetch_raises_non_retryable_400_immediately(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that fetch raises 400 Bad Request immediately without retrying."""
        mock_get.side_effect = urllib.error.HTTPError(
            "http://example.com", 400, "Bad Request", {}, io.BytesIO(b"")
        )
        scraper = Scraper()

        with self.assertRaises(urllib.error.HTTPError) as context:
            scraper.fetch("http://example.com")

        self.assertEqual(context.exception.code, 400)
        self.assertEqual(mock_get.call_count, 1)  # No retries
        mock_sleep.assert_not_called()

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")
    def test_fetch_raises_after_max_attempts_exhausted(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that fetch raises after 5 failed attempts."""
        # 5 consecutive 500 errors
        mock_get.side_effect = [
            urllib.error.HTTPError(
                "http://example.com", 500, "Internal Server Error", {}, io.BytesIO(b"")
            ),
            urllib.error.HTTPError(
                "http://example.com", 500, "Internal Server Error", {}, io.BytesIO(b"")
            ),
            urllib.error.HTTPError(
                "http://example.com", 500, "Internal Server Error", {}, io.BytesIO(b"")
            ),
            urllib.error.HTTPError(
                "http://example.com", 500, "Internal Server Error", {}, io.BytesIO(b"")
            ),
            urllib.error.HTTPError(
                "http://example.com", 500, "Internal Server Error", {}, io.BytesIO(b"")
            ),
        ]
        scraper = Scraper()

        with self.assertRaises(urllib.error.HTTPError) as context:
            scraper.fetch("http://example.com")

        self.assertEqual(context.exception.code, 500)
        self.assertEqual(mock_get.call_count, 5)  # Max 5 attempts
        self.assertEqual(mock_sleep.call_count, 4)  # 4 delays between 5 attempts

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")
    def test_fetch_exponential_backoff_delays(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that fetch uses exponential backoff between retries."""
        mock_get.side_effect = [
            ConnectionError("error 1"),
            ConnectionError("error 2"),
            ConnectionError("error 3"),
            ConnectionError("error 4"),
            "success"
        ]
        scraper = Scraper()

        scraper.fetch("http://example.com")

        # Exponential backoff: 1s, 2s, 4s, 8s
        expected_delays = [1.0, 2.0, 4.0, 8.0]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(actual_delays, expected_delays)

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")
    def test_scrape_method_uses_retry_decorated_fetch(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that scrape() uses the retry-decorated fetch()."""
        mock_get.side_effect = [
            urllib.error.HTTPError(
                "http://example.com", 503, "Service Unavailable", {}, io.BytesIO(b"")
            ),
            "page content"
        ]
        scraper = Scraper()

        result = scraper.scrape("http://example.com")

        self.assertEqual(result["url"], "http://example.com")
        self.assertEqual(result["content"], "page content")
        self.assertEqual(result["status"], "fetched")
        self.assertEqual(mock_get.call_count, 2)  # Retried once

    @patch("trader.scraper.HTTPClient.get")
    def test_fetch_success_no_retry_needed(self, mock_get: MagicMock) -> None:
        """Test that fetch succeeds on first attempt without any retries."""
        mock_get.return_value = "immediate success"
        scraper = Scraper()

        result = scraper.fetch("http://example.com")

        self.assertEqual(result, "immediate success")
        mock_get.assert_called_once()

    def test_scraper_imports_retry_decorator(self) -> None:
        """Test that Scraper module properly imports retry_with_backoff."""
        from trader.scraper import retry_with_backoff
        self.assertTrue(callable(retry_with_backoff))


if __name__ == "__main__":
    unittest.main()
