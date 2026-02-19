"""Tests for trader exceptions."""
import sys
import os
import importlib.util

# Import directly from file to avoid circular imports through package __init__
spec = importlib.util.spec_from_file_location("exceptions", os.path.join(os.path.dirname(__file__), '..', 'trader', 'exceptions.py'))
exceptions_module = importlib.util.module_from_spec(spec)
sys.modules["exceptions"] = exceptions_module
spec.loader.exec_module(exceptions_module)
ValidationError = exceptions_module.ValidationError

import pytest


class TestValidationError:
    """Test cases for ValidationError exception class."""

    def test_validation_error_inherits_from_exception(self) -> None:
        """Verify ValidationError inherits from Exception."""
        assert issubclass(ValidationError, Exception)

    def test_validation_error_accepts_message_parameter(self) -> None:
        """Verify ValidationError accepts a message parameter."""
        message = "Test validation error message"
        error = ValidationError(message)
        assert error.message == message

    def test_validation_error_stores_message_as_instance_attribute(self) -> None:
        """Verify ValidationError stores message as instance attribute."""
        message = "Price must be greater than 0"
        error = ValidationError(message)
        assert hasattr(error, 'message')
        assert error.message == message

    def test_validation_error_can_be_raised_with_message(self) -> None:
        """Verify ValidationError can be raised with a descriptive message."""
        message = "Invalid HTML structure"
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError(message)
        assert str(exc_info.value) == message
        assert exc_info.value.message == message

    def test_validation_error_message_is_accessible_via_str(self) -> None:
        """Verify the message is accessible via str() conversion."""
        message = "Duplicate item found"
        error = ValidationError(message)
        assert str(error) == message

    def test_validation_error_different_messages(self) -> None:
        """Verify ValidationError works with different message types."""
        # Test various message formats
        messages = [
            "Simple error",
            "Error with numbers: 123",
            "Error with special chars: !@#$%",
            "Multiline\nerror\nmessage",
            "Very long message: " + "x" * 1000,
        ]
        for msg in messages:
            error = ValidationError(msg)
            assert error.message == msg
            assert str(error) == msg