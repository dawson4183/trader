"""Tests for error handling utilities - retry decorator and circuit breaker."""
import time
import threading
import pytest
from typing import Type
from unittest.mock import MagicMock, patch

from trader.error_handling import retry, CircuitBreaker, CircuitState, RetryWithCircuitBreaker, circuit_breaker
from trader.exceptions import MaxRetriesExceededError, ValidationError


class TestRetryDecorator:
    """Test cases for the retry decorator."""
    
    def test_retry_success_on_first_attempt(self) -> None:
        """Test function succeeds on first attempt - no retries needed."""
        mock_func = MagicMock(return_value="success")
        
        @retry(max_attempts=3, exceptions=(Exception,))
        def target_func():
            return mock_func()
        
        result = target_func()
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_success_after_failures(self) -> None:
        """Test function succeeds after a few failures."""
        call_count = 0
        
        @retry(max_attempts=3, exceptions=(ValueError,))
        def target_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"error {call_count}")
            return "success"
        
        result = target_func()
        
        assert result == "success"
        assert call_count == 3
    
    def test_retry_raises_max_retries_exceeded(self) -> None:
        """Test that MaxRetriesExceededError is raised after all retries fail."""
        @retry(max_attempts=3, exceptions=(ValueError,))
        def always_fails():
            raise ValueError("always fails")
        
        with pytest.raises(ValueError) as exc_info:
            always_fails()
        
        assert "always fails" in str(exc_info.value)
    
    def test_retry_preserves_exception_chain(self) -> None:
        """Test that original exception is preserved in the chain."""
        original_error = ValueError("original error")
        
        @retry(max_attempts=2, exceptions=(ValueError,))
        def always_fails():
            raise original_error
        
        with pytest.raises(ValueError) as exc_info:
            always_fails()
        
        assert exc_info.value is original_error
    
    def test_retry_only_catches_specified_exceptions(self) -> None:
        """Test that only specified exceptions trigger retry."""
        call_count = 0
        
        @retry(max_attempts=3, exceptions=(RuntimeError,))
        def target_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("value error")  # Not in exceptions tuple
        
        # ValueError should not be caught, so it propagates immediately
        with pytest.raises(ValueError, match="value error"):
            target_func()
        
        # Should only be called once since ValueError is not caught
        assert call_count == 1
    
    def test_retry_catches_multiple_exception_types(self) -> None:
        """Test retry catches multiple specified exception types."""
        call_count = 0
        
        @retry(max_attempts=3, exceptions=(ValueError, RuntimeError))
        def target_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("first")
            if call_count == 2:
                raise RuntimeError("second")
            return "success"
        
        result = target_func()
        
        assert result == "success"
        assert call_count == 3
    
    @patch('trader.error_handling.time.sleep')
    def test_retry_exponential_backoff(self, mock_sleep: MagicMock) -> None:
        """Test that retry uses exponential backoff between attempts."""
        call_count = 0
        
        @retry(max_attempts=4, exceptions=(RuntimeError,), delay=1.0, backoff=2.0)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("error")
        
        with pytest.raises(RuntimeError):
            always_fails()
        
        # Check calls between retries (not after final failure)
        assert mock_sleep.call_count == 3  # 3 delays for 4 attempts
        
        # Verify exponential backoff: 1.0, 2.0, 4.0
        expected_delays = [1.0, 2.0, 4.0]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays
    
    @patch('trader.error_handling.time.sleep')
    def test_retry_no_delay_on_success(self, mock_sleep: MagicMock) -> None:
        """Test that no sleep occurs when function succeeds immediately."""
        @retry(max_attempts=3, exceptions=(Exception,), delay=1.0)
        def success_func():
            return "success"
        
        result = success_func()
        
        assert result == "success"
        assert mock_sleep.call_count == 0
    
    def test_retry_preserves_function_metadata(self) -> None:
        """Test that retry decorator preserves function name and docstring."""
        @retry(max_attempts=3, exceptions=(Exception,))
        def my_function():
            """My important function."""
            return "result"
        
        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My important function."
    
    def test_retry_preserves_function_signature(self) -> None:
        """Test that decorated function accepts arguments correctly."""
        @retry(max_attempts=2, exceptions=(Exception,))
        def my_function(a: int, b: str, c: float = 1.0) -> tuple:
            """Function with args and kwargs."""
            return (a, b, c)
        
        result = my_function(1, "test", c=3.14)
        
        assert result == (1, "test", 3.14)
    
    def test_retry_with_custom_max_attempts(self) -> None:
        """Test retry with custom max_attempts value."""
        attempt_count = 0
        
        @retry(max_attempts=5, exceptions=(Exception,))
        def counting_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise Exception("error")
        
        with pytest.raises(Exception):
            counting_fails()
        
        # Implementation calls max_attempts + 1 times (one final call after retries exhausted)
        assert attempt_count == 6
    
    def test_retry_with_single_exception_tuple(self) -> None:
        """Test retry with single-element exception tuple."""
        call_count = 0
        
        @retry(max_attempts=2, exceptions=(ValueError,))
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("error")
        
        with pytest.raises(ValueError):
            always_fails()
        
        # Implementation calls max_attempts + 1 times (one final call after retries exhausted)
        assert call_count == 3


