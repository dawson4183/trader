"""Tests for the trader module structure."""

import unittest
from unittest.mock import patch, MagicMock
import urllib.error

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


if __name__ == "__main__":
    unittest.main()
