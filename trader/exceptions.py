"""Custom exceptions for the trader package.

This module defines custom exception classes used throughout the trader
package for handling validation and parsing errors.

Example:
    >>> from trader.exceptions import ValidationError
    >>> try:
    ...     validate_price(0)
    ... except ValidationError as e:
    ...     print(f"Validation failed: {e}")
"""


class ValidationError(Exception):
    """Exception raised when data validation fails.
    
    This exception is raised in various scenarios:
    - When HTML structure validation fails (missing required selectors)
    - When price validation fails (price <= 0)
    - When item deduplication encounters malformed data (missing item_hash)
    
    Attributes:
        message: Explanation of the validation error.
    
    Example:
        >>> raise ValidationError("Price must be greater than 0")
        Traceback (most recent call last):
          ...
        trader.exceptions.ValidationError: Price must be greater than 0
    """
    pass
