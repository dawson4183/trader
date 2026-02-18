"""Retry decorator with exponential backoff for transient HTTP failures."""

import time
import functools
from typing import Callable, TypeVar, Optional, Tuple, Any
import urllib.error
import http.client


# Type variable for the return type of the decorated function
T = TypeVar("T")


class TransientError(Exception):
    """Exception representing a transient error that should be retried."""
    pass


class RetryableHTTPError(TransientError):
    """HTTP error that should be retried (5xx, 429)."""
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class NonRetryableHTTPError(Exception):
    """HTTP error that should NOT be retried (4xx except 429)."""
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _is_retryable_exception(exc: Exception) -> bool:
    """Determine if an exception represents a transient error that should be retried.
    
    Retryable exceptions:
    - ConnectionError and subclasses (includes URLError with certain messages)
    - Timeout errors (TimeoutError, socket.timeout)
    - HTTP 5xx server errors
    - HTTP 429 Too Many Requests
    
    Non-retryable exceptions:
    - HTTP 4xx client errors (except 429)
    
    Args:
        exc: The exception to check.
        
    Returns:
        True if the exception is retryable, False otherwise.
    """
    # Connection errors are always retryable
    if isinstance(exc, ConnectionError):
        return True
    
    # Timeout errors are always retryable
    if isinstance(exc, TimeoutError):
        return True
    
    # Check for HTTPError from urllib
    if isinstance(exc, urllib.error.HTTPError):
        # 5xx server errors are retryable
        if 500 <= exc.code < 600:
            return True
        # 429 Too Many Requests is retryable
        if exc.code == 429:
            return True
        # All other 4xx are not retryable
        if 400 <= exc.code < 500:
            return False
    
    # Check for HTTPException (from http.client)
    if isinstance(exc, http.client.HTTPException):
        # Treat HTTPException as potentially transient
        return True
    
    # URLError - check if it contains connection-related messages
    if isinstance(exc, urllib.error.URLError):
        reason_str = str(exc.reason).lower() if hasattr(exc, 'reason') else str(exc).lower()
        connection_keywords = ['connection', 'refused', 'reset', 'timeout', 'unreachable', 'dns']
        if any(keyword in reason_str for keyword in connection_keywords):
            return True
        # General URLError treated as retryable
        return True
    
    # Custom retryable error types
    if isinstance(exc, RetryableHTTPError):
        return True
    
    # Non-retryable custom error
    if isinstance(exc, NonRetryableHTTPError):
        return False
    
    # Default: don't retry unknown exceptions
    return False


def _get_backoff_delay(attempt: int, base_delay: float = 1.0) -> float:
    """Calculate the exponential backoff delay for a given attempt.
    
    Args:
        attempt: The current attempt number (0-indexed).
        base_delay: The base delay in seconds (default 1.0).
        
    Returns:
        The delay in seconds for this attempt.
    """
    return base_delay * (2 ** attempt)


def retry_with_backoff(
    max_attempts: int = 5,
    base_delay: float = 1.0,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that retries a function with exponential backoff.
    
    Only retries on transient errors (ConnectionError, Timeout, HTTP 5xx, 429).
    Does NOT retry on 4xx client errors (except 429).
    
    Args:
        max_attempts: Maximum number of attempts (default 5).
        base_delay: Base delay in seconds for exponential backoff (default 1.0).
        on_retry: Optional callback function called on each retry.
                 Receives (exception, attempt_number, next_delay).
        
    Returns:
        A decorator that wraps the function with retry logic.
        
    Raises:
        The last exception encountered after all attempts are exhausted,
        or immediately if a non-retryable exception is raised.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc
                    
                    # Check if this is a retryable exception
                    if not _is_retryable_exception(exc):
                        # Non-retryable exception - raise immediately
                        raise
                    
                    # If this was the last attempt, break and raise
                    if attempt >= max_attempts - 1:
                        break
                    
                    # Calculate backoff delay
                    delay = _get_backoff_delay(attempt, base_delay)
                    
                    # Call the on_retry callback if provided
                    if on_retry:
                        on_retry(exc, attempt + 1, delay)
                    
                    # Wait before retrying
                    time.sleep(delay)
            
            # All attempts exhausted - raise the last exception
            if last_exception:
                raise last_exception
            
            # This should never be reached
            raise RuntimeError("Unexpected error in retry decorator")
        
        return wrapper
    return decorator