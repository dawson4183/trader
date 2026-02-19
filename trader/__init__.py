"""Trader package for item parsing and data validation.

This package provides tools for parsing trader items from HTML,
validating data structures, and managing item databases.

Example usage:
    >>> from trader import validate_html_structure, validate_price, deduplicate_items
    >>> from trader import ValidationError, Scraper, DatabaseConnection
    >>> 
    >>> # Validate HTML structure
    >>> validate_html_structure(html, ["div.item", "span.price"])
    >>> 
    >>> # Validate item price
    >>> validate_price(99.99)
    >>> 
    >>> # Remove duplicates from items list
    >>> unique_items = deduplicate_items(items)

Modules:
    item_parser: HTML structure validation and item deduplication utilities.
    exceptions: Custom exception classes for validation errors.
    scraper: HTTP scraper for fetching web content.
    database: SQLite database connection management.
    logging_utils: Structured logging utilities with JSON formatting.
    config: Logging and configuration settings.
"""

from trader.item_parser import validate_html_structure, validate_price, deduplicate_items
from trader.exceptions import ValidationError
from trader.scraper import Scraper
from trader.database import DatabaseConnection, get_connection
from trader.logging_utils import JsonFormatter, WebhookHandler

__version__ = "0.1.0"
__all__ = [
    # Validation functions
    "validate_html_structure",
    "validate_price",
    "deduplicate_items",
    # Exceptions
    "ValidationError",
    # Scraping
    "Scraper",
    # Database
    "DatabaseConnection",
    "get_connection",
    # Logging
    "JsonFormatter",
    "WebhookHandler",
]
