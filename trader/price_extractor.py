"""Price extraction utilities with support for multiple currencies."""
import re
from typing import Optional, Dict, Any
from decimal import Decimal, InvalidOperation
from .exceptions import ValidationError


CURRENCY_SYMBOLS: Dict[str, str] = {
    '$': 'USD',
    '€': 'EUR',
    '£': 'GBP',
    '¥': 'JPY',
    '₹': 'INR',
    'CAD': 'CAD',
    'AUD': 'AUD',
}

CURRENCY_CODES = ['USD', 'EUR', 'GBP', 'JPY', 'INR', 'CAD', 'AUD']


def extract_price(price_str: Optional[str]) -> Dict[str, Any]:
    """
    Extract price value and currency from a string.
    
    Args:
        price_str: String containing price (e.g., "$19.99", "€50", "100 CAD")
        
    Returns:
        Dict with 'amount' (float), 'currency' (str), and 'raw' (str)
        
    Raises:
        ValidationError: If price cannot be parsed or is invalid
    """
    if price_str is None:
        raise ValidationError("Price string cannot be None")
    
    price_str = price_str.strip()
    
    if not price_str:
        raise ValidationError("Price string cannot be empty")
    
    # Detect currency from symbol first (takes precedence)
    currency = 'USD'  # Default
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in price_str:
            currency = code
            break
    else:
        # Only check codes if no symbol found
        for code in CURRENCY_CODES:
            if code in price_str.upper():
                currency = code
                break
    
    # Check for negative sign first
    is_negative = '-' in price_str
    
    # Extract numeric value
    # Remove currency symbols and codes, keep digits, decimal points, commas, and minus
    cleaned = re.sub(r'[^\d.,-]', '', price_str)
    
    if not cleaned:
        raise ValidationError(f"No numeric value found in price string: '{price_str}'")
    
    # Handle European format (1.234,56) vs US format (1,234.56)
    if ',' in cleaned and '.' in cleaned:
        if cleaned.rfind(',') > cleaned.rfind('.'):
            # European: 1.234,56
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            # US: 1,234.56
            cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        # Could be decimal separator or thousands separator
        if len(cleaned) - cleaned.rfind(',') == 3:
            # Likely thousands: 1,234
            cleaned = cleaned.replace(',', '')
        else:
            # Likely decimal: 12,34
            cleaned = cleaned.replace(',', '.')
    
    # Handle multiple dots (invalid format) - keep only the last one
    if cleaned.count('.') > 1:
        parts = cleaned.split('.')
        # Join all but last part (thousands), use last as decimal
        cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
    
    try:
        amount = float(cleaned)
    except ValueError:
        raise ValidationError(f"Could not parse price value from: '{price_str}'")
    
    # Apply negative if detected
    if is_negative:
        amount = -abs(amount)
    
    if amount < 0:
        raise ValidationError(f"Price cannot be negative: {amount}")
    
    if amount == 0:
        raise ValidationError("Price cannot be zero")
    
    return {
        'amount': amount,
        'currency': currency,
        'raw': price_str
    }


def format_price(amount: float, currency: str = 'USD') -> str:
    """Format a price amount with currency symbol."""
    symbols = {v: k for k, v in CURRENCY_SYMBOLS.items()}
    symbol = symbols.get(currency, '$')
    return f"{symbol}{amount:.2f}"
