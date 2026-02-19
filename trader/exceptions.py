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


class CircuitOpenError(Exception):
    """Raised when circuit breaker is OPEN.

    This exception is raised by the CircuitBreaker when the circuit
    is in OPEN state, meaning calls are rejected without attempting
    the underlying operation. This protects downstream services from
    being overwhelmed when failures exceed the threshold.

    Attributes:
        message: Explanation of why the circuit is open.
        failure_count: Number of consecutive failures that caused the circuit to open.

    Example:
        >>> raise CircuitOpenError("Circuit breaker is OPEN after 10 failures")
        Traceback (most recent call last):
          ...
        trader.exceptions.CircuitOpenError: Circuit breaker is OPEN after 10 failures
    """
    pass
