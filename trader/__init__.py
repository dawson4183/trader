"""Trader package for web scraping with error handling."""

from .scraper import Scraper
from .circuit_breaker import CircuitBreakerError

__all__ = ["Scraper", "CircuitBreakerError"]
