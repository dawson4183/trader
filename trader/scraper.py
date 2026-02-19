"""Scraper module with HTTP client wrapper for web scraping."""

import atexit
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from trader.retry import retry_with_backoff
from trader.circuit_breaker import CircuitBreaker, CircuitBreakerError
from trader.state import StateManager


class HTTPClient:
    """Basic HTTP client wrapper for making requests."""

    def __init__(self, timeout: int = 30) -> None:
        """Initialize HTTP client with timeout.
        
        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout

    def get(self, url: str) -> str:
        """Make a GET request to the specified URL.
        
        Args:
            url: The URL to fetch.
            
        Returns:
            The response body as a string.
            
        Raises:
            urllib.error.URLError: If the request fails.
        """
        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            return response.read().decode("utf-8")


class Scraper:
    """Web scraper with HTTP client for fetching data.
    
    The Scraper can be configured with a CircuitBreaker to prevent
    cascading failures when external services are unavailable.
    
    The Scraper also includes state management for crash recovery,
    allowing scraping to resume from the last saved state.
    """

    def __init__(
        self,
        client: Optional[HTTPClient] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        circuit_breaker_config: Optional[Dict[str, Any]] = None,
        state_manager: Optional[StateManager] = None,
        state_filepath: Optional[str] = None
    ) -> None:
        """Initialize scraper with optional HTTP client, circuit breaker, and state manager.
        
        Args:
            client: HTTP client instance. If None, a default client is created.
            circuit_breaker: Pre-configured CircuitBreaker instance. If provided,
                circuit_breaker_config is ignored.
            circuit_breaker_config: Configuration dict for creating a new
                CircuitBreaker. Keys: 'failure_threshold', 'recovery_timeout', 'name'.
            state_manager: Pre-configured StateManager instance. If None, a default
                StateManager is created with state_filepath if provided.
            state_filepath: Path for state file. Used if state_manager is not provided.
        """
        self.client = client or HTTPClient()
        
        # Initialize circuit breaker
        if circuit_breaker is not None:
            self._circuit_breaker = circuit_breaker
        elif circuit_breaker_config is not None:
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=circuit_breaker_config.get('failure_threshold', 5),
                recovery_timeout=circuit_breaker_config.get('recovery_timeout', 30.0),
                name=circuit_breaker_config.get('name', 'scraper')
            )
        else:
            # Default circuit breaker with sensible defaults
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=30.0,
                name='scraper'
            )
        
        # Initialize state manager
        if state_manager is not None:
            self._state_manager = state_manager
        elif state_filepath is not None:
            self._state_manager = StateManager(filepath=state_filepath)
        else:
            self._state_manager = StateManager()
        
        # Register atexit handler for emergency state save
        self._register_atexit_handler()

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance.
        
        Returns:
            The CircuitBreaker instance used by this scraper.
        """
        return self._circuit_breaker

    @property
    def state_manager(self) -> StateManager:
        """Get the state manager instance.
        
        Returns:
            The StateManager instance used by this scraper.
        """
        return self._state_manager

    def _register_atexit_handler(self) -> None:
        """Register atexit handler for emergency state save on SIGINT/SIGTERM."""
        def _emergency_save() -> None:
            """Save state on process exit."""
            if self._state_manager.filepath:
                self._state_manager.save_on_crash()
        
        atexit.register(_emergency_save)

    def save_state_on_exception(self, exc: Exception) -> None:
        """Save state before raising an exception.
        
        This method should be called from exception handlers to ensure
        state is persisted before the exception propagates.
        
        Args:
            exc: The exception that triggered the save.
        """
        self._state_manager.save_on_crash()

    def resume_from_state(self, filepath: Optional[str] = None) -> bool:
        """Resume scraping from saved state.
        
        Loads state from a JSON file and restores the scraper's position.
        
        Args:
            filepath: Path to the state file. Uses state_manager's default if None.
        
        Returns:
            True if state was loaded successfully, False if no state file exists.
        """
        target_path = filepath or self._state_manager.filepath
        if target_path is None:
            return False
        
        return self._state_manager.load(target_path)

    def clear_state(self, filepath: Optional[str] = None) -> bool:
        """Clear the state file after successful completion.
        
        Args:
            filepath: Path to the state file. Uses state_manager's default if None.
        
        Returns:
            True if state file was deleted or didn't exist, False on error.
        """
        from pathlib import Path
        
        target_path = filepath or self._state_manager.filepath
        if target_path is None:
            return True
        
        try:
            path_obj = Path(target_path)
            if path_obj.exists():
                path_obj.unlink()
            return True
        except Exception:
            return False

    @retry_with_backoff(max_attempts=5)
    def _fetch_with_retry(self, url: str) -> str:
        """Internal fetch method with retry logic.
        
        This method uses exponential backoff retry (max 5 attempts)
        for transient failures like connection errors, timeouts,
        and HTTP 5xx or 429 responses.
        
        Args:
            url: The URL to fetch.
            
        Returns:
            The fetched content as a string.
            
        Raises:
            urllib.error.URLError: If all retry attempts fail.
            urllib.error.HTTPError: If a non-retryable HTTP error occurs (4xx except 429).
        """
        return self.client.get(url)

    def fetch(self, url: str) -> str:
        """Fetch content from a URL with circuit breaker protection.
        
        This method wraps the actual fetch operation through the circuit breaker
        to prevent cascading failures. It also uses exponential backoff retry
        (max 5 attempts) for transient failures.
        
        On exception, state is saved before re-raising for crash recovery.
        
        Args:
            url: The URL to fetch.
            
        Returns:
            The fetched content as a string.
            
        Raises:
            CircuitBreakerError: If the circuit breaker is OPEN.
            urllib.error.URLError: If all retry attempts fail.
            urllib.error.HTTPError: If a non-retryable HTTP error occurs (4xx except 429).
        """
        # Update state with current URL before attempting fetch
        self._state_manager.update(url=url)
        
        try:
            return self._circuit_breaker.call(self._fetch_with_retry, url)
        except Exception as e:
            # Save state before re-raising exception
            self.save_state_on_exception(e)
            raise

    def scrape(self, url: str) -> dict:
        """Scrape data from a URL.
        
        This is a placeholder method for future scraping logic.
        
        On successful completion, the state file is cleared.
        
        Args:
            url: The URL to scrape.
            
        Returns:
            A dictionary containing scraped data.
        """
        # Update state before scraping
        self._state_manager.update(url=url)
        
        try:
            content = self.fetch(url)
            result = {"url": url, "content": content, "status": "fetched"}
            
            # Clear state on successful completion
            self.clear_state()
            
            return result
        except Exception as e:
            # Save state before re-raising
            self.save_state_on_exception(e)
            raise
