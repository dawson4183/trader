"""Trader package for web scraping with error handling."""

from .database import ConnectionPool, DatabaseManager, Transaction
from .scraper import Scraper
from .circuit_breaker import CircuitBreakerError
from .state import StateManager

__all__ = [
    "ConnectionPool",
    "DatabaseManager", 
    "Scraper",
    "CircuitBreakerError",
    "StateManager",
    "Transaction",
]