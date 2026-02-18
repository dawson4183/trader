"""Circuit breaker pattern implementation for fault tolerance."""

import time
from enum import Enum, auto
from typing import Callable, TypeVar, Any, Optional


T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = auto()      # Normal operation - requests pass through
    OPEN = auto()        # Failing fast - requests immediately rejected
    HALF_OPEN = auto()   # Testing - one request allowed to test recovery


class CircuitBreakerError(Exception):
    """Exception raised when the circuit breaker is OPEN."""
    def __init__(self, message: str, state: CircuitState) -> None:
        super().__init__(message)
        self.state = state


class CircuitBreaker:
    """Circuit breaker implementation to prevent cascading failures.
    
    The circuit breaker has three states:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Circuit is tripped, all requests immediately fail
    - HALF_OPEN: After recovery timeout, one request allowed to test recovery
    
    Configuration:
    - failure_threshold: Number of failures before opening circuit (default 5)
    - recovery_timeout: Seconds to wait before attempting recovery (default 30)
    
    State transitions:
    - CLOSED -> OPEN: After failure_threshold failures
    - OPEN -> HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN -> CLOSED: On successful request
    - HALF_OPEN -> OPEN: On failed request
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "default"
    ) -> None:
        """Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of consecutive failures before opening circuit.
            recovery_timeout: Seconds to wait before attempting recovery (half-open).
            name: Optional name for the circuit breaker (for logging/debugging).
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
    
    @property
    def state(self) -> CircuitState:
        """Get the current circuit state."""
        return self._state
    
    @property
    def failure_count(self) -> int:
        """Get the current failure count."""
        return self._failure_count
    
    def _can_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery.
        
        Returns:
            True if recovery timeout has elapsed since last failure.
        """
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout
    
    def _record_success(self) -> None:
        """Record a successful call and update state."""
        if self._state == CircuitState.HALF_OPEN:
            # Success in half-open closes the circuit
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
        elif self._state == CircuitState.CLOSED:
            # Success in closed state resets failure count
            self._failure_count = 0
    
    def _record_failure(self) -> None:
        """Record a failed call and update state."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            # Failure in half-open reopens the circuit
            self._state = CircuitState.OPEN
        elif self._state == CircuitState.CLOSED:
            # Check if we should open the circuit
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with circuit breaker protection.
        
        Args:
            func: The function to call.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.
            
        Returns:
            The result of the function call.
            
        Raises:
            CircuitBreakerError: If the circuit is OPEN.
            Any exception raised by the wrapped function.
        """
        # Check if we need to transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN:
            if self._can_attempt_reset():
                self._state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerError(
                    f"Circuit '{self.name}' is OPEN - failing fast",
                    self._state
                )
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Use circuit breaker as a decorator.
        
        Args:
            func: The function to wrap.
            
        Returns:
            A wrapped function with circuit breaker protection.
        """
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return self.call(func, *args, **kwargs)
        return wrapper
