"""Error handling utilities with retry decorator and circuit breaker."""
import time
import functools
import threading
from typing import Callable, Any, TypeVar, Optional, Tuple, Type, Union, List
from enum import Enum, auto
from .exceptions import ValidationError, MaxRetriesExceededError, CircuitBreakerOpenError


F = TypeVar('F', bound=Callable[..., Any])


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Failing, reject requests
    HALF_OPEN = auto()   # Testing if service recovered


# Alias for backward compatibility
ScraperState = CircuitState


class CircuitBreaker:
    """Circuit breaker pattern implementation with thread-safety."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state (thread-safe)."""
        with self._lock:
            return self._state
    
    @property
    def failure_count(self) -> int:
        """Get current failure count (thread-safe)."""
        with self._lock:
            return self._failure_count
    
    @property
    def last_failure_time(self) -> Optional[float]:
        """Get last failure time (thread-safe)."""
        with self._lock:
            return self._last_failure_time
    
    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Call a function with circuit breaker protection."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError(f"Circuit breaker is OPEN - service unavailable")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try reset."""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful call."""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
    
    def __call__(self, func: F) -> F:
        """Use circuit breaker as a decorator."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.call(func, *args, **kwargs)
        return wrapper  # type: ignore


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception
) -> Callable[[F], F]:
    """
    Circuit breaker decorator factory.
    
    Creates a circuit breaker decorator with specified configuration.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        expected_exception: Exception type(s) to count as failures
        
    Returns:
        Decorator that wraps function with circuit breaker protection
        
    Example:
        @circuit_breaker(failure_threshold=3, recovery_timeout=30.0)
        def fetch_data():
            return requests.get('http://api.example.com/data')
    """
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception
    )
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return breaker.call(func, *args, **kwargs)
        return wrapper  # type: ignore
    
    return decorator


def retry(
    max_attempts: int = 3,
    exceptions: Union[Tuple[Type[Exception], ...], List[Type[Exception]]] = (Exception,),
    delay: float = 1.0,
    backoff: float = 2.0,
) -> Callable[[F], F]:
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        exceptions: Tuple of exception types to catch and retry on
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        
    Returns:
        Decorated function with retry logic
        
    Raises:
        MaxRetriesExceededError: When all retry attempts are exhausted
    """
    # Convert list to tuple if needed
    if isinstance(exceptions, list):
        exceptions = tuple(exceptions)
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            # All retries exhausted - raise MaxRetriesExceededError
            error_msg = f"Function failed after {max_attempts} attempts"
            raise MaxRetriesExceededError(error_msg) from last_exception
        
        return wrapper  # type: ignore
    
    return decorator


class RetryWithCircuitBreaker:
    """Combines retry and circuit breaker patterns."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 1.0,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0
    ):
        self.max_attempts = max_attempts
        self.delay = delay
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
    
    def __call__(self, func: F) -> F:
        """Apply both retry and circuit breaker to a function."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = self.delay
            last_exception: Optional[Exception] = None
            
            for attempt in range(self.max_attempts):
                try:
                    return self.circuit_breaker.call(func, *args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < self.max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay *= 2.0
            
            # All retries exhausted - re-raise the last exception
            if last_exception is not None:
                raise last_exception
            
            raise MaxRetriesExceededError(
                f"Function failed after {self.max_attempts} attempts"
            )
        
        return wrapper  # type: ignore
