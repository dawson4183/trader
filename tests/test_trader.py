"""Tests for the trader module structure."""

import unittest
from unittest.mock import patch, MagicMock, Mock, call
import urllib.error
import io
import time

from trader import Scraper
from trader.scraper import HTTPClient
from trader.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState


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
        self.assertEqual(trader.__all__, ["Scraper", "CircuitBreakerError"])


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


class TestScraperCircuitBreakerIntegration(unittest.TestCase):
    """Test cases for Scraper circuit breaker integration."""

    def test_scraper_initializes_with_default_circuit_breaker(self) -> None:
        """Test Scraper initializes with default circuit breaker."""
        scraper = Scraper()
        self.assertIsInstance(scraper.circuit_breaker, CircuitBreaker)
        self.assertEqual(scraper.circuit_breaker.name, "scraper")
        self.assertEqual(scraper.circuit_breaker.failure_threshold, 5)
        self.assertEqual(scraper.circuit_breaker.recovery_timeout, 30.0)

    def test_scraper_initializes_with_custom_circuit_breaker(self) -> None:
        """Test Scraper initializes with custom circuit breaker instance."""
        custom_cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0, name="custom")
        scraper = Scraper(circuit_breaker=custom_cb)
        self.assertEqual(scraper.circuit_breaker, custom_cb)
        self.assertEqual(scraper.circuit_breaker.name, "custom")

    def test_scraper_initializes_with_circuit_breaker_config(self) -> None:
        """Test Scraper initializes with circuit breaker config dict."""
        config = {
            'failure_threshold': 3,
            'recovery_timeout': 15.0,
            'name': 'configured-cb'
        }
        scraper = Scraper(circuit_breaker_config=config)
        self.assertEqual(scraper.circuit_breaker.failure_threshold, 3)
        self.assertEqual(scraper.circuit_breaker.recovery_timeout, 15.0)
        self.assertEqual(scraper.circuit_breaker.name, "configured-cb")

    def test_circuit_breaker_takes_precedence_over_config(self) -> None:
        """Test circuit_breaker parameter takes precedence over config."""
        custom_cb = CircuitBreaker(failure_threshold=2, name="instance")
        config = {'failure_threshold': 10, 'name': 'config'}
        scraper = Scraper(circuit_breaker=custom_cb, circuit_breaker_config=config)
        self.assertEqual(scraper.circuit_breaker.name, "instance")
        self.assertEqual(scraper.circuit_breaker.failure_threshold, 2)

    def test_fetch_passes_through_circuit_breaker(self) -> None:
        """Test fetch() calls pass through circuit breaker."""
        mock_cb = MagicMock()
        mock_cb.call.return_value = "fetched content"
        
        scraper = Scraper(circuit_breaker=mock_cb)
        result = scraper.fetch("http://example.com")
        
        self.assertEqual(result, "fetched content")
        mock_cb.call.assert_called_once()
        # Check that the wrapped method is passed to call()
        self.assertEqual(mock_cb.call.call_args[0][0].__name__, '_fetch_with_retry')

    @patch("trader.scraper.HTTPClient.get")
    def test_circuit_breaker_records_success(self, mock_get: MagicMock) -> None:
        """Test successful fetch records success with circuit breaker."""
        mock_get.return_value = "success content"
        scraper = Scraper()
        
        result = scraper.fetch("http://example.com")
        
        self.assertEqual(result, "success content")
        self.assertEqual(scraper.circuit_breaker.failure_count, 0)
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.CLOSED)

    @patch("trader.scraper.HTTPClient.get")
    def test_circuit_breaker_records_failure(self, mock_get: MagicMock) -> None:
        """Test failed fetch records failure with circuit breaker."""
        mock_get.side_effect = ConnectionError("Connection refused")
        scraper = Scraper(circuit_breaker_config={'failure_threshold': 5})
        
        with self.assertRaises(ConnectionError):
            scraper.fetch("http://example.com")
        
        # After one failure, failure count should be 1, state still CLOSED
        self.assertEqual(scraper.circuit_breaker.failure_count, 1)
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.CLOSED)

    @patch("trader.scraper.HTTPClient.get")
    @patch("trader.circuit_breaker.time.time")
    def test_circuit_breaker_opens_after_threshold(self, mock_time: MagicMock, mock_get: MagicMock) -> None:
        """Test circuit opens after failure_threshold failures."""
        mock_time.return_value = 1000.0
        mock_get.side_effect = ConnectionError("Connection refused")
        
        scraper = Scraper(circuit_breaker_config={'failure_threshold': 3})
        
        # 3 failures to open circuit
        for _ in range(3):
            with self.assertRaises(ConnectionError):
                scraper.fetch("http://example.com")
        
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.OPEN)
        self.assertEqual(scraper.circuit_breaker.failure_count, 3)

    @patch("trader.scraper.HTTPClient.get")
    @patch("trader.circuit_breaker.time.time")
    def test_circuit_breaker_raises_when_open(self, mock_time: MagicMock, mock_get: MagicMock) -> None:
        """Test CircuitBreakerError raised when circuit is OPEN."""
        mock_time.return_value = 1000.0
        # Retry decorator will try 5 times, so provide 5 failures
        mock_get.side_effect = [ConnectionError("fail")] * 5
        
        scraper = Scraper(circuit_breaker_config={'failure_threshold': 1, 'name': 'test-circuit'})
        
        # Open the circuit with 1 failure (after all 5 retries are exhausted)
        with self.assertRaises(ConnectionError):
            scraper.fetch("http://example.com")
        
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.OPEN)
        # Circuit breaker saw 1 failure (after retries exhausted)
        self.assertEqual(scraper.circuit_breaker.failure_count, 1)
        
        # Next call should raise CircuitBreakerError immediately
        with self.assertRaises(CircuitBreakerError) as ctx:
            scraper.fetch("http://example.com")
        
        self.assertIn("test-circuit", str(ctx.exception))
        self.assertIn("OPEN", str(ctx.exception))
        # Client should not have been called again (circuit blocked it)
        self.assertEqual(mock_get.call_count, 5)

    @patch("trader.scraper.HTTPClient.get")
    @patch("trader.circuit_breaker.time.time")
    def test_circuit_breaker_half_open_recovery(self, mock_time: MagicMock, mock_get: MagicMock) -> None:
        """Test circuit recovers through HALF_OPEN state."""
        start_time = 1000.0
        mock_time.return_value = start_time
        
        # First call: 5 retries fail to open the circuit
        # Then recovery: 5 retries succeed to close the circuit
        mock_get.side_effect = (
            [ConnectionError("fail")] * 5 +  # First fetch: all retries fail
            ["recovery success"]            # Second fetch (recovery): succeeds
        )
        
        scraper = Scraper(circuit_breaker_config={
            'failure_threshold': 1,  # Only 1 failure needed to open
            'recovery_timeout': 30.0,
            'name': 'recovery-test'
        })
        
        # Open the circuit (5 retries all fail)
        with self.assertRaises(ConnectionError):
            scraper.fetch("http://example.com")
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.OPEN)
        
        # Before timeout - still OPEN
        mock_time.return_value = start_time + 29.0
        with self.assertRaises(CircuitBreakerError):
            scraper.fetch("http://example.com")
        
        # After timeout - should try recovery in HALF_OPEN state
        mock_time.return_value = start_time + 30.0
        result = scraper.fetch("http://example.com")
        
        self.assertEqual(result, "recovery success")
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.CLOSED)

    @patch("trader.scraper.HTTPClient.get")
    def test_scrape_method_uses_circuit_breaker(self, mock_get: MagicMock) -> None:
        """Test scrape() method also uses circuit breaker via fetch()."""
        mock_get.return_value = "page content"
        mock_cb = MagicMock()
        mock_cb.call.return_value = "page content"
        mock_cb.state = CircuitState.CLOSED
        
        scraper = Scraper(circuit_breaker=mock_cb)
        result = scraper.scrape("http://example.com")
        
        self.assertEqual(result["url"], "http://example.com")
        self.assertEqual(result["content"], "page content")
        # Circuit breaker should have been called for fetch
        self.assertTrue(mock_cb.call.called)

    def test_circuit_breaker_state_property(self) -> None:
        """Test Scraper exposes circuit breaker state property."""
        scraper = Scraper()
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.CLOSED)

    def test_fetch_with_retry_not_called_directly(self) -> None:
        """Test _fetch_with_retry is internal and should be called through fetch."""
        scraper = Scraper()
        # _fetch_with_retry should exist but be "protected"
        self.assertTrue(hasattr(scraper, '_fetch_with_retry'))
        self.assertTrue(callable(scraper._fetch_with_retry))

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")  # Speed up retry tests
    def test_retry_and_circuit_breaker_work_together(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test that retry decorator and circuit breaker work together."""
        # First 2 calls fail with retryable error, 3rd succeeds
        mock_get.side_effect = [
            urllib.error.HTTPError("http://example.com", 500, "Error", {}, io.BytesIO(b"")),
            urllib.error.HTTPError("http://example.com", 500, "Error", {}, io.BytesIO(b"")),
            "success"
        ]
        
        scraper = Scraper(circuit_breaker_config={'failure_threshold': 5})
        
        result = scraper.fetch("http://example.com")
        
        self.assertEqual(result, "success")
        # Circuit breaker sees 1 successful call (after retries)
        self.assertEqual(scraper.circuit_breaker.failure_count, 0)
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.CLOSED)

    @patch("trader.scraper.HTTPClient.get")
    @patch("time.sleep")
    def test_circuit_failure_count_tracks_after_retries_exhausted(self, mock_sleep: MagicMock, mock_get: MagicMock) -> None:
        """Test circuit breaker tracks failures when all retries are exhausted."""
        # First call: all 5 retry attempts fail
        # Second call: all 5 retry attempts fail
        mock_get.side_effect = (
            [urllib.error.HTTPError("http://example.com", 503, "Error", {}, io.BytesIO(b""))] * 5 +
            [urllib.error.HTTPError("http://example.com", 503, "Error", {}, io.BytesIO(b""))] * 5
        )
        
        scraper = Scraper(circuit_breaker_config={'failure_threshold': 2})
        
        # First call - 5 retries all fail, then circuit breaker counts 1 failure
        with self.assertRaises(urllib.error.HTTPError):
            scraper.fetch("http://example.com")
        
        self.assertEqual(scraper.circuit_breaker.failure_count, 1)
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.CLOSED)
        
        # Second call - another 5 retries fail, circuit reaches threshold
        with self.assertRaises(urllib.error.HTTPError):
            scraper.fetch("http://example.com")
        
        self.assertEqual(scraper.circuit_breaker.failure_count, 2)
        self.assertEqual(scraper.circuit_breaker.state, CircuitState.OPEN)


if __name__ == "__main__":
    unittest.main()
