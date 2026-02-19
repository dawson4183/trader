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
    
    The Scraper also integrates with StateManager for crash recovery,
    allowing state to be persisted before process exit on crash.
    """

    def __init__(
        self,
        client: Optional[HTTPClient] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        circuit_breaker_config: Optional[Dict[str, Any]] = None,
        state_manager: Optional[StateManager] = None,
        state_file: Optional[str] = None
    ) -> None:
        """Initialize scraper with optional HTTP client, circuit breaker, and state manager.
        
        Args:
            client: HTTP client instance. If None, a default client is created.
            circuit_breaker: Pre-configured CircuitBreaker instance. If provided,
                circuit_breaker_config is ignored.
            circuit_breaker_config: Configuration dict for creating a new
                CircuitBreaker. Keys: 'failure_threshold', 'recovery_timeout', 'name'.
            state_manager: Pre-configured StateManager instance. If None and
                state_file is provided, a new StateManager is created.
            state_file: Path to the state file for save/load operations.
                Used if state_manager is not provided.
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
        self._state_manager: Optional[StateManager]
        if state_manager is not None:
            self._state_manager = state_manager
        elif state_file is not None:
            self._state_manager = StateManager(filepath=state_file)
        else:
            # No state management by default
            self._state_manager = None
        
        self._state_file = state_file
        self._atexit_registered = False
        
        # Register atexit handler if we have a state manager
        if self._state_manager is not None:
            atexit.register(self._emergency_save_state)
            self._atexit_registered = True

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance.
        
        Returns:
            The CircuitBreaker instance used by this scraper.
        """
        return self._circuit_breaker
    
    @property
    def state_manager(self) -> Optional[StateManager]:
        """Get the state manager instance.
        
        Returns:
            The StateManager instance used by this scraper, or None.
        """
        return self._state_manager

    def _emergency_save_state(self) -> None:
        """Emergency state save for atexit handler.
        
        This method is called on program exit (normal or via SIGINT/SIGTERM)
        to ensure state is persisted.
        """
        if self._state_manager is not None:
            try:
                self._state_manager.save_on_crash(self._state_file)
            except Exception:
                # Best effort - don't let emergency save cause issues
                pass
    
    def _save_state_on_error(self) -> None:
        """Save state when an exception occurs.
        
        This method is called before re-raising exceptions to ensure
        state is persisted for crash recovery.
        """
        if self._state_manager is not None:
            try:
                self._state_manager.save_on_crash(self._state_file)
            except Exception:
                # Best effort - don't let state saving cause additional failures
                pass
    
    def clear_state(self) -> bool:
        """Clear the state file after successful completion.
        
        Returns:
            True if state file was deleted or didn't exist, False on error.
        """
        import os
        
        filepath = self._state_file or (self._state_manager.filepath if self._state_manager else None)
        if filepath is None:
            return True
        
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        except Exception:
            return False
    
    def resume_from_state(self) -> bool:
        """Resume scraping from saved state.
        
        Loads state from the state file and updates the state manager.
        The caller can then use the state manager's properties to
        determine where to resume from.
        
        Returns:
            True if state was loaded successfully, False if no state file exists.
        """
        if self._state_manager is None:
            return False
        
        return self._state_manager.load(self._state_file)

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
        
        On exception, the current state is saved before the exception is re-raised.
        
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
        if self._state_manager is not None:
            self._state_manager.update(url=url)
        
        try:
            result = self._circuit_breaker.call(self._fetch_with_retry, url)
            return result
        except Exception:
            # Save state before re-raising exception
            self._save_state_on_error()
            raise

    def scrape(self, url: str, clear_state_on_success: bool = True) -> dict:
        """Scrape data from a URL.
        
        This method fetches content from the URL and returns structured data.
        On successful completion, the state file is cleared by default.
        
        Args:
            url: The URL to scrape.
            clear_state_on_success: Whether to clear the state file on success.
            
        Returns:
            A dictionary containing scraped data.
            
        Raises:
            CircuitBreakerError: If the circuit breaker is OPEN.
            urllib.error.URLError: If all retry attempts fail.
            urllib.error.HTTPError: If a non-retryable HTTP error occurs.
        """
        try:
            content = self.fetch(url)
            result = {"url": url, "content": content, "status": "fetched"}
            
            # Clear state on successful completion
            if clear_state_on_success:
                self.clear_state()
            
            return result
        except Exception:
            # Ensure state is saved before re-raising
            self._save_state_on_error()
            raise
