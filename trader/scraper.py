"""Scraper module for HTTP data fetching.

This module provides a Scraper class for fetching web content with proper
error handling, structured logging, and type hints. It handles common HTTP
errors gracefully including connection errors and timeouts.

Also includes scraper_retry decorator with exponential backoff for network operations.

Example usage:
    >>> from trader.scraper import Scraper
    >>> scraper = Scraper(timeout=30)
    >>> content = scraper.fetch_url("https://example.com/data")

"""

import functools
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Literal, Optional, Tuple, Type, TypeVar, Union

from trader.exceptions import CircuitOpenError
import logging

F = TypeVar("F", bound=Callable[..., Any])

# Network-related exceptions that trigger retry
NETWORK_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    urllib.error.HTTPError,
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    ConnectionAbortedError,
)

T = TypeVar("T")
CircuitStateType = Literal["CLOSED", "OPEN", "HALF_OPEN"]


class CircuitBreaker:
    """Circuit breaker pattern implementation for resilient scraper operations.
    
    Implements the circuit breaker pattern with three states:
    - CLOSED: Normal operation, circuit allows calls through
    - OPEN: Too many failures, circuit rejects all calls immediately
    - HALF_OPEN: Recovery test mode, allows one test call to check health
    
    Transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After recovery_timeout seconds have passed
    - HALF_OPEN -> CLOSED: If the test call succeeds
    - HALF_OPEN -> OPEN: If the test call fails
    
    Thread-safe using threading.Lock for all state modifications.
    
    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit.
            Defaults to 10.
        recovery_timeout: Seconds to wait before testing recovery.
            Defaults to 60.
        current_state: Current state of the circuit.
        failure_count: Current number of consecutive failures.
        last_failure_time: Timestamp of the last failure, or None.
    """
    
    def __init__(
        self,
        failure_threshold: int = 10,
        recovery_timeout: float = 60.0,
    ) -> None:
        """Initialize the circuit breaker."""
        self.failure_threshold: int = failure_threshold
        self.recovery_timeout: float = recovery_timeout
        
        # Circuit state
        self._state: CircuitStateType = "CLOSED"
        self._failure_count: int = 0
        self._last_failure_time: Optional[float] = None
        
        # Thread safety
        self._lock: threading.Lock = threading.Lock()
    
    @property
    def current_state(self) -> CircuitStateType:
        """Get the current state of the circuit breaker."""
        with self._lock:
            return self._state
    
    @property
    def failure_count(self) -> int:
        """Get the current failure count."""
        with self._lock:
            return self._failure_count
    
    @property
    def last_failure_time(self) -> Optional[float]:
        """Get the timestamp of the last failure."""
        with self._lock:
            return self._last_failure_time
    
    def _can_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout
    
    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        self._state = "OPEN"
        self._last_failure_time = time.time()
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self._state = "HALF_OPEN"
    
    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        self._state = "CLOSED"
        self._failure_count = 0
        self._last_failure_time = None
    
    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            if self._state == "CLOSED":
                self._failure_count = 0
            elif self._state == "HALF_OPEN":
                self._transition_to_closed()
    
    def record_failure(self) -> None:
        """Record a failed operation and update circuit state."""
        with self._lock:
            if self._state == "CLOSED":
                self._failure_count += 1
                self._last_failure_time = time.time()
                if self._failure_count >= self.failure_threshold:
                    self._transition_to_open()
            elif self._state == "HALF_OPEN":
                self._failure_count += 1
                self._transition_to_open()
    
    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = "CLOSED"
            self._failure_count = 0
            self._last_failure_time = None
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with circuit breaker protection."""
        with self._lock:
            if self._state == "OPEN":
                if self._can_attempt_recovery():
                    self._transition_to_half_open()
                else:
                    raise CircuitOpenError(
                        f"Circuit breaker is OPEN after {self._failure_count} failures. "
                        f"Retry after {self.recovery_timeout} seconds."
                    )
            # HALF_OPEN and CLOSED states allow calls through
        
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise


def scraper_retry(
    func: Optional[F] = None,
    *,
    max_attempts: int = 5,
    initial_delay: float = 10.0,
    max_delay: float = 240.0,
    backoff_multiplier: float = 2.0,
) -> Union[F, Callable[[F], F]]:
    """Retry decorator with exponential backoff for scraper network operations.

    Specialized retry decorator with specific parameters:
    - 5 max attempts
    - 10 second initial delay
    - 240 second maximum delay cap
    - 2.0 exponential backoff multiplier
    - Catches only network-related exceptions

    Args:
        func: The function to decorate (for bare decorator usage).
        max_attempts: Maximum number of retry attempts. Defaults to 5.
        initial_delay: Initial delay between retries in seconds. Defaults to 10.
        max_delay: Maximum delay cap between retries in seconds. Defaults to 240.
        backoff_multiplier: Multiplier for delay after each retry. Defaults to 2.0.

    Returns:
        Decorated function with retry logic.

    Example:
        >>> @scraper_retry
        ... def fetch_data(url: str) -> str:
        ...     return requests.get(url).text
        >>>
        >>> @scraper_retry(max_attempts=3)
        ... def fetch_with_custom_attempts(url: str) -> str:
        ...     return requests.get(url).text

    """

    def decorator(wrapped_func: F) -> F:
        @functools.wraps(wrapped_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = initial_delay
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return wrapped_func(*args, **kwargs)
                except NETWORK_EXCEPTIONS as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay = min(
                            current_delay * backoff_multiplier, max_delay
                        )

            # All retries exhausted - re-raise the last exception
            if last_exception is not None:
                raise last_exception

            raise RuntimeError(f"Function failed after {max_attempts} attempts")

        return wrapper  # type: ignore

    if func is None:
        return decorator
    return decorator(func)


class Scraper:
    """HTTP scraper for fetching web content.
    
    Provides a simple interface for fetching URL content with configurable
    timeout and proper error handling. Uses structured JSON logging for
    all operations.
    
    Attributes:
        timeout: Request timeout in seconds.
        logger: Structured logger instance.
    
    Example:
        >>> scraper = Scraper(timeout=30)
        >>> html = scraper.fetch_url("https://example.com")
        >>> print(html[:100])  # First 100 characters
    """
    
    def __init__(self, timeout: int = 30) -> None:
        """Initialize the scraper.
        
        Args:
            timeout: Request timeout in seconds. Defaults to 30.
        """
        self.timeout: int = timeout
        self.logger: logging.Logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up structured logging for the scraper.
        
        Returns:
            A logger instance configured with standard logging Formatter.
        """
        logger = logging.getLogger("trader.scraper")
        
        # Only add handler if logger doesn't already have handlers
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    def fetch_url(self, url: str) -> Optional[str]:
        """Fetch content from a URL.
        
        Fetches the HTML/content from the given URL with configured timeout.
        Handles connection errors and timeouts gracefully by logging and
        returning None.
        
        Args:
            url: The URL to fetch.
            
        Returns:
            The response content as a string, or None if the request failed.
            
        Example:
            >>> scraper = Scraper()
            >>> content = scraper.fetch_url("https://example.com")
            >>> if content:
            ...     print(f"Fetched {len(content)} characters")
        """
        self.logger.info(
            f"Fetching URL: {url}",
            extra={"url": url, "timeout": self.timeout}
        )
        
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/91.0.4472.124 Safari/537.36"
                    )
                }
            )
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content: str = response.read().decode("utf-8")
                self.logger.info(
                    f"Successfully fetched {len(content)} characters from {url}",
                    extra={"url": url, "content_length": len(content)}
                )
                return content
                
        except urllib.error.HTTPError as e:
            self.logger.error(
                f"HTTP error {e.code} when fetching {url}",
                extra={"url": url, "error_code": e.code, "error": str(e)}
            )
            return None
            
        except urllib.error.URLError as e:
            self.logger.error(
                f"URL error when fetching {url}",
                extra={"url": url, "error": str(e)}
            )
            return None
            
        except TimeoutError:
            self.logger.error(
                f"Timeout when fetching {url}",
                extra={"url": url, "timeout": self.timeout}
            )
            return None
            
        except Exception as e:
            self.logger.error(
                f"Unexpected error when fetching {url}",
                extra={"url": url, "error": str(e), "error_type": type(e).__name__}
            )
            return None
