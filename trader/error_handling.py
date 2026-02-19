"""Error handling utilities with retry decorator and circuit breaker."""
import time
import functools
import json
import os
import atexit
import tempfile
import threading
from pathlib import Path
from typing import Callable, Any, TypeVar, Optional, Tuple, Type, Dict, List
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
        self._lock = threading.Lock()
    
    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Call a function with circuit breaker protection."""
        with self._lock:
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
        with self._lock:
            self.failure_count = 0
            self.state = CircuitState.CLOSED
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        with self._lock:
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


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception
) -> Callable[[F], F]:
    """Circuit breaker decorator factory.
    
    Creates a circuit breaker decorator with specified configuration.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        expected_exception: Exception type(s) to count as failures
        
    Returns:
        Decorator that wraps function with circuit breaker protection
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
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    delay: float = 1.0,
    backoff: float = 2.0,
) -> Callable[[F], F]:
    """Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        exceptions: Tuple of exception types to catch and retry on
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        
    Returns:
        Decorated function with retry logic
    """
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
            raise MaxRetriesExceededError(f"Function failed after {max_attempts} attempts")
        
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
        self.retry_decorator = retry(
            max_attempts=max_attempts,
            exceptions=(Exception,),
            delay=delay,
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
    
    def __call__(self, func: F) -> F:
        """Apply both retry and circuit breaker to a function."""
        retried = self.retry_decorator(func)
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.circuit_breaker.call(retried, *args, **kwargs)
        
        return wrapper  # type: ignore


class ScraperState:
    """Manages scraper state persistence to JSON file.
    
    Saves and loads scraper state including circuit breaker status,
    failure counts, pending/completed URLs, and timestamps.
    
    Uses atomic writes (temp file + rename) to prevent corruption.
    Automatically registers atexit handler to save on uncaught exceptions.
    
    Attributes:
        state_file: Path to the JSON state file
        circuit_state: Current state of the circuit breaker (CLOSED, OPEN, HALF_OPEN)
        failure_count: Number of consecutive failures
        last_failure_time: Timestamp of the last failure
        pending_urls: List of URLs pending processing
        completed_urls: List of completed URLs
    """
    
    DEFAULT_STATE_FILE = Path.home() / ".trader" / "scraper_state.json"
    
    def __init__(
        self,
        state_file: Optional[Path] = None,
        circuit_state: CircuitState = CircuitState.CLOSED,
        failure_count: int = 0,
        last_failure_time: Optional[float] = None,
        pending_urls: Optional[List[str]] = None,
        completed_urls: Optional[List[str]] = None
    ):
        self.state_file = state_file or self.DEFAULT_STATE_FILE
        self.circuit_state = circuit_state
        self.failure_count = failure_count
        self.last_failure_time = last_failure_time
        self.pending_urls = pending_urls or []
        self.completed_urls = completed_urls or []
        self._atexit_registered = False
    
    def _ensure_directory_exists(self) -> None:
        """Ensure the state file directory exists."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    def save_state(self) -> None:
        """Save current state to JSON file using atomic write.
        
        Writes to a temporary file first, then renames to prevent
        corruption if the process crashes mid-write.
        """
        self._ensure_directory_exists()
        
        state_data = {
            "circuit_state": self.circuit_state.name,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "pending_urls": self.pending_urls,
            "completed_urls": self.completed_urls,
            "timestamp": time.time()
        }
        
        # Atomic write: write to temp file, then rename
        temp_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.tmp',
            prefix='scraper_state_',
            dir=self.state_file.parent,
            delete=False
        )
        
        try:
            json.dump(state_data, temp_file, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())  # Ensure data is written to disk
            temp_file.close()
            
            # Atomic rename
            os.rename(temp_file.name, self.state_file)
        except Exception:
            temp_file.close()
            # Clean up temp file on failure
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass
            raise
    
    def load_state(self) -> Dict[str, Any]:
        """Load state from JSON file.
        
        Returns:
            Dictionary containing the loaded state data
            
        Raises:
            FileNotFoundError: If state file doesn't exist
            json.JSONDecodeError: If state file is corrupted
        """
        with open(self.state_file, 'r') as f:
            return json.load(f)
    
    def load_and_restore(self) -> None:
        """Load state from file and restore instance attributes."""
        state_data = self.load_state()
        
        # Restore circuit state
        circuit_state_name = state_data.get("circuit_state", "CLOSED")
        self.circuit_state = CircuitState[circuit_state_name]
        
        # Restore other fields
        self.failure_count = state_data.get("failure_count", 0)
        self.last_failure_time = state_data.get("last_failure_time")
        self.pending_urls = state_data.get("pending_urls", [])
        self.completed_urls = state_data.get("completed_urls", [])
    
    def register_atexit_handler(self) -> None:
        """Register atexit handler to save state on uncaught exceptions."""
        if not self._atexit_registered:
            atexit.register(self._atexit_save)
            self._atexit_registered = True
    
    def _atexit_save(self) -> None:
        """Save state on program exit (called by atexit)."""
        # Only save if there's something worth saving
        if (self.failure_count > 0 or 
            self.pending_urls or 
            self.completed_urls or
            self.circuit_state != CircuitState.CLOSED):
            try:
                self.save_state()
            except Exception:
                # Don't raise during atexit
                pass
    
    def state_exists(self) -> bool:
        """Check if a state file exists."""
        return self.state_file.exists()
    
    def clear_state(self) -> None:
        """Remove the state file if it exists."""
        if self.state_file.exists():
            self.state_file.unlink()
