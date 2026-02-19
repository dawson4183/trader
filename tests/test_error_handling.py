"""Tests for error handling with retry decorator and circuit breaker."""
import time
import pytest
from unittest.mock import Mock, patch
from trader.error_handling import retry, CircuitBreaker, RetryWithCircuitBreaker, CircuitState
from trader.exceptions import ValidationError


class TestRetryDecorator:
    """Test the retry decorator functionality."""

    def test_retry_success_on_first_attempt(self):
        """Should succeed without retry on first attempt."""
        mock_func = Mock(return_value="success")
        
        @retry(max_attempts=3, delay=0.1)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_success_after_failure(self):
        """Should retry and succeed after initial failures."""
        mock_func = Mock(side_effect=[Exception("error"), Exception("error"), "success"])
        
        @retry(max_attempts=3, delay=0.1)
        def test_func():
            return mock_func()
        
        result = test_func()
        
        assert result == "success"
        assert mock_func.call_count == 3

    def test_retry_exhausts_all_attempts(self):
        """Should raise last exception after all attempts exhausted."""
        mock_func = Mock(side_effect=[Exception("error1"), Exception("error2"), Exception("error3")])
        
        @retry(max_attempts=3, delay=0.1)
        def test_func():
            return mock_func()
        
        with pytest.raises(Exception) as exc_info:
            test_func()
        
        assert "error3" in str(exc_info.value)
        assert mock_func.call_count == 3

    def test_retry_respects_max_attempts(self):
        """Should not exceed max_attempts."""
        mock_func = Mock(side_effect=Exception("always fails"))
        
        @retry(max_attempts=5, delay=0.01)
        def test_func():
            return mock_func()
        
        with pytest.raises(Exception):
            test_func()
        
        assert mock_func.call_count == 5

    def test_retry_backoff_increases_delay(self):
        """Backoff should increase delay between retries."""
        call_times = []
        
        def failing_func():
            call_times.append(time.time())
            raise Exception("fail")
        
        @retry(max_attempts=3, delay=0.1, backoff=2.0)
        def test_func():
            return failing_func()
        
        start = time.time()
        with pytest.raises(Exception):
            test_func()
        end = time.time()
        
        # Should take at least delay + delay*backoff = 0.1 + 0.2 = 0.3s
        assert (end - start) >= 0.25
        assert len(call_times) == 3

    def test_retry_only_catches_specified_exceptions(self):
        """Should only retry on specified exception types."""
        mock_func = Mock(side_effect=[ValueError("value error"), "success"])
        
        @retry(max_attempts=3, delay=0.1, exceptions=[ValueError])
        def test_func():
            return mock_func()
        
        result = test_func()
        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_does_not_catch_unspecified_exceptions(self):
        """Should not retry on unspecified exception types."""
        mock_func = Mock(side_effect=[TypeError("type error"), "success"])
        
        @retry(max_attempts=3, delay=0.1, exceptions=[ValueError])
        def test_func():
            return mock_func()
        
        with pytest.raises(TypeError):
            test_func()
        
        assert mock_func.call_count == 1

    def test_retry_preserves_function_metadata(self):
        """Should preserve function name and docstring."""
        @retry(max_attempts=2, delay=0.1)
        def my_function():
            """My docstring."""
            return "result"
        
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."


