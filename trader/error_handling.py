"""Error handling utilities with retry decorator and circuit breaker."""
import time
import functools
from typing import Callable, Any, TypeVar, Optional, Tuple, Type, Union, List
from enum import Enum, auto
from .exceptions import ValidationError, MaxRetriesExceededError


F = TypeVar('F', bound=Callable[..., Any])


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Failing, reject requests
    HALF_OPEN = auto()   # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
    
    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Call a function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise ValidationError(f"Circuit breaker is OPEN - service unavailable")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try reset."""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def __call__(self, func: F) -> F:
        """Use circuit breaker as a decorator."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.call(func, *args, **kwargs)
        return wrapper  # type: ignore


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
            
            # All retries exhausted - re-raise the last exception
            if last_exception is not None:
                raise last_exception
            
            # Should not reach here, but for type safety
            raise MaxRetriesExceededError(
                f"Function failed after {max_attempts} attempts"
            )
        
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
