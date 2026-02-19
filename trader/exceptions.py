"""Custom exceptions for the trader package."""


class ValidationError(Exception):
    """Raised when data validation fails.

    Args:
        message: A descriptive error message explaining the validation failure.
    """

    def __init__(self, message: str) -> None:
        """Initialize ValidationError with a descriptive message.

        Args:
            message: The error message describing the validation failure.
        """
        self.message = message
        super().__init__(self.message)


class MaxRetriesExceededError(Exception):
    """Raised when maximum retry attempts are exhausted.

    Args:
        message: A descriptive error message explaining that all retries failed.
    """

    def __init__(self, message: str) -> None:
        """Initialize MaxRetriesExceededError with a descriptive message.

        Args:
            message: The error message describing the retry exhaustion.
        """
        self.message = message
        super().__init__(self.message)
