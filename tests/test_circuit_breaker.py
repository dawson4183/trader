"""Tests for the circuit breaker implementation."""

import unittest
from unittest.mock import patch, MagicMock
import time

from trader.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
)


class TestCircuitBreakerInitialization(unittest.TestCase):
    """Test cases for circuit breaker initialization."""

    def test_default_values(self) -> None:
        """Circuit breaker should have sensible defaults."""
        cb = CircuitBreaker()
        self.assertEqual(cb.failure_threshold, 5)
        self.assertEqual(cb.recovery_timeout, 30.0)
        self.assertEqual(cb.name, "default")
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failure_count, 0)

    def test_custom_values(self) -> None:
        """Circuit breaker should accept custom configuration."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0, name="test")
        self.assertEqual(cb.failure_threshold, 3)
        self.assertEqual(cb.recovery_timeout, 10.0)
        self.assertEqual(cb.name, "test")

    def test_initial_state_is_closed(self) -> None:
        """Circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)


class TestCircuitBreakerStates(unittest.TestCase):
    """Test cases for circuit breaker state transitions."""

    def test_closed_to_open_on_threshold(self) -> None:
        """Circuit should OPEN after failure_threshold failures."""
        cb = CircuitBreaker(failure_threshold=3)
        
        # First 2 failures - still CLOSED
        for _ in range(2):
            with self.assertRaises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failure_count, 2)
        
        # 3rd failure - circuit OPENS
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertEqual(cb.failure_count, 3)

    def test_open_fails_fast(self) -> None:
        """OPEN circuit should immediately raise CircuitBreakerError."""
        cb = CircuitBreaker(failure_threshold=1)
        
        # Trigger circuit open
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        self.assertEqual(cb.state, CircuitState.OPEN)
        
        # Next call should fail fast with CircuitBreakerError
        with self.assertRaises(CircuitBreakerError) as ctx:
            cb.call(lambda: "success")
        
        self.assertIn("OPEN", str(ctx.exception))
        self.assertEqual(ctx.exception.state, CircuitState.OPEN)

    @patch("time.time")
    def test_open_to_half_open_after_timeout(self, mock_time: MagicMock) -> None:
        """Circuit should transition to HALF_OPEN after recovery_timeout."""
        mock_time.return_value = 1000.0
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0)
        
        # Open the circuit
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        self.assertEqual(cb.state, CircuitState.OPEN)
        
        # Before timeout - still OPEN
        mock_time.return_value = 1029.0  # 29 seconds later
        with self.assertRaises(CircuitBreakerError):
            cb.call(lambda: "success")
        self.assertEqual(cb.state, CircuitState.OPEN)
        
        # After timeout - transitions to HALF_OPEN and allows call
        mock_time.return_value = 1030.0  # 30 seconds later
        result = cb.call(lambda: "success")
        self.assertEqual(result, "success")
        self.assertEqual(cb.state, CircuitState.CLOSED)  # Success closes it

    @patch("time.time")
    def test_half_open_success_closes_circuit(self, mock_time: MagicMock) -> None:
        """Success in HALF_OPEN should CLOSE the circuit."""
        mock_time.return_value = 1000.0
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0)
        
        # Open the circuit
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        
        # Move to HALF_OPEN after timeout
        mock_time.return_value = 1030.0
        result = cb.call(lambda: "success")
        
        self.assertEqual(result, "success")
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failure_count, 0)

    @patch("time.time")
    def test_half_open_failure_reopens_circuit(self, mock_time: MagicMock) -> None:
        """Failure in HALF_OPEN should re-OPEN the circuit."""
        mock_time.return_value = 1000.0
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0)
        
        # Open the circuit
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        
        # Move to HALF_OPEN after timeout, then fail
        mock_time.return_value = 1030.0
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail again")))
        
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_success_resets_failure_count(self) -> None:
        """Success in CLOSED state should reset failure count."""
        cb = CircuitBreaker(failure_threshold=5)
        
        # 2 failures
        for _ in range(2):
            with self.assertRaises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        self.assertEqual(cb.failure_count, 2)
        
        # Success resets count
        cb.call(lambda: "success")
        self.assertEqual(cb.failure_count, 0)
        self.assertEqual(cb.state, CircuitState.CLOSED)


