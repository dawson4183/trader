"""Tests for scraper_retry decorator."""

import time
import urllib.error
from unittest.mock import patch

import pytest

from trader.scraper import scraper_retry, NETWORK_EXCEPTIONS


class TestScraperRetry:
    """Test cases for the scraper_retry decorator."""

    def test_successful_call_no_retry(self):
        """Test that successful calls don't trigger retries."""
        call_count = 0

        @scraper_retry
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retries_on_network_exceptions(self):
        """Test that retry happens on network exceptions."""
        call_count = 0

        @scraper_retry
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise urllib.error.HTTPError(
                    "url", 500, "Server Error", {}, None
                )
            return "success"

        with patch("time.sleep"):
            result = failing_func()

        assert result == "success"
        assert call_count == 3

    def test_max_5_attempts_before_giving_up(self):
        """Test that max 5 attempts are made before giving up."""
        call_count = 0

        @scraper_retry
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                "url", 500, "Server Error", {}, None
            )

        with patch("time.sleep"):
            with pytest.raises(urllib.error.HTTPError):
                always_fails()

        assert call_count == 5

    def test_no_retry_on_non_network_exceptions(self):
        """Test that non-network exceptions are not retried."""
        call_count = 0

        @scraper_retry
        def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a network error")

        with pytest.raises(ValueError):
            raises_value_error()

        assert call_count == 1

    def test_preserves_function_metadata(self):
        """Test that functools.wraps preserves function metadata."""

        @scraper_retry
        def my_function():
            """My docstring."""
            return "result"

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_delay_progression_10_20_40_80_160(self):
        """Test delay progression: 10s, 20s, 40s, 80s, 160s."""
        delays = []
        call_count = 0

        def mock_sleep(duration):
            delays.append(duration)

        @scraper_retry
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                "url", 500, "Server Error", {}, None
            )

        with patch("time.sleep", side_effect=mock_sleep):
            with pytest.raises(urllib.error.HTTPError):
                always_fails()

        # Should have delays: 10, 20, 40, 80, 160 (4 delays between 5 attempts)
        assert delays == [10.0, 20.0, 40.0, 80.0]
        assert call_count == 5

    def test_delay_capped_at_240_seconds(self):
        """Test that delay is capped at 240 seconds maximum."""
        delays = []

        def mock_sleep(duration):
            delays.append(duration)

        @scraper_retry(max_attempts=10)
        def always_fails():
            raise urllib.error.HTTPError(
                "url", 500, "Server Error", {}, None
            )

        with patch("time.sleep", side_effect=mock_sleep):
            with pytest.raises(urllib.error.HTTPError):
                always_fails()

        # All delays should be <= 240
        assert all(d <= 240.0 for d in delays)
        # After reaching 240, should stay at 240
        assert delays[-1] == 240.0

    def test_backoff_multiplier_of_2(self):
        """Test that exponential backoff multiplier is 2.0."""
        delays = []

        def mock_sleep(duration):
            delays.append(duration)

        @scraper_retry
        def always_fails():
            raise urllib.error.HTTPError(
                "url", 500, "Server Error", {}, None
            )

        with patch("time.sleep", side_effect=mock_sleep):
            with pytest.raises(urllib.error.HTTPError):
                always_fails()

        # Each delay should be double the previous (capped at 240)
        for i in range(1, len(delays)):
            assert delays[i] == delays[i - 1] * 2.0

    def test_custom_max_attempts_parameter(self):
        """Test custom max_attempts parameter."""
        call_count = 0

        @scraper_retry(max_attempts=3)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                "url", 500, "Server Error", {}, None
            )

        with patch("time.sleep"):
            with pytest.raises(urllib.error.HTTPError):
                always_fails()

        assert call_count == 3

    def test_retry_urllib_urlerror(self):
        """Test retry on URLError."""
        call_count = 0

        @scraper_retry
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise urllib.error.URLError("Connection failed")
            return "success"

        with patch("time.sleep"):
            result = failing_func()

        assert result == "success"
        assert call_count == 2

    def test_retry_timeout_error(self):
        """Test retry on TimeoutError."""
        call_count = 0

        @scraper_retry
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Connection timed out")
            return "success"

        with patch("time.sleep"):
            result = failing_func()

        assert result == "success"
        assert call_count == 2

    def test_retry_connection_error(self):
        """Test retry on ConnectionError."""
        call_count = 0

        @scraper_retry
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection refused")
            return "success"

        with patch("time.sleep"):
            result = failing_func()

        assert result == "success"
        assert call_count == 2

    def test_default_parameters(self):
        """Test that default parameters are set correctly."""
        # Test via checking the delays match expected progression
        delays = []
        call_count = 0

        def mock_sleep(duration):
            delays.append(duration)

        @scraper_retry
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                "url", 500, "Server Error", {}, None
            )

        with patch("time.sleep", side_effect=mock_sleep):
            with pytest.raises(urllib.error.HTTPError):
                always_fails()

        # Default: initial 10s, max 5 attempts, multiplier 2.0, max_delay 240s
        assert call_count == 5
        assert delays[0] == 10.0  # Initial delay
        assert delays == [10.0, 20.0, 40.0, 80.0]  # 4 delays between 5 attempts

    def test_network_exceptions_tuple_contents(self):
        """Test that NETWORK_EXCEPTIONS contains expected exception types."""
        expected_exceptions = (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            ConnectionRefusedError,
            ConnectionResetError,
            ConnectionAbortedError,
        )
        assert NETWORK_EXCEPTIONS == expected_exceptions

    def test_passes_args_and_kwargs(self):
        """Test that decorator passes args and kwargs correctly."""
        received_args = None
        received_kwargs = None

        @scraper_retry
        def capture_args(*args, **kwargs):
            nonlocal received_args, received_kwargs
            received_args = args
            received_kwargs = kwargs
            return "success"

        result = capture_args(1, 2, key="value")

        assert result == "success"
        assert received_args == (1, 2)
        assert received_kwargs == {"key": "value"}

    def test_bare_decorator_usage(self):
        """Test using decorator without parentheses."""

        @scraper_retry
        def my_func():
            return "success"

        assert my_func() == "success"

    def test_decorator_with_parentheses(self):
        """Test using decorator with parentheses."""

        @scraper_retry()
        def my_func():
            return "success"

        assert my_func() == "success"

    def test_decorator_with_custom_params(self):
        """Test using decorator with custom parameters."""
        call_count = 0

        @scraper_retry(max_attempts=2, initial_delay=5.0)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                "url", 500, "Server Error", {}, None
            )

        delays = []

        def mock_sleep(duration):
            delays.append(duration)

        with patch("time.sleep", side_effect=mock_sleep):
            with pytest.raises(urllib.error.HTTPError):
                always_fails()

        assert call_count == 2
        assert delays == [5.0]  # Only 1 delay between 2 attempts