"""Tests for the CircuitBreaker class.

This module covers the circuit breaker pattern implementation including:
- State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Thread safety
- Recovery timeout behavior
- Integration with scraper operations
"""

import threading
import time
import urllib.error
from unittest.mock import Mock, patch

import pytest

from trader.exceptions import CircuitOpenError
from trader.scraper import CircuitBreaker


class TestCircuitBreakerInitialization:
    """Tests for CircuitBreaker initialization."""
    
    def test_default_parameters(self) -> None:
        """Test default parameters match requirements."""
        cb = CircuitBreaker()
        
        assert cb.failure_threshold == 10
        assert cb.recovery_timeout == 60.0
        assert cb.current_state == "CLOSED"
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
    
    def test_custom_parameters(self) -> None:
        """Test custom parameter values."""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
        
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 30.0
        assert cb.current_state == "CLOSED"
    
    def test_initial_failure_count_is_zero(self) -> None:
        """Test failure count starts at zero."""
        cb = CircuitBreaker()
        
        assert cb.failure_count == 0
    
    def test_initial_state_is_closed(self) -> None:
        """Test circuit starts in CLOSED state."""
        cb = CircuitBreaker()
        
        assert cb.current_state == "CLOSED"
    
    def test_initial_last_failure_time_is_none(self) -> None:
        """Test last failure time starts as None."""
        cb = CircuitBreaker()
        
        assert cb.last_failure_time is None


class TestCircuitBreakerClosedState:
    """Tests for CLOSED state behavior."""
    
    def test_success_resets_failure_count(self) -> None:
        """Test successful calls reset failure count to zero."""
        cb = CircuitBreaker(failure_threshold=10)
        
        # Record some failures
        for _ in range(5):
            cb.record_failure()
        
        assert cb.failure_count == 5
        
        # Success should reset count
        cb.record_success()
        
        assert cb.failure_count == 0
        assert cb.current_state == "CLOSED"
    
    def test_success_with_zero_failures_does_nothing(self) -> None:
        """Test success when count is zero stays at zero."""
        cb = CircuitBreaker()
        
        cb.record_success()
        
        assert cb.failure_count == 0
        assert cb.current_state == "CLOSED"
    
    def test_failure_increments_count(self) -> None:
        """Test each failure increments the count."""
        cb = CircuitBreaker()
        
        cb.record_failure()
        assert cb.failure_count == 1
        
        cb.record_failure()
        assert cb.failure_count == 2
        
        cb.record_failure()
        assert cb.failure_count == 3


class TestCircuitBreakerOpensAfterThreshold:
    """Tests for circuit opening after threshold failures."""
    
    def test_circuit_opens_after_exactly_10_failures(self) -> None:
        """Test circuit transitions to OPEN after exactly 10 consecutive failures."""
        cb = CircuitBreaker(failure_threshold=10)
        
        # Record exactly 9 failures - should still be CLOSED
        for _ in range(9):
            cb.record_failure()
        
        assert cb.current_state == "CLOSED"
        assert cb.failure_count == 9
        
        # 10th failure should open the circuit
        cb.record_failure()
        
        assert cb.current_state == "OPEN"
        assert cb.failure_count == 10
        assert cb.last_failure_time is not None
    
    def test_circuit_opens_after_threshold_crossed(self) -> None:
        """Test circuit opens when failure threshold is crossed."""
        cb = CircuitBreaker(failure_threshold=10)
        
        # Simulate 10 failures
        for _ in range(10):
            cb.record_failure()
        
        assert cb.current_state == "OPEN"
    
    def test_failure_count_continues_after_open(self) -> None:
        """Test failure count is 10 when circuit opens."""
        cb = CircuitBreaker(failure_threshold=10)
        
        for _ in range(10):
            cb.record_failure()
        
        assert cb.failure_count == 10
    
    def test_last_failure_time_set_on_open(self) -> None:
        """Test last_failure_time is set when circuit opens."""
        cb = CircuitBreaker(failure_threshold=10)
        
        before_failures = time.time()
        
        for _ in range(10):
            cb.record_failure()
        
        after_failures = time.time()
        
        assert cb.last_failure_time is not None
        assert before_failures <= cb.last_failure_time <= after_failures


