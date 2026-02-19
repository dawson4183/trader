"""Custom exceptions for the trader package.

This module defines exception classes used throughout the trader package
for handling validation errors and other error conditions.

Example:
    Catching validation errors:

    >>> from trader.exceptions import ValidationError
    >>> try:
    ...     validate_price(-10.00)
    ... except ValidationError as e:
    ...     print(f"Validation failed: {e.message}")
"""


class ValidationError(Exception):
    """Raised when data validation fails.

    This exception is raised by validation functions in the trader package
    when input data does not meet the expected criteria.

    Attributes:
        message: A descriptive error message explaining the validation failure.

    Example:
        >>> try:
        ...     validate_price(0)
        ... except ValidationError as e:
        ...     print(e.message)
        'Price must be greater than 0, got: 0'
    """

    def __init__(self, message: str) -> None:
        """Initialize ValidationError with a descriptive message.

        Args:
            message: The error message describing the validation failure.
        """
        self.message = message
        super().__init__(self.message)


class MaxRetriesExceededError(Exception):
    """Raised when all retry attempts have been exhausted.
    
    This exception is raised by the retry decorator when a function
    continues to fail after all retry attempts have been exhausted.
    
    Attributes:
        message: A descriptive error message explaining the failure.
    """
    
    def __init__(self, message: str) -> None:
        """Initialize MaxRetriesExceededError with a descriptive message.
        
        Args:
            message: The error message describing the retry exhaustion.
        """
        self.message = message
        super().__init__(self.message)
