"""Item parser with validation integration for the trader package."""

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
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize ItemParser with configuration.

        Args:
            config: Configuration dictionary containing:
                - required_selectors: List of CSS selectors required in HTML

        Raises:
            ValidationError: If config is missing required_selectors key.
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

        Finds item elements based on required_selectors and extracts
        item data including name, price, and item_hash.

        Args:
            html: The HTML content to parse.

        Returns:
            A list of item dictionaries.

        Raises:
            ValidationError: If any extracted item has an invalid price.
        """
        soup = BeautifulSoup(html, 'html.parser')
        items: List[Dict[str, Any]] = []

        # Use the first required selector to find item containers
        # This is a simple implementation - real-world might have dedicated item selector
        if not self.required_selectors:
            return items

        # Find elements that match our selectors and extract item data
        # Strategy: Look for elements with data attributes for item data
        for selector in self.required_selectors:
            elements = soup.select(selector)
            for elem in elements:
                item = self._extract_item_data(elem)
                if item:
                    # Validate price during extraction
                    if 'price' in item:
                        validate_price(item['price'])
                    items.append(item)

        return items

    def _extract_item_data(self, element: Any) -> Union[Dict[str, Any], None]:
        """Extract item data from a BeautifulSoup element.

        Extracts item attributes from HTML data attributes or element content.

        Args:
            element: A BeautifulSoup element.

        Returns:
            A dictionary containing item data, or None if extraction fails.
        """
        item: Dict[str, Any] = {}

        # Extract from data attributes
        if hasattr(element, 'attrs') and 'data-item-hash' in element.attrs:
            item['item_hash'] = element['data-item-hash']

        if hasattr(element, 'attrs') and 'data-price' in element.attrs:
            try:
                price_str = element['data-price']
                item['price'] = float(price_str)
            except (ValueError, TypeError):
                item['price'] = 0  # Will fail validation
        elif hasattr(element, 'attrs') and 'data-item-price' in element.attrs:
            try:
                price_str = element['data-item-price']
                item['price'] = float(price_str)
            except (ValueError, TypeError):
                item['price'] = 0  # Will fail validation

        if hasattr(element, 'attrs') and 'data-name' in element.attrs:
            item['name'] = element['data-name']
        elif element.get_text(strip=True):
            item['name'] = element.get_text(strip=True)

        # Generate hash if not provided
        if 'item_hash' not in item and 'name' in item:
            import hashlib
            item['item_hash'] = hashlib.md5(item['name'].encode()).hexdigest()

        return item if item else None
