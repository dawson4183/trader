from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from .exceptions import ValidationError


def parse_item(html: str, selectors: Dict[str, str]) -> Dict[str, Any]:
    """
    Parse an item from HTML using CSS selectors.
    
    Args:
        html: The HTML content to parse
        selectors: Dict mapping field names to CSS selectors
        
    Returns:
        Dict containing extracted item data
        
    Raises:
        ValidationError: If required selectors are missing or parsing fails
    """
    validate_html_structure(html, list(selectors.values()))
    
    soup = BeautifulSoup(html, 'html.parser')
    item: Dict[str, Any] = {}
    
    for field, selector in selectors.items():
        element = soup.select_one(selector)
        if element:
            item[field] = element.get_text(strip=True)
        else:
            raise ValidationError(f"Could not find element for field '{field}' with selector '{selector}'")
    
    # Generate item hash from content
    content_str = ''.join(str(v) for v in item.values())
    item['item_hash'] = str(hash(content_str) % (2**32))
    
    return item


def validate_html_structure(html: str, required_selectors: List[str]) -> None:
    """
    Validate that HTML contains expected CSS selectors before parsing.
    
    Args:
        html: The HTML content to validate
        required_selectors: List of CSS selectors that must be present
        
    Raises:
        ValidationError: If any required selector is not found in the HTML
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    for selector in required_selectors:
        if not soup.select(selector):
            raise ValidationError(f"Required CSS selector not found: {selector}")


def validate_price(price: float) -> None:
    """
    Validate that price is greater than 0.
    
    Args:
        price: The price value to validate
        
    Raises:
        ValidationError: If price is not greater than 0
    """
    if price <= 0:
        raise ValidationError(f"Price must be greater than 0, got: {price}")


def deduplicate_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate items based on item_hash field.
    
    Args:
        items: List of item dictionaries, each containing an 'item_hash' key
        
    Returns:
        List of unique items (first occurrence kept)
        
    Raises:
        ValidationError: If an item is missing the 'item_hash' field
    """
    seen_hashes = set()
    unique_items = []
    
    for item in items:
        if 'item_hash' not in item:
            raise ValidationError(f"Item missing required 'item_hash' field: {item}")
        
        item_hash = item['item_hash']
        if item_hash not in seen_hashes:
            seen_hashes.add(item_hash)
            unique_items.append(item)
    
    return unique_items
