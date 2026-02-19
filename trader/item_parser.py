import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .exceptions import ValidationError

# Get logger for this module
logger = logging.getLogger(__name__)


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
            logger.warning(
                "HTML validation failed - CSS selector not found",
                extra={
                    "selector": selector,
                    "html_length": len(html),
                    "required_selectors": required_selectors
                }
            )
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
        logger.warning(
            "Price validation failed - price must be greater than 0",
            extra={
                "price": price,
                "validation_rule": "price > 0"
            }
        )
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
    duplicate_count = 0
    
    for item in items:
        if 'item_hash' not in item:
            logger.error(
                "Item validation failed - missing item_hash field",
                extra={
                    "item_keys": list(item.keys()),
                    "item_preview": str(item)[:100]
                }
            )
            raise ValidationError(f"Item missing required 'item_hash' field: {item}")
        
        item_hash = item['item_hash']
        if item_hash not in seen_hashes:
            seen_hashes.add(item_hash)
            unique_items.append(item)
        else:
            duplicate_count += 1
    
    # Log deduplication stats at INFO level
    total_items = len(items)
    unique_count = len(unique_items)
    if total_items > 0:
        logger.info(
            "Deduplication completed",
            extra={
                "total_items": total_items,
                "unique_items": unique_count,
                "duplicates_removed": duplicate_count,
                "deduplication_rate": duplicate_count / total_items
            }
        )
    
    return unique_items
