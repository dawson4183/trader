"""Item parser module with validation integration for the trader package.

This module provides the ItemParser class for extracting, validating,
and deduplicating trading items from HTML content.

Example:
    Using ItemParser to parse items from HTML:

    >>> from trader.item_parser import ItemParser
    >>> config = {'required_selectors': ['.item', '.price']}
    >>> parser = ItemParser(config)
    >>> html = "<div class='item' data-price='19.99' data-item-hash='abc123'>Item</div>"
    >>> items = parser.parse(html)
    >>> print(len(items))
    1
"""

from typing import Any, Dict, List, Union

from bs4 import BeautifulSoup

from trader.exceptions import ValidationError
from trader.validators import deduplicate_items, validate_html_structure, validate_price


class ItemParser:
    """Parser for extracting items from HTML with validation.

    This class handles the complete parsing workflow including HTML structure
    validation, item extraction with price validation, and deduplication.

    Attributes:
        config: Configuration dictionary containing required_selectors list.
        required_selectors: List of CSS selectors required in HTML.

    Example:
        >>> config = {'required_selectors': ['.item']}
        >>> parser = ItemParser(config)
        >>> html = "<div class='item' data-price='10.00' data-item-hash='h1'>Item</div>"
        >>> items = parser.parse(html)
        >>> items[0]['price']
        10.0
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize ItemParser with configuration.

        Args:
            config: Configuration dictionary containing:
                - required_selectors: List of CSS selectors required in HTML

        Raises:
            ValidationError: If config is missing required_selectors key.

        Example:
            >>> config = {'required_selectors': ['.item']}
            >>> parser = ItemParser(config)
        """
        if 'required_selectors' not in config:
            raise ValidationError("Config must contain 'required_selectors' key")

        self.config = config
        self.required_selectors: List[str] = config['required_selectors']

    def parse(self, html: str) -> List[Dict[str, Any]]:
        """Parse HTML and extract items with validation.

        This method performs the following steps:
        1. Validates HTML structure against required_selectors
        2. Extracts items from HTML
        3. Validates price for each extracted item
        4. Deduplicates items based on item_hash

        Args:
            html: The HTML content to parse.

        Returns:
            A list of unique item dictionaries.

        Raises:
            ValidationError: If HTML structure is invalid (missing selectors).
            ValidationError: If any item has an invalid price.
        """
        # Step 1: Validate HTML structure
        validate_html_structure(html, self.required_selectors)

        # Step 2: Extract items from HTML
        items = self._extract_items(html)

        # Step 3: Validate prices (already done during extraction)
        # Step 4: Deduplicate items
        unique_items = deduplicate_items(items)

        return unique_items

    def _extract_items(self, html: str) -> List[Dict[str, Any]]:
        """Extract items from HTML content.

        Args:
            html: The HTML content to parse.

        Returns:
            A list of item dictionaries.

        Raises:
            ValidationError: If any extracted item has an invalid price.
        """
        soup = BeautifulSoup(html, 'html.parser')
        items: List[Dict[str, Any]] = []

        if not self.required_selectors:
            return items

        for selector in self.required_selectors:
            elements = soup.select(selector)
            for elem in elements:
                item = self._extract_item_data(elem)
                if item:
                    if 'price' in item:
                        validate_price(item['price'])
                    items.append(item)

        return items

    def _extract_item_data(self, element: Any) -> Union[Dict[str, Any], None]:
        """Extract item data from a BeautifulSoup element.

        Args:
            element: A BeautifulSoup element.

        Returns:
            A dictionary containing item data, or None if extraction fails.
        """
        item: Dict[str, Any] = {}

        if hasattr(element, 'attrs') and 'data-item-hash' in element.attrs:
            item['item_hash'] = element['data-item-hash']

        if hasattr(element, 'attrs') and 'data-price' in element.attrs:
            try:
                price_str = element['data-price']
                item['price'] = float(price_str)
            except (ValueError, TypeError):
                item['price'] = 0

        if hasattr(element, 'attrs') and 'data-name' in element.attrs:
            item['name'] = element['data-name']
        elif element.get_text(strip=True):
            item['name'] = element.get_text(strip=True)

        if 'item_hash' not in item and 'name' in item:
            import hashlib
            item['item_hash'] = hashlib.md5(item['name'].encode()).hexdigest()

        return item if item else None


def parse_item(html: str, selectors: Dict[str, str]) -> Dict[str, Any]:
    """Parse a single item from HTML using CSS selectors.

    Args:
        html: The HTML content to parse.
        selectors: Dictionary mapping field names to CSS selectors.

    Returns:
        A dictionary containing the extracted item data.

    Raises:
        ValidationError: If required selectors are missing or parsing fails.
    """
    validate_html_structure(html, list(selectors.values()))

    soup = BeautifulSoup(html, 'html.parser')
    item: Dict[str, Any] = {}

    for field, selector in selectors.items():
        element = soup.select_one(selector)
        if element:
            item[field] = element.get_text(strip=True)
        else:
            raise ValidationError(
                f"Could not find element for field '{field}' with selector '{selector}'"
            )

    content_str = ''.join(str(v) for v in item.values())
    item['item_hash'] = str(hash(content_str) % (2**32))

    return item
