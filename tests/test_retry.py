"""Tests for the retry decorator with exponential backoff."""

import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import http.client
import time

from trader.retry import (
    retry_with_backoff,
    _is_retryable_exception,
    _get_backoff_delay,
    RetryableHTTPError,
    NonRetryableHTTPError,
)


class TestBackoffDelay(unittest.TestCase):
    """Test cases for exponential backoff delay calculation."""

    def test_backoff_delays_sequence(self) -> None:
        """Test backoff delays double each attempt (1s, 2s, 4s, 8s, 16s)."""
        self.assertEqual(_get_backoff_delay(0, base_delay=1.0), 1.0)
        self.assertEqual(_get_backoff_delay(1, base_delay=1.0), 2.0)
        self.assertEqual(_get_backoff_delay(2, base_delay=1.0), 4.0)
        self.assertEqual(_get_backoff_delay(3, base_delay=1.0), 8.0)
        self.assertEqual(_get_backoff_delay(4, base_delay=1.0), 16.0)

    def test_backoff_with_custom_base(self) -> None:
        """Test backoff with custom base delay."""
        self.assertEqual(_get_backoff_delay(0, base_delay=0.5), 0.5)
        self.assertEqual(_get_backoff_delay(1, base_delay=0.5), 1.0)
        self.assertEqual(_get_backoff_delay(2, base_delay=0.5), 2.0)


