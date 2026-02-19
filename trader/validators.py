"""Validation functions for the trader package."""

from typing import Any, Dict, List, Union

from bs4 import BeautifulSoup

from trader.exceptions import ValidationError


def validate_html_structure(html: str, required_selectors: List[str]) -> bool:
    """Validate that HTML contains all required CSS selectors.

    Args:
        html: The HTML content to validate.
        required_selectors: A list of CSS selectors that must exist in the HTML.

    Returns:
        True if all required selectors are found in the HTML.

    Raises:
        ValidationError: If any required selectors are missing from the HTML.
                         Error message lists all missing selectors.
    """
    soup = BeautifulSoup(html, 'html.parser')

    missing_selectors: List[str] = []

    for selector in required_selectors:
        # Attempt to select elements using the CSS selector
        elements = soup.select(selector)
        if not elements:
            missing_selectors.append(selector)

    if missing_selectors:
        selector_list = ', '.join(missing_selectors)
        raise ValidationError(f'Missing required selectors: {selector_list}')

    return True


def validate_price(price: Union[int, float]) -> bool:
    """Validate that a price value is numeric and greater than 0.

    Args:
        price: The price value to validate. Must be an int or float.

    Returns:
        True if price is numeric and greater than 0.

    Raises:
        ValidationError: If price is not numeric (int or float).
        ValidationError: If price is less than or equal to 0.
    """
    # Check if price is numeric (int or float)
    if not isinstance(price, (int, float)):
        raise ValidationError('Price must be numeric')

    # Check if price is greater than 0
    if price <= 0:
        raise ValidationError(f'Price must be greater than 0, got: {price}')

    return True


def deduplicate_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate items based on item_hash field, keeping first occurrence.

    Args:
        items: A list of dictionaries, each containing an 'item_hash' key.

    Returns:
        A new list with duplicates removed, preserving order of first occurrences.

    Raises:
        ValidationError: If any item is missing the 'item_hash' key.
                         Error message format: 'Item missing item_hash: {item}'
    """
    seen_hashes: set[str] = set()
    unique_items: List[Dict[str, Any]] = []

    for item in items:
        # Check if item has item_hash key
        if 'item_hash' not in item:
            raise ValidationError(f'Item missing item_hash: {item}')

        item_hash = item['item_hash']
        if item_hash not in seen_hashes:
            seen_hashes.add(item_hash)
            unique_items.append(item)

    return unique_items