class TestCircuitBreakerCall(unittest.TestCase):
    """Test cases for the call method."""

    def test_successful_call(self) -> None:
        """Successful call should return result."""
        cb = CircuitBreaker()
        result = cb.call(lambda: "hello")
        self.assertEqual(result, "hello")

    def test_call_passes_args(self) -> None:
        """Call should pass args and kwargs to wrapped function."""
        cb = CircuitBreaker()
        
        def func(a: int, b: str, c: float = 1.0) -> str:
            return f"{a}-{b}-{c}"
        
        result = cb.call(func, 1, "test", c=2.0)
        self.assertEqual(result, "1-test-2.0")

    def test_call_raises_original_exception(self) -> None:
        """Call should raise original exception on failure."""
        cb = CircuitBreaker()
        
        with self.assertRaises(ValueError) as ctx:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("custom error")))
        
        self.assertEqual(str(ctx.exception), "custom error")


class TestCircuitBreakerAsDecorator(unittest.TestCase):
    """Test cases for using circuit breaker as a decorator."""

    def test_decorator_success(self) -> None:
        """Decorator should work for successful calls."""
        cb = CircuitBreaker()
        
        @cb
        def my_func() -> str:
            return "decorated"
        
        result = my_func()
        self.assertEqual(result, "decorated")

    def test_decorator_failure(self) -> None:
        """Decorator should track failures."""
        cb = CircuitBreaker(failure_threshold=2)
        
        @cb
        def failing_func() -> None:
            raise ConnectionError("fail")
        
        with self.assertRaises(ConnectionError):
            failing_func()
        self.assertEqual(cb.failure_count, 1)
        
        with self.assertRaises(ConnectionError):
            failing_func()
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_decorator_with_args(self) -> None:
        """Decorator should preserve function arguments."""
        cb = CircuitBreaker()
        
        @cb
        def func_with_args(x: int, y: str) -> str:
            return f"{x}-{y}"
        
        result = func_with_args(42, "hello")
        self.assertEqual(result, "42-hello")


class TestCircuitBreakerIntegration(unittest.TestCase):
    """Integration tests for circuit breaker behavior."""

    @patch("time.time")
    def test_full_lifecycle(self, mock_time: MagicMock) -> None:
        """Test complete circuit breaker lifecycle."""
        start_time = 1000.0
        mock_time.return_value = start_time
        
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)
        
        # Phase 1: Normal operation (CLOSED)
        result = cb.call(lambda: "success1")
        self.assertEqual(result, "success1")
        self.assertEqual(cb.state, CircuitState.CLOSED)
        
        # Phase 2: Failures accumulate
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail1")))
        self.assertEqual(cb.state, CircuitState.CLOSED)
        
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail2")))
        self.assertEqual(cb.state, CircuitState.OPEN)
        
        # Phase 3: Failing fast (OPEN)
        with self.assertRaises(CircuitBreakerError):
            cb.call(lambda: "should not execute")
        
        # Phase 4: Recovery timeout passes
        mock_time.return_value = start_time + 10.0
        
        # Phase 5: HALF_OPEN - success closes circuit
        result = cb.call(lambda: "recovery success")
        self.assertEqual(result, "recovery success")
        self.assertEqual(cb.state, CircuitState.CLOSED)
        
        # Phase 6: Back to normal operation
        result = cb.call(lambda: "back to normal")
        self.assertEqual(result, "back to normal")

    def test_consecutive_circuits(self) -> None:
        """Multiple circuit breakers should operate independently."""
        cb1 = CircuitBreaker(name="circuit1", failure_threshold=1)
        cb2 = CircuitBreaker(name="circuit2", failure_threshold=2)
        
        # Open cb1
        with self.assertRaises(ValueError):
            cb1.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        self.assertEqual(cb1.state, CircuitState.OPEN)
        
        # cb2 is still closed
        self.assertEqual(cb2.state, CircuitState.CLOSED)
        cb2.call(lambda: "success")
        self.assertEqual(cb2.state, CircuitState.CLOSED)


class TestCircuitBreakerError(unittest.TestCase):
    """Test cases for CircuitBreakerError."""

    def test_error_attributes(self) -> None:
        """CircuitBreakerError should have message and state."""
        err = CircuitBreakerError("test error", CircuitState.OPEN)
        self.assertEqual(str(err), "test error")
        self.assertEqual(err.state, CircuitState.OPEN)

    def test_error_in_message(self) -> None:
        """Error message should contain circuit name and state."""
        cb = CircuitBreaker(name="my-circuit", failure_threshold=1)
        
        with self.assertRaises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        
        with self.assertRaises(CircuitBreakerError) as ctx:
            cb.call(lambda: "test")
        
        self.assertIn("my-circuit", str(ctx.exception))
        self.assertIn("OPEN", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