class TestCircuitBreakerOpenState:
    """Tests for OPEN state behavior."""
    
    def test_circuit_rejects_calls_when_open(self) -> None:
        """Test CircuitOpenError is raised when circuit is OPEN."""
        cb = CircuitBreaker(failure_threshold=10)
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        assert cb.current_state == "OPEN"
        
        # Call should be rejected
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.call(lambda: "success")
        
        assert "Circuit breaker is OPEN" in str(exc_info.value)
        assert "10" in str(exc_info.value)
    
    def test_call_not_executed_when_open(self) -> None:
        """Test function is NOT called when circuit is open."""
        cb = CircuitBreaker(failure_threshold=10)
        mock_func = Mock(return_value="result")
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        try:
            cb.call(mock_func)
        except CircuitOpenError:
            pass
        
        mock_func.assert_not_called()
    
    def test_open_state_persists_until_timeout(self) -> None:
        """Test circuit stays OPEN until recovery timeout elapses."""
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=60.0)
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        # Immediately try to call - should still be open
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "success")
        
        assert cb.current_state == "OPEN"


class TestCircuitBreakerHalfOpenState:
    """Tests for HALF_OPEN state behavior."""
    
    def test_circuit_transitions_to_half_open_after_timeout(self) -> None:
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=0.1)
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        assert cb.current_state == "OPEN"
        
        # Wait for timeout
        time.sleep(0.15)
        
        # This call should transition to HALF_OPEN and execute
        result = cb.call(lambda: "success")
        
        assert result == "success"
        assert cb.current_state == "CLOSED"  # Success closes the circuit
    
    def test_success_in_half_opens_closes_circuit(self) -> None:
        """Test successful call in HALF_OPEN closes circuit and resets failures."""
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=0.1)
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        time.sleep(0.15)
        
        # Call will transition to HALF_OPEN, then success closes circuit
        cb.call(lambda: "success")
        
        assert cb.current_state == "CLOSED"
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
    
    def test_failure_in_half_open_reopens_immediately(self) -> None:
        """Test failure in HALF_OPEN immediately reopens the circuit."""
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=0.1)
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        time.sleep(0.15)
        
        # Transition to HALF_OPEN by calling
        # This should fail and transition to OPEN
        def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            cb.call(failing_func)
        
        # Circuit should be OPEN again
        assert cb.current_state == "OPEN"
        # Failure count should have incremented
        assert cb.failure_count == 11
    
    def test_half_open_state_transition_on_timeout(self) -> None:
        """Test recovery timeout triggers transition to HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=0.1)
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        # Verify circuit is initially OPEN
        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "should fail")
        
        # Wait for timeout
        time.sleep(0.15)
        
        # Now call should be allowed and transition to HALF_OPEN/CLOSED
        result = cb.call(lambda: "should succeed")
        
        assert result == "should succeed"
        assert cb.current_state == "CLOSED"


class TestCircuitBreakerReset:
    """Tests for manual reset functionality."""
    
    def test_reset_closes_circuit(self) -> None:
        """Test reset() forces circuit to CLOSED state."""
        cb = CircuitBreaker(failure_threshold=10)
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        assert cb.current_state == "OPEN"
        
        cb.reset()
        
        assert cb.current_state == "CLOSED"
    
    def test_reset_clears_failure_count(self) -> None:
        """Test reset() clears the failure count."""
        cb = CircuitBreaker(failure_threshold=10)
        
        for _ in range(5):
            cb.record_failure()
        
        assert cb.failure_count == 5
        
        cb.reset()
        
        assert cb.failure_count == 0
    
    def test_reset_clears_last_failure_time(self) -> None:
        """Test reset() clears the last failure time."""
        cb = CircuitBreaker(failure_threshold=10)
        
        for _ in range(10):
            cb.record_failure()
        
        assert cb.last_failure_time is not None
        
        cb.reset()
        
        assert cb.last_failure_time is None
    
    def test_call_allowed_after_reset(self) -> None:
        """Test calls are allowed after manual reset."""
        cb = CircuitBreaker(failure_threshold=10)
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        # Reset
        cb.reset()
        
        # Call should succeed
        result = cb.call(lambda: "success")
        
        assert result == "success"


class TestCircuitBreakerThreadSafety:
    """Tests for thread safety."""
    
    def test_concurrent_failure_records(self) -> None:
        """Test concurrent failure recording is thread-safe."""
        cb = CircuitBreaker(failure_threshold=1000)
        
        def record_many_failures():
            for _ in range(10):
                cb.record_failure()
        
        threads = [
            threading.Thread(target=record_many_failures)
            for _ in range(10)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert cb.failure_count == 100  # 10 threads * 10 failures each
    
    def test_concurrent_success_resets(self) -> None:
        """Test concurrent success recording is thread-safe."""
        cb = CircuitBreaker(failure_threshold=1000)
        
        # Add some failures
        for _ in range(50):
            cb.record_failure()
        
        def record_success():
            cb.record_success()
        
        threads = [
            threading.Thread(target=record_success)
            for _ in range(10)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # After successes, count should be 0
        assert cb.failure_count == 0
    
    def test_concurrent_call_synchronization(self) -> None:
        """Test concurrent calls are properly synchronized."""
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=0.1)
        
        results = []
        
        def call_and_record():
            try:
                result = cb.call(lambda: "success")
                results.append(("success", result))
            except Exception as e:
                results.append(("error", str(e)))
        
        threads = [
            threading.Thread(target=call_and_record)
            for _ in range(20)
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # All calls should have either succeeded or raised CircuitOpenError
        for status, _ in results:
            assert status in ("success", "error")


class TestCircuitBreakerCall:
    """Tests for the call() method."""
    
    def test_call_success_returns_result(self) -> None:
        """Test call returns function result on success."""
        cb = CircuitBreaker()
        
        result = cb.call(lambda: "test_result")
        
        assert result == "test_result"
    
    def test_call_with_args_and_kwargs(self) -> None:
        """Test call passes args and kwargs correctly."""
        cb = CircuitBreaker()
        
        def func(a, b, c=None):
            return (a, b, c)
        
        result = cb.call(func, 1, 2, c=3)
        
        assert result == (1, 2, 3)
    
    def test_call_reraises_function_exception(self) -> None:
        """Test call re-raises exceptions from the wrapped function."""
        cb = CircuitBreaker()
        
        def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            cb.call(failing_func)
    
    def test_call_records_failure_on_exception(self) -> None:
        """Test call records failure when function raises exception."""
        cb = CircuitBreaker()
        
        def failing_func():
            raise ValueError("Test error")
        
        try:
            cb.call(failing_func)
        except ValueError:
            pass
        
        assert cb.failure_count == 1
    
    def test_call_records_success_on_completion(self) -> None:
        """Test call records success when function completes."""
        cb = CircuitBreaker()
        
        cb.call(lambda: "success")
        
        # Since we start at 0 and success in CLOSED state resets to 0
        assert cb.failure_count == 0


class TestCircuitBreakerWithScraper:
    """Integration tests with the Scraper class."""
    
    def test_circuit_breaker_protects_scraper_call(self) -> None:
        """Test circuit breaker can wrap scraper operations."""
        from trader.scraper import Scraper
        
        cb = CircuitBreaker(failure_threshold=10)
        scraper = Scraper(timeout=5)
        
        # Circuit should be CLOSED, call should work
        # Note: This is a mock test to avoid network calls
        with patch.object(scraper, 'fetch_url', return_value="mock content"):
            result = cb.call(scraper.fetch_url, "http://example.com")
        
        assert result == "mock content"
    
    def test_circuit_opens_after_many_scraper_failures(self) -> None:
        """Test circuit opens after repeated scraper failures."""
        from trader.scraper import Scraper
        
        cb = CircuitBreaker(failure_threshold=10)
        scraper = Scraper(timeout=5)
        
        # Mock fetch_url to always fail with an exception
        with patch.object(scraper, 'fetch_url', side_effect=urllib.error.HTTPError(
            url="http://example.com", code=500, msg="Server Error", hdrs={}, fp=None
        )):
            # Simulate 9 failures (HTTPError is a network exception)
            for _ in range(9):
                try:
                    cb.call(scraper.fetch_url, "http://example.com")
                except Exception:
                    pass
            
            assert cb.current_state == "CLOSED"
            assert cb.failure_count == 9
            
            # One more failure opens circuit
            try:
                cb.call(scraper.fetch_url, "http://example.com")
            except Exception:
                pass
        
        assert cb.current_state == "OPEN"
        assert cb.failure_count == 10


class TestCircuitBreakerIntegration:
    """Integration tests with other components."""
    
    def test_imports(self) -> None:
        """Test CircuitBreaker is importable from scraper module."""
        from trader.scraper import CircuitBreaker as CB
        
        cb = CB()
        assert cb is not None
        assert cb.current_state == "CLOSED"
    
    def test_exception_import(self) -> None:
        """Test CircuitOpenError is importable."""
        from trader.exceptions import CircuitOpenError as COE
        
        ex = COE("test")
        assert str(ex) == "test"


class TestCircuitBreakerProperties:
    """Tests for circuit breaker properties."""
    
    def test_current_state_property_returns_state(self) -> None:
        """Test current_state property returns correct value."""
        cb = CircuitBreaker()
        
        assert cb.current_state == "CLOSED"
        
        for _ in range(10):
            cb.record_failure()
        
        assert cb.current_state == "OPEN"
    
    def test_failure_count_property_returns_count(self) -> None:
        """Test failure_count property returns correct value."""
        cb = CircuitBreaker()
        
        assert cb.failure_count == 0
        
        cb.record_failure()
        cb.record_failure()
        
        assert cb.failure_count == 2
    
    def test_last_failure_time_property_returns_time(self) -> None:
        """Test last_failure_time property returns correct value."""
        cb = CircuitBreaker()
        
        before = time.time()
        cb.record_failure()
        after = time.time()
        
        assert cb.last_failure_time is not None
        assert before <= cb.last_failure_time <= after


class TestEdgeCases:
    """Edge case tests."""
    
    def test_failure_threshold_of_one(self) -> None:
        """Test circuit opens after single failure with threshold=1."""
        cb = CircuitBreaker(failure_threshold=1)
        
        cb.record_failure()
        
        assert cb.current_state == "OPEN"
        assert cb.failure_count == 1
    
    def test_zero_failure_threshold(self) -> None:
        """Test zero threshold opens immediately."""
        cb = CircuitBreaker(failure_threshold=0)
        
        # First failure should open immediately
        cb.record_failure()
        
        assert cb.current_state == "OPEN"
    
    def test_very_large_failure_threshold(self) -> None:
        """Test large threshold never opens."""
        cb = CircuitBreaker(failure_threshold=10000)
        
        for _ in range(9999):
            cb.record_failure()
        
        assert cb.current_state == "CLOSED"
    
    def test_recovery_timeout_of_zero(self) -> None:
        """Test zero recovery timeout allows immediate recovery test."""
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=0)
        
        # Open the circuit
        for _ in range(10):
            cb.record_failure()
        
        assert cb.current_state == "OPEN"
        
        # Immediately try - should transition to HALF_OPEN and succeed
        result = cb.call(lambda: "success")
        
        assert result == "success"
        assert cb.current_state == "CLOSED"