class TestIsRetryableException(unittest.TestCase):
    """Test cases for determining if exceptions are retryable."""

    def test_connection_error_is_retryable(self) -> None:
        """ConnectionError should be retryable."""
        self.assertTrue(_is_retryable_exception(ConnectionError()))
        self.assertTrue(_is_retryable_exception(ConnectionRefusedError()))
        self.assertTrue(_is_retryable_exception(ConnectionResetError()))

    def test_timeout_error_is_retryable(self) -> None:
        """TimeoutError should be retryable."""
        self.assertTrue(_is_retryable_exception(TimeoutError()))

    def test_http_500_is_retryable(self) -> None:
        """HTTP 500 should be retryable."""
        error = urllib.error.HTTPError(
            url="http://example.com",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None
        )
        self.assertTrue(_is_retryable_exception(error))

    def test_http_502_is_retryable(self) -> None:
        """HTTP 502 should be retryable."""
        error = urllib.error.HTTPError(
            url="http://example.com",
            code=502,
            msg="Bad Gateway",
            hdrs={},
            fp=None
        )
        self.assertTrue(_is_retryable_exception(error))

    def test_http_503_is_retryable(self) -> None:
        """HTTP 503 should be retryable."""
        error = urllib.error.HTTPError(
            url="http://example.com",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None
        )
        self.assertTrue(_is_retryable_exception(error))

    def test_http_429_is_retryable(self) -> None:
        """HTTP 429 (Too Many Requests) should be retryable."""
        error = urllib.error.HTTPError(
            url="http://example.com",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None
        )
        self.assertTrue(_is_retryable_exception(error))

    def test_http_400_is_not_retryable(self) -> None:
        """HTTP 400 should not be retryable."""
        error = urllib.error.HTTPError(
            url="http://example.com",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=None
        )
        self.assertFalse(_is_retryable_exception(error))

    def test_http_404_is_not_retryable(self) -> None:
        """HTTP 404 should not be retryable."""
        error = urllib.error.HTTPError(
            url="http://example.com",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        self.assertFalse(_is_retryable_exception(error))

    def test_http_403_is_not_retryable(self) -> None:
        """HTTP 403 should not be retryable."""
        error = urllib.error.HTTPError(
            url="http://example.com",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None
        )
        self.assertFalse(_is_retryable_exception(error))

    def test_url_error_is_retryable(self) -> None:
        """URLError should be retryable."""
        error = urllib.error.URLError("Connection failed")
        self.assertTrue(_is_retryable_exception(error))

    def test_http_exception_is_retryable(self) -> None:
        """HTTPException should be retryable."""
        error = http.client.HTTPException("Bad response")
        self.assertTrue(_is_retryable_exception(error))

    def test_value_error_not_retryable(self) -> None:
        """Generic ValueError should not be retryable."""
        self.assertFalse(_is_retryable_exception(ValueError("Some error")))

    def test_custom_retryable_error(self) -> None:
        """RetryableHTTPError should be retryable."""
        error = RetryableHTTPError("Retry me", 503)
        self.assertTrue(_is_retryable_exception(error))

    def test_custom_non_retryable_error(self) -> None:
        """NonRetryableHTTPError should not be retryable."""
        error = NonRetryableHTTPError("Don't retry", 400)
        self.assertFalse(_is_retryable_exception(error))


class TestRetryDecorator(unittest.TestCase):
    """Test cases for the @retry_with_backoff decorator."""

    def test_success_no_retry(self) -> None:
        """Successful function should not trigger retries."""
        call_count = 0

        @retry_with_backoff(max_attempts=5)
        def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)  # Should only be called once

    @patch("time.sleep")
    def test_retry_on_connection_error(self, mock_sleep: MagicMock) -> None:
        """Should retry on ConnectionError up to max attempts."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.1)
        def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"

        result = flaky_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)
        # Should sleep twice (after attempt 1 and 2)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep")
    def test_retry_exhausted_raises_last_exception(self, mock_sleep: MagicMock) -> None:
        """Should raise final exception after all retries exhausted."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.1)
        def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError(f"Attempt {call_count}")

        with self.assertRaises(ConnectionError) as ctx:
            always_fails()

        self.assertEqual(str(ctx.exception), "Attempt 3")
        self.assertEqual(call_count, 3)

    def test_non_retryable_exception_raises_immediately(self) -> None:
        """Should raise immediately on non-retryable HTTP error (4xx)."""
        call_count = 0

        @retry_with_backoff(max_attempts=5)
        def client_error() -> None:
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                url="http://example.com",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=None
            )

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            client_error()

        self.assertEqual(ctx.exception.code, 404)
        self.assertEqual(call_count, 1)  # Should only be called once

    @patch("time.sleep")
    def test_retry_on_429_rate_limit(self, mock_sleep: MagicMock) -> None:
        """Should retry on HTTP 429 (Too Many Requests)."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.1)
        def rate_limited() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise urllib.error.HTTPError(
                    url="http://example.com",
                    code=429,
                    msg="Too Many Requests",
                    hdrs={},
                    fp=None
                )
            return "success"

        result = rate_limited()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch("time.sleep")
    def test_retry_on_500_server_error(self, mock_sleep: MagicMock) -> None:
        """Should retry on HTTP 500 server error."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.1)
        def server_error() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise urllib.error.HTTPError(
                    url="http://example.com",
                    code=500,
                    msg="Internal Server Error",
                    hdrs={},
                    fp=None
                )
            return "success"

        result = server_error()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)

    @patch("time.sleep")
    def test_retry_on_503_service_unavailable(self, mock_sleep: MagicMock) -> None:
        """Should retry on HTTP 503 service unavailable."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.1)
        def service_unavailable() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise urllib.error.HTTPError(
                    url="http://example.com",
                    code=503,
                    msg="Service Unavailable",
                    hdrs={},
                    fp=None
                )
            return "success"

        result = service_unavailable()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)

    @patch("time.sleep")
    def test_default_max_attempts_is_5(self, mock_sleep: MagicMock) -> None:
        """Should default to 5 max attempts."""
        call_count = 0

        @retry_with_backoff()  # No max_attempts specified
        def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Failed")

        with self.assertRaises(ConnectionError):
            always_fails()

        self.assertEqual(call_count, 5)
        # Should sleep 4 times (after attempts 1, 2, 3, 4)
        self.assertEqual(mock_sleep.call_count, 4)

    @patch("time.sleep")
    def test_custom_max_attempts(self, mock_sleep: MagicMock) -> None:
        """Should respect custom max_attempts parameter."""
        call_count = 0

        @retry_with_backoff(max_attempts=3)
        def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Failed")

        with self.assertRaises(ConnectionError):
            always_fails()

        self.assertEqual(call_count, 3)

    @patch("time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep: MagicMock) -> None:
        """Should use exponential backoff: 1s, 2s, 4s, 8s, 16s."""
        @retry_with_backoff(max_attempts=5, base_delay=1.0)
        def always_fails() -> None:
            raise ConnectionError("Failed")

        with self.assertRaises(ConnectionError):
            always_fails()

        expected_delays = [1.0, 2.0, 4.0, 8.0]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(actual_delays, expected_delays)

    @patch("time.sleep")
    def test_on_retry_callback(self, mock_sleep: MagicMock) -> None:
        """Should call on_retry callback with exception, attempt, and delay."""
        callback_calls = []

        def on_retry(exc: Exception, attempt: int, delay: float) -> None:
            callback_calls.append((type(exc).__name__, attempt, delay))

        @retry_with_backoff(max_attempts=3, base_delay=0.5, on_retry=on_retry)
        def flaky_func() -> str:
            if len(callback_calls) < 2:
                raise ConnectionError("Failed")
            return "success"

        result = flaky_func()
        self.assertEqual(result, "success")
        self.assertEqual(len(callback_calls), 2)
        self.assertEqual(callback_calls[0], ("ConnectionError", 1, 0.5))
        self.assertEqual(callback_calls[1], ("ConnectionError", 2, 1.0))

    @patch("time.sleep")
    def test_preserves_function_metadata(self, mock_sleep: MagicMock) -> None:
        """Decorator should preserve function name and docstring."""
        @retry_with_backoff(max_attempts=3)
        def my_function() -> str:
            """My docstring."""
            return "result"

        self.assertEqual(my_function.__name__, "my_function")
        self.assertEqual(my_function.__doc__, "My docstring.")

    @patch("time.sleep")
    def test_function_with_arguments(self, mock_sleep: MagicMock) -> None:
        """Decorator should work with functions that have arguments."""
        call_args = []

        @retry_with_backoff(max_attempts=2, base_delay=0.1)
        def func_with_args(a: int, b: str, c: float = 1.0) -> str:
            call_args.append((a, b, c))
            if len(call_args) == 1:
                raise ConnectionError("Failed")
            return f"{a}-{b}-{c}"

        result = func_with_args(1, "test", c=2.0)
        self.assertEqual(result, "1-test-2.0")
        self.assertEqual(call_args, [(1, "test", 2.0), (1, "test", 2.0)])


if __name__ == "__main__":
    unittest.main()