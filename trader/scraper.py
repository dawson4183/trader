"""Scraper module for HTTP data fetching.

This module provides utilities for robust web scraping with retry logic,
circuit breaker pattern, and state persistence for recovery from crashes.

This module provides a Scraper class for fetching web content with proper
error handling, structured logging, and type hints. It handles common HTTP
errors gracefully including connection errors and timeouts.

Also includes scraper_retry decorator with exponential backoff for network operations.

Example usage:
    >>> from trader.scraper import Scraper
    >>> scraper = Scraper(timeout=30)
    >>> content = scraper.fetch_url("https://example.com/data")

"""

import atexit
import functools
import json
import logging
import os
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

from trader.logging_utils import JsonFormatter

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


class ScraperState:
    """State persistence manager for scraper operations.
    
    Saves and loads scraper state to/from a JSON file, enabling recovery
    from crashes and shutdowns. Uses atomic writes to prevent corruption.
    
    Attributes:
        state_file: Path to the state file.
        state_dir: Directory containing state file.
        circuit_state: Current circuit breaker state.
        failure_count: Current failure count.
        last_failure_time: ISO timestamp of last failure.
        pending_urls: List of URLs pending processing.
        completed_urls: List of URLs that were successfully processed.
    
    Example:
        >>> state = ScraperState()
        >>> state.save_state(circuit_state="closed", failure_count=0, 
        ...                  pending_urls=["https://example.com"])
        >>> loaded_state = ScraperState.load_state()
    
    """
    
    def __init__(self, state_file: Optional[str] = None) -> None:
        """Initialize the ScraperState.
        
        Args:
            state_file: Path to state file. Defaults to ~/.trader/scraper_state.json.
        """
        self._initialized: bool = True
        
        if state_file is None:
            self.state_dir: Path = Path.home() / ".trader"
            self.state_file: Path = self.state_dir / "scraper_state.json"
        else:
            self.state_file = Path(state_file)
            self.state_dir = self.state_file.parent
        
        # State values stored for atexit handler
        self.circuit_state: str = "closed"
        self.failure_count: int = 0
        self.last_failure_time: Optional[str] = None
        self.pending_urls: List[str] = []
        self.completed_urls: List[str] = []
        
        self._ensure_state_dir()
        self._register_atexit_handler()
    
    def _ensure_state_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def _register_atexit_handler(self) -> None:
        """Register atexit handler to save state on uncaught exceptions."""
        atexit.register(self._cleanup_on_exit)
    
    def _cleanup_on_exit(self) -> None:
        """Save state when program exits (called by atexit)."""
        try:
            # Save current state without needing parameters
            self._atomic_save()
        except Exception:
            # Silently fail on atexit - can't do much at this point
            pass
    
    def _atomic_save(self) -> Path:
        """Internal method to save current state atomically."""
        state_data: Dict[str, Any] = {
            "circuit_state": self.circuit_state,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "pending_urls": self.pending_urls,
            "completed_urls": self.completed_urls,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._state_data = state_data  # Store for atexit
        
        # Atomic write: write to temp file, then rename
        temp_file = self.state_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, sort_keys=True)
            
            # Atomic rename
            temp_file.replace(self.state_file)
            
        except Exception:
            # Clean up temp file on failure
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise
        
        return self.state_file
    
    def save_state(
        self,
        circuit_state: str = "closed",
        failure_count: int = 0,
        last_failure_time: Optional[str] = None,
        pending_urls: Optional[List[str]] = None,
        completed_urls: Optional[List[str]] = None,
    ) -> Path:
        """Save scraper state to JSON file using atomic write.
        
        Writes to a temporary file first, then renames it to the target
        file path atomically to prevent corruption.
        
        Args:
            circuit_state: Current circuit breaker state ("closed", "open", "half_open").
            failure_count: Current failure count.
            last_failure_time: ISO format timestamp of last failure.
            pending_urls: List of URLs pending processing.
            completed_urls: List of URLs that were successfully processed.
            
        Returns:
            Path to the saved state file.
            
        Raises:
            IOError: If unable to write state file.
        
        Example:
            >>> state = ScraperState()
            >>> state.save_state(circuit_state="closed", failure_count=0)
        
        """
        self.circuit_state = circuit_state
        self.failure_count = failure_count
        self.last_failure_time = last_failure_time
        self.pending_urls = pending_urls or []
        self.completed_urls = completed_urls or []
        
        return self._atomic_save()
    
    def load_state(self) -> Dict[str, Any]:
        """Load scraper state from JSON file.
        
        Returns:
            Dictionary containing saved state.
            
        Raises:
            FileNotFoundError: If state file doesn't exist.
            json.JSONDecodeError: If state file is corrupted.
        
        Example:
            >>> state = ScraperState()
            >>> try:
            ...     saved_state = state.load_state()
            ...     print(f"Circuit: {saved_state['circuit_state']}")
            ... except FileNotFoundError:
            ...     print("No saved state found")
        
        """
        if not self.state_file.exists():
            raise FileNotFoundError(f"State file not found: {self.state_file}")
        
        with open(self.state_file, 'r', encoding='utf-8') as f:
            data: Dict[str, Any] = json.load(f)
            return data
    
    def clear_state(self) -> None:
        """Clear/reset the saved state (useful for testing)."""
        if self.state_file.exists():
            self.state_file.unlink()
    
    @classmethod
    def load_state_from_file(cls, state_file: str) -> Dict[str, Any]:
        """Class method to load state from a specific file.
        
        Args:
            state_file: Path to state file.
            
        Returns:
            Dictionary containing saved state.
            
        Raises:
            FileNotFoundError: If state file doesn't exist.
        
        Example:
            >>> state = ScraperState.load_state_from_file("/path/to/state.json")
        
        """
        instance = cls(state_file)
        return instance.load_state()


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
            A logger instance configured with JsonFormatter.
        """
        logger = logging.getLogger("trader.scraper")
        
        # Only add handler if logger doesn't already have handlers
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(JsonFormatter())
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


# Global state instance for automatic cleanup
_global_state: Optional[ScraperState] = None


def get_global_state(state_file: Optional[str] = None) -> ScraperState:
    """Get or create global ScraperState instance.
    
    This enables automatic state persistence across modules.
    
    Args:
        state_file: Optional custom state file path.
        
    Returns:
        Global ScraperState instance.
    
    """
    global _global_state  # noqa: PLW0603
    if _global_state is None:
        _global_state = ScraperState(state_file)
    return _global_state