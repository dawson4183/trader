"""HTML parser module for extracting item data from HTML."""
from typing import Dict, Any
from bs4 import BeautifulSoup
from .exceptions import ValidationError


def parse_item(html: str) -> Dict[str, Any]:
    """
    Parse an item from HTML using BeautifulSoup.
    
    Extracts item_name from .item-name selector, price from .price selector,
    and item_hash from data-hash attribute.
    
    Args:
        html: The HTML content to parse
        
    Returns:
        Dict containing extracted item data with keys:
            - item_name: str - The item name from .item-name element
            - price: str - The price text from .price element
            - item_hash: str - The value from data-hash attribute
            
    Raises:
        ValidationError: If HTML is malformed or required elements are missing
    """
    if not html or not html.strip():
        raise ValidationError("HTML content is empty")
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        raise ValidationError(f"Failed to parse HTML: {e}")
    
    # Extract item_name from .item-name selector
    name_element = soup.select_one('.item-name')
    if not name_element:
        raise ValidationError("Could not find item name element with selector '.item-name'")
    item_name = name_element.get_text(strip=True)
    
    # Extract price from .price selector
    price_element = soup.select_one('.price')
    if not price_element:
        raise ValidationError("Could not find price element with selector '.price'")
    price = price_element.get_text(strip=True)
    
    # Extract item_hash from data-hash attribute
    # Look for any element with data-hash attribute
    hash_element = soup.find(attrs={'data-hash': True})
    if not hash_element:
        raise ValidationError("Could not find element with 'data-hash' attribute")
    item_hash = hash_element.get('data-hash')
    
    if not item_hash:
        raise ValidationError("Element with 'data-hash' attribute has empty value")
    
    return {
        'item_name': item_name,
        'price': price,
        'item_hash': str(item_hash)
    }


def validate_html_structure(html: str) -> None:
    """
    Validate that HTML contains expected structure for parsing.
    
    Checks for presence of .item-name, .price elements and data-hash attribute.
    
    Args:
        html: The HTML content to validate
        
    Raises:
        ValidationError: If HTML structure is invalid or missing required elements
    """
    if not html or not html.strip():
        raise ValidationError("HTML content is empty")
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        raise ValidationError(f"Failed to parse HTML: {e}")
    
    # Check for required elements
    if not soup.select_one('.item-name'):
        raise ValidationError("Required element not found: .item-name")
    
    if not soup.select_one('.price'):
        raise ValidationError("Required element not found: .price")
    
    if not soup.find(attrs={'data-hash': True}):
        raise ValidationError("Required attribute not found: data-hash")
