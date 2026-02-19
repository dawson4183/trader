"""Error handling utilities with retry and circuit breaker patterns.

This module provides decorators and classes for resilient error handling:
- retry: Decorator for exponential backoff retry
- CircuitBreaker: Circuit breaker pattern implementation
- CircuitState: Enum for circuit breaker states
- RetryWithCircuitBreaker: Combined retry and circuit breaker

Example:
    >>> from trader.error_handling import CircuitBreaker, retry
    >>> cb = CircuitBreaker(failure_threshold=10)
    >>> @cb
    ... def fetch_data():
    ...     return requests.get("https://api.example.com/data").json()

"""

import functools
import time
from enum import Enum
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union

from trader.exceptions import CircuitOpenError, MaxRetriesExceededError, ValidationError

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(Enum):
    """Circuit breaker states.
    
    CLOSED: Circuit is closed, calls pass through normally.
    OPEN: Circuit is open, calls are rejected immediately.
    HALF_OPEN: Circuit is testing if the service has recovered.
    
    Example:
        >>> state = CircuitState.CLOSED
        >>> print(state.value)
        'closed'
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker pattern implementation.
    
    Stops calling a failing service after a threshold of consecutive
    failures, allowing it time to recover.
    
    Attributes:
        state: Current circuit state (CLOSED, OPEN, HALF_OPEN).
        failure_count: Number of consecutive failures.
        failure_threshold: Number of failures before opening circuit.
        recovery_timeout: Seconds before attempting recovery.
        expected_exception: Exception type that counts as failure.
        last_failure_time: Timestamp of last failure.
        
    Example:
        >>> cb = CircuitBreaker(failure_threshold=10)
        >>> @cb
        ... def api_call():
        ...     return fetch_from_api()
    """
    
    def __init__(
        self,
        failure_threshold: int = 10,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
    ) -> None:
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Failures before opening circuit. Defaults to 10.
            recovery_timeout: Seconds before recovery attempt. Defaults to 60.
            expected_exception: Exception type that counts as failure.
        """
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.failure_threshold: int = failure_threshold
        self.recovery_timeout: float = recovery_timeout
        self.expected_exception: Type[Exception] = expected_exception
        self.last_failure_time: Optional[float] = None
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.state != CircuitState.OPEN:
            return False
        if self.last_failure_time is None:
            return False
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _can_execute(self) -> bool:
        """Check if call should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN - allow one test call
        return True
    
    def _on_success(self) -> None:
        """Reset circuit on success."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
    
    def _on_failure(self, error: Exception) -> None:
        """Count failure and open circuit if threshold reached."""
        if not isinstance(error, self.expected_exception):
            return  # Don't count unexpected exceptions
        
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection.
        
        Args:
            func: The function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.
            
        Returns:
            The function's return value.
            
        Raises:
            CircuitOpenError: When circuit is open.
            Any exception raised by func.
        """
        if not self._can_execute():
            raise CircuitOpenError(
                f"Circuit breaker is OPEN after {self.failure_count} failures. "
                f"Threshold: {self.failure_threshold}. "
                "Service temporarily unavailable."
            )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
    
    def __call__(self, func: F) -> F:
        """Make circuit breaker usable as decorator."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.call(func, *args, **kwargs)
        return wrapper  # type: ignore


def retry(
    func: Optional[F] = None,
    *,
    max_attempts: int = 5,
    delay: float = 10.0,
    backoff: float = 2.0,
    max_delay: float = 240.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Union[F, Callable[[F], F]]:
    """Retry decorator with exponential backoff.
    
    Retries the decorated function on specified exceptions with
    exponential backoff between attempts.
    
    Args:
        func: Function to decorate (for bare decorator usage).
        max_attempts: Maximum retry attempts. Defaults to 5.
        delay: Initial delay between retries. Defaults to 10.0.
        backoff: Delay multiplier after each retry. Defaults to 2.0.
        max_delay: Maximum delay cap. Defaults to 240.0.
        exceptions: Exception types to catch and retry.
        
    Returns:
        Decorated function with retry logic.
        
    Raises:
        MaxRetriesExceededError: When all attempts fail.
        
    Example:
        >>> @retry(max_attempts=3, exceptions=(ConnectionError,))
        ... def fetch_data():
        ...     return requests.get("https://api.example.com").json()
    """
    def decorator(wrapped_func: F) -> F:
        @functools.wraps(wrapped_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_attempts):
                try:
                    return wrapped_func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay = min(current_delay * backoff, max_delay)
            
            # All retries exhausted
            raise MaxRetriesExceededError(
                f"Function failed after {max_attempts} attempts"
            ) from last_exception
        
        return wrapper  # type: ignore
    
    if func is None:
        return decorator
    return decorator(func)


class RetryWithCircuitBreaker:
    """Combined retry and circuit breaker decorator.
    
    Applies both retry logic and circuit breaker protection
to decorated functions.
    
    Attributes:
        circuit_breaker: The circuit breaker instance.
        max_attempts: Number of retry attempts per call.
        delay: Initial retry delay.
        backoff: Delay multiplier.
        
    Example:
        >>> @RetryWithCircuitBreaker(max_attempts=3, failure_threshold=10)
        ... def api_call():
        ...     return requests.get("https://api.example.com").json()
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        delay: float = 10.0,
        backoff: float = 2.0,
        max_delay: float = 240.0,
        failure_threshold: int = 10,
        recovery_timeout: float = 60.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ) -> None:
        """Initialize combined decorator."""
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff = backoff
        self.max_delay = max_delay
        self.exceptions = exceptions
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=Exception,
        )
    
    def __call__(self, func: F) -> F:
        """Apply both retry and circuit breaker to function."""
        @functools.wraps(func)  
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.circuit_breaker.call(
                lambda: retry(
                    max_attempts=self.max_attempts,
                    delay=self.delay,
                    backoff=self.backoff,
                    max_delay=self.max_delay,
                    exceptions=self.exceptions,
                )(func)(*args, **kwargs)  # type: ignore
            )
        return wrapper  # type: ignore