"""Trader package for parsing, validating, and deduplicating trading items.

This package provides functionality for:
- Validating HTML structure against required CSS selectors
- Parsing items from HTML with price validation
- Deduplicating items based on item hash
- Error handling with retry decorator and circuit breaker
- Scraper state persistence

Example:
    >>> from trader import validate_html_structure, ValidationError
    >>> html = "<div class='item'>Item</div>"
    >>> validate_html_structure(html, ['.item'])

Attributes:
    __version__: The version of the trader package.
"""

from trader.exceptions import ValidationError, MaxRetriesExceededError, CircuitBreakerOpenError
from trader.item_parser import ItemParser, parse_item
from trader.validators import (
    deduplicate_items,
    validate_html_structure,
    validate_price,
)
from trader.error_handling import (
    retry,
    CircuitBreaker,
    CircuitState,
    RetryWithCircuitBreaker,
    ScraperState,
    circuit_breaker,
)

__version__ = "0.1.0"

__all__ = [
    "ItemParser",
    "ValidationError",
    "MaxRetriesExceededError",
    "CircuitBreakerOpenError",
    "deduplicate_items",
    "parse_item",
    "validate_html_structure",
    "validate_price",
    "retry",
    "CircuitBreaker",
    "CircuitState",
    "RetryWithCircuitBreaker",
    "ScraperState",
    "circuit_breaker",
]