class TestCircuitBreaker:
    """Test the circuit breaker functionality."""

    def test_circuit_starts_closed(self):
        """Circuit should start in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_success_increments_no_failure(self):
        """Successful calls don't increment failure count."""
        cb = CircuitBreaker()
        
        result = cb.call(lambda: "success")
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_failure_increments_count(self):
        """Failed calls increment failure count."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise ValueError("error")
        
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED

    def test_circuit_opens_after_threshold(self):
        """Circuit opens after failure threshold reached."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise ValueError("error")
        
        # First 2 failures - circuit still closed
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failing_func)
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 2
        
        # 3rd failure - circuit opens
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    def test_circuit_rejects_when_open(self):
        """When open, circuit should reject calls immediately."""
        cb = CircuitBreaker(failure_threshold=1)
        
        def failing_func():
            raise ValueError("error")
        
        # Trigger failure
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Next call should be rejected
        with pytest.raises(ValidationError) as exc_info:
            cb.call(lambda: "should not run")
        
        assert "OPEN" in str(exc_info.value)

    def test_circuit_half_open_after_timeout(self):
        """Circuit should enter HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        def failing_func():
            raise ValueError("error")
        
        # Open the circuit
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Next call - circuit enters HALF_OPEN, tries the call
        # If successful, circuit closes. If fails, reopens.
        # Let's test with a successful call
        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitState.CLOSED  # Success closes it

    def test_circuit_closes_on_success_in_half_open(self):
        """Successful call in HALF_OPEN should close circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        # Open the circuit
        with pytest.raises(ValueError):
            cb.call(lambda: exec('raise ValueError("open")'))
        
        time.sleep(0.15)
        
        # Success should close it
        result = cb.call(lambda: "success")
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_as_decorator(self):
        """Circuit breaker can be used as decorator."""
        cb = CircuitBreaker(failure_threshold=2)
        
        @cb
        def test_func(should_fail=False):
            if should_fail:
                raise ValueError("fail")
            return "success"
        
        # Successful call
        assert test_func(should_fail=False) == "success"
        
        # Failures
        for _ in range(2):
            with pytest.raises(ValueError):
                test_func(should_fail=True)
        
        # Circuit now open
        with pytest.raises(ValidationError):
            test_func(should_fail=False)

    def test_circuit_respects_expected_exception(self):
        """Only expected exception types count toward failures."""
        cb = CircuitBreaker(failure_threshold=1, expected_exception=ValueError)
        
        def raises_type_error():
            raise TypeError("not counted")
        
        def raises_value_error():
            raise ValueError("counted")
        
        # TypeError shouldn't count
        with pytest.raises(TypeError):
            cb.call(raises_type_error)
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        
        # ValueError should count
        with pytest.raises(ValueError):
            cb.call(raises_value_error)
        
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 1


class TestRetryWithCircuitBreaker:
    """Test combined retry and circuit breaker."""

    def test_combined_success(self):
        """Combined decorator should work for successful calls."""
        combined = RetryWithCircuitBreaker(max_attempts=3, delay=0.1)
        
        @combined
        def test_func():
            return "success"
        
        assert test_func() == "success"

    def test_combined_retry_then_circuit(self):
        """Should retry then eventually open circuit."""
        combined = RetryWithCircuitBreaker(
            max_attempts=2,
            delay=0.1,
            failure_threshold=1,  # Open after first retry batch fails
            recovery_timeout=1.0
        )

        call_count = 0

        @combined
        def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fails")

        # First call - retries twice (max_attempts), then circuit counts as 1 failure
        with pytest.raises(ValueError):
            test_func()

        assert call_count == 2  # Retried once

        # Second call - circuit should be open now
        with pytest.raises(ValidationError) as exc_info:
            test_func()

        assert "OPEN" in str(exc_info.value)

    def test_combined_respects_parameters(self):
        """Should respect both retry and circuit parameters."""
        combined = RetryWithCircuitBreaker(
            max_attempts=3,
            delay=0.05,
            failure_threshold=1,
            recovery_timeout=0.1
        )
        
        mock_func = Mock(side_effect=Exception("fail"))
        
        @combined
        def test_func():
            return mock_func()
        
        # First invocation - 3 attempts due to retry
        with pytest.raises(Exception):
            test_func()
        
        assert mock_func.call_count == 3
        
        # Circuit should now be open
        with pytest.raises(ValidationError):
            test_func()
        
        # No additional calls to mock_func
        assert mock_func.call_count == 3


class TestEdgeCases:
    """Test edge cases for error handling."""

    def test_retry_with_zero_delay(self):
        """Retry with zero delay should work."""
        @retry(max_attempts=2, delay=0)
        def test_func():
            return "success"
        
        assert test_func() == "success"

    def test_retry_with_single_attempt(self):
        """Retry with max_attempts=1 should not retry."""
        mock_func = Mock(side_effect=[Exception("fail"), "success"])
        
        @retry(max_attempts=1, delay=0.1)
        def test_func():
            return mock_func()
        
        with pytest.raises(Exception):
            test_func()
        
        assert mock_func.call_count == 1

    def test_circuit_with_very_short_timeout(self):
        """Circuit with very short recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.001)
        
        # Open circuit
        with pytest.raises(ValueError):
            cb.call(lambda: exec('raise ValueError("open")'))
        
        # Very short wait
        time.sleep(0.01)
        
        # Should attempt reset
        try:
            cb.call(lambda: exec('raise ValueError("fail")'))
        except (ValidationError, ValueError):
            pass
        
        # Circuit should have tried to reset (went to half-open)

    def test_circuit_with_high_threshold(self):
        """Circuit with high failure threshold."""
        cb = CircuitBreaker(failure_threshold=100)
        
        for i in range(50):
            with pytest.raises(ValueError):
                cb.call(lambda: exec('raise ValueError("fail")'))
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 50
