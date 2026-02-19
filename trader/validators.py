"""Validation functions for the trader package."""

from typing import List

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
