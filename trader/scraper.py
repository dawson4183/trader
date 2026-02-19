"""Scraper module for HTTP data fetching.

This module provides a Scraper class for fetching web content with proper
error handling, structured logging, and type hints. It handles common HTTP
errors gracefully including connection errors and timeouts.

Example usage:
    >>> from trader.scraper import Scraper
    >>> scraper = Scraper(timeout=30)
    >>> content = scraper.fetch_url("https://example.com/data")

"""

import logging
import urllib.error
import urllib.request
from typing import Optional

from trader.logging_utils import JsonFormatter


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