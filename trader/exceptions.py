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


class MaxRetriesExceededError(Exception):
    """Exception raised when all retry attempts are exhausted.
    
    This exception is raised by the retry decorator when the maximum
    number of retry attempts has been reached without success.
    
    Attributes:
        message: Explanation of the failure.
        __cause__: The original exception that caused the final failure.
    
    Example:
        >>> raise MaxRetriesExceededError("Operation failed after 5 attempts")
        Traceback (most recent call last):
          ...
        trader.exceptions.MaxRetriesExceededError: Operation failed after 5 attempts
    """
    pass


class CircuitOpenError(Exception):
    """Exception raised when circuit breaker is open.
    
    This exception is raised by the circuit breaker when it is in
    the OPEN state and rejects further calls.
    
    Attributes:
        message: Explanation including failure count and threshold.
    
    Example:
        >>> raise CircuitOpenError("Circuit breaker is OPEN after 10 failures")
        Traceback (most recent call last):
          ...
        trader.exceptions.CircuitOpenError: Circuit breaker is OPEN after 10 failures
    """
    pass
