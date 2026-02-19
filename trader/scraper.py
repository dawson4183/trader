"""Scraper module with HTTP client wrapper for web scraping."""

import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from trader.retry import retry_with_backoff
from trader.circuit_breaker import CircuitBreaker, CircuitBreakerError


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
    """

    def __init__(
        self,
        client: Optional[HTTPClient] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        circuit_breaker_config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize scraper with optional HTTP client and circuit breaker.
        
        Args:
            client: HTTP client instance. If None, a default client is created.
            circuit_breaker: Pre-configured CircuitBreaker instance. If provided,
                circuit_breaker_config is ignored.
            circuit_breaker_config: Configuration dict for creating a new
                CircuitBreaker. Keys: 'failure_threshold', 'recovery_timeout', 'name'.
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

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance.
        
        Returns:
            The CircuitBreaker instance used by this scraper.
        """
        return self._circuit_breaker

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
        
        Args:
            url: The URL to fetch.
            
        Returns:
            The fetched content as a string.
            
        Raises:
            CircuitBreakerError: If the circuit breaker is OPEN.
            urllib.error.URLError: If all retry attempts fail.
            urllib.error.HTTPError: If a non-retryable HTTP error occurs (4xx except 429).
        """
        return self._circuit_breaker.call(self._fetch_with_retry, url)

    def scrape(self, url: str) -> dict:
        """Scrape data from a URL.
        
        This is a placeholder method for future scraping logic.
        
        Args:
            url: The URL to scrape.
            
        Returns:
            A dictionary containing scraped data.
        """
        content = self.fetch(url)
        return {"url": url, "content": content, "status": "fetched"}
