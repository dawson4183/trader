"""Scraper module with HTTP client wrapper for web scraping."""

import urllib.request
import urllib.error
from typing import Optional

from trader.retry import retry_with_backoff


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
    """Web scraper with HTTP client for fetching data."""

    def __init__(self, client: Optional[HTTPClient] = None) -> None:
        """Initialize scraper with optional HTTP client.
        
        Args:
            client: HTTP client instance. If None, a default client is created.
        """
        self.client = client or HTTPClient()

    @retry_with_backoff(max_attempts=5)
    def fetch(self, url: str) -> str:
        """Fetch content from a URL.
        
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