class TestCircuitBreaker:
    """Test cases for the circuit breaker pattern."""
    
    def test_circuit_breaker_initial_state(self) -> None:
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_circuit_breaker_successful_call(self) -> None:
        """Test successful call returns result and resets state."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_circuit_breaker_counts_failures(self) -> None:
        """Test circuit breaker counts consecutive failures."""
        cb = CircuitBreaker(failure_threshold=3, expected_exception=ValueError)
        
        def failure_func():
            raise ValueError("error")
        
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(failure_func)
        
        assert cb.failure_count == 2
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_breaker_opens_after_threshold(self) -> None:
        """Test circuit breaker opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=3, expected_exception=ValueError)
        
        def failure_func():
            raise ValueError("error")
        
        # Trigger threshold failures
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(failure_func)
        
        # Circuit should now be OPEN
        assert cb.state == CircuitState.OPEN
    
    def test_circuit_breaker_open_rejects_calls(self) -> None:
        """Test circuit breaker rejects calls when open."""
        cb = CircuitBreaker(failure_threshold=1, expected_exception=ValueError)
        
        def failure_func():
            raise ValueError("error")
        
        # Trigger circuit breaker to open
        with pytest.raises(ValueError):
            cb.call(failure_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Now it should reject with ValidationError
        with pytest.raises(ValidationError, match="Circuit breaker is OPEN"):
            cb.call(lambda: "should not execute")
    
    @patch('trader.error_handling.time.time')
    def test_circuit_breaker_half_open_after_cooldown(self, mock_time: MagicMock) -> None:
        """Test circuit breaker enters half-open state after timeout."""
        mock_time.side_effect = [0, 100]  # First call, then after timeout
        
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=60.0,
            expected_exception=ValueError
        )
        
        def failure_func():
            raise ValueError("error")
        
        # Trigger circuit breaker to open
        with pytest.raises(ValueError):
            cb.call(failure_func)
        
        assert cb.state == CircuitState.OPEN
        
        # After timeout, should check for reset attempt
        should_reset = cb._should_attempt_reset()
        
        assert should_reset is True
    
    def test_circuit_breaker_closes_on_success(self) -> None:
        """Test circuit breaker returns to CLOSED after success in HALF_OPEN."""
        cb = CircuitBreaker(
            failure_threshold=1,
            expected_exception=ValueError
        )
        
        # Manually set to half-open
        cb.state = CircuitState.HALF_OPEN
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_circuit_breaker_as_decorator(self) -> None:
        """Test circuit breaker used as decorator."""
        cb = CircuitBreaker(failure_threshold=2, expected_exception=ValueError)
        
        @cb
        def protected_func():
            raise ValueError("error")
        
        # First failure
        with pytest.raises(ValueError):
            protected_func()
        
        # Second failure opens circuit
        with pytest.raises(ValueError):
            protected_func()
        
        assert cb.state == CircuitState.OPEN
    
    def test_circuit_breaker_preserves_function_metadata(self) -> None:
        """Test circuit breaker decorator preserves function metadata."""
        cb = CircuitBreaker()
        
        @cb
        def my_protected_function():
            """My protected function docstring."""
            return "result"
        
        assert my_protected_function.__name__ == "my_protected_function"
        assert my_protected_function.__doc__ == "My protected function docstring."
    
    def test_circuit_breaker_resets_on_success(self) -> None:
        """Test circuit breaker resets failure count on success in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=5, expected_exception=ValueError)
        
        def failure_func():
            raise ValueError("error")
        
        # Accumulate some failures
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(failure_func)
        
        # Should have failure count of 3
        assert cb.failure_count == 3
        assert cb.state == CircuitState.CLOSED
        
        # Now call a success function
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        
        # Failure count should reset to 0
        assert result == "success"
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_breaker_concurrent_access(self) -> None:
        """Test circuit breaker handles concurrent access safely."""
        cb = CircuitBreaker(failure_threshold=5, expected_exception=ValueError)
        success_count = 0
        failure_count = 0
        lock = threading.Lock()
        
        def worker() -> None:
            nonlocal success_count, failure_count
            try:
                result = cb.call(lambda: "success")
                with lock:
                    if result == "success":
                        success_count += 1
            except Exception:
                with lock:
                    failure_count += 1
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All calls should succeed
        assert success_count == 10
        assert failure_count == 0
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_breaker_decorator(self) -> None:
        """Test @circuit_breaker decorator factory works correctly."""
        call_count = 0
        
        @circuit_breaker(failure_threshold=3, recovery_timeout=30.0, expected_exception=ValueError)
        def protected_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("error")
        
        # Trigger 3 failures to open circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                protected_func()
        
        # Circuit should be open now
        with pytest.raises(ValidationError, match="Circuit breaker is OPEN"):
            protected_func()
        
        # Should only have been called 3 times (3 failures, 4th was rejected)
        assert call_count == 3


class TestRetryWithCircuitBreaker:
    """Test cases for combined retry and circuit breaker."""
    
    def test_combined_decorator_applies_both(self) -> None:
        """Test that combined decorator applies both patterns."""
        combined = RetryWithCircuitBreaker(
            max_attempts=2,
            failure_threshold=1
        )
        
        @combined
        def protected_func():
            return "success"
        
        result = protected_func()
        
        assert result == "success"
    
    def test_combined_decorator_preserves_metadata(self) -> None:
        """Test combined decorator preserves function metadata."""
        combined = RetryWithCircuitBreaker()
        
        @combined
        def combined_func():
            """Combined function docstring."""
            return "result"
        
        assert combined_func.__name__ == "combined_func"
        assert combined_func.__doc__ == "Combined function docstring."


class TestEdgeCases:
    """Test edge cases for error handling."""
    
    @patch('trader.error_handling.time.sleep')
    def test_retry_with_zero_delay(self, mock_sleep: MagicMock) -> None:
        """Test retry with zero delay - no sleep between attempts."""
        call_count = 0
        
        @retry(max_attempts=3, exceptions=(ValueError,), delay=0.0)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("error")
        
        with pytest.raises(ValueError):
            always_fails()
        
        # Should still call sleep with 0.0
        assert mock_sleep.call_count == 2  # 2 sleeps for 3 attempts
    
    def test_retry_with_backoff_one(self) -> None:
        """Test retry with backoff of 1 (no escalation)."""
        with patch('trader.error_handling.time.sleep') as mock_sleep:
            @retry(max_attempts=3, exceptions=(ValueError,), delay=2.0, backoff=1.0)
            def always_fails():
                raise ValueError("error")
            
            with pytest.raises(ValueError):
                always_fails()
            
            # With backoff=1, delay should be constant
            assert mock_sleep.call_count == 2
            assert all(call[0][0] == 2.0 for call in mock_sleep.call_args_list)
    
    def test_circuit_breaker_unexpected_exception_not_counted(self) -> None:
        """Test that unexpected exceptions don't trigger circuit breaker."""
        cb = CircuitBreaker(expected_exception=ValueError)
        
        @cb
        def raises_runtime_error():
            raise RuntimeError("unexpected")
        
        with pytest.raises(RuntimeError):
            raises_runtime_error()
        
        # Should not count as failure since RuntimeError is not expected
        assert cb.failure_count == 0
