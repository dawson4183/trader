"""Custom exceptions for the trader package."""


class ValidationError(Exception):
    """Raised when data validation fails.

    Contains a descriptive message explaining the validation failure.
    """
    
    def __init__(self, message: str) -> None:
        """Initialize ValidationError with a descriptive message.

        Args:
            message: The error message describing the validation failure.
        """
        self.message = message
        super().__init__(self.message)


class MaxRetriesExceededError(Exception):
    """Raised when retry decorator exhausts all attempts.

    Contains the count of attempts that were made before giving up.
    """
    
    def __init__(self, message: str) -> None:
        """Initialize MaxRetriesExceededError with a descriptive message.

        Args:
            message: The error message describing the retry failure.
        """
        self.message = message
        super().__init__(self.message)
