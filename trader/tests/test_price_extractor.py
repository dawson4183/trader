"""Tests for price_extractor module edge cases."""
import pytest

from trader.price_extractor import (
    extract_price,
    extract_price_with_currency,
    format_price,
)
from trader.exceptions import ValidationError


class TestExtractPriceEmptyInput:
    """Test extract_price with empty and whitespace-only inputs."""

    def test_extract_price_empty_string(self) -> None:
        """Should raise ValidationError for empty string input."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("")
        assert "empty" in str(exc_info.value).lower()

    def test_extract_price_whitespace_only(self) -> None:
        """Should raise ValidationError for whitespace-only input."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("   ")
        assert "empty" in str(exc_info.value).lower()

    def test_extract_price_whitespace_tabs_newlines(self) -> None:
        """Should raise ValidationError for tabs and newlines only."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("\t\n  \r\n")
        assert "empty" in str(exc_info.value).lower()


class TestExtractPriceZeroValue:
    """Test extract_price with zero values."""

    def test_extract_price_zero(self) -> None:
        """Should raise ValidationError for zero value."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("0")
        assert "zero" in str(exc_info.value).lower()

    def test_extract_price_zero_with_currency(self) -> None:
        """Should raise ValidationError for $0.00."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("$0.00")
        assert "zero" in str(exc_info.value).lower()

    def test_extract_price_zero_decimal(self) -> None:
        """Should raise ValidationError for 0.00."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("0.00")
        assert "zero" in str(exc_info.value).lower()

    def test_extract_price_zero_with_whitespace(self) -> None:
        """Should raise ValidationError for '  0.00  '."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("  0.00  ")
        assert "zero" in str(exc_info.value).lower()


class TestExtractPriceNegative:
    """Test extract_price with negative values."""

    def test_extract_price_negative(self) -> None:
        """Should raise ValidationError for negative value."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("-10.00")
        assert "negative" in str(exc_info.value).lower()

    def test_extract_price_negative_with_currency(self) -> None:
        """Should raise ValidationError for negative with currency."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("-$5.00")
        assert "negative" in str(exc_info.value).lower()

    def test_extract_price_negative_dash_after_currency(self) -> None:
        """Should raise ValidationError for $-5.00."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("$-5.00")
        assert "negative" in str(exc_info.value).lower()


class TestExtractPriceInvalidFormat:
    """Test extract_price with invalid formats."""

    def test_extract_price_invalid_format_non_numeric(self) -> None:
        """Should raise ValidationError for non-numeric string."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("abc")
        assert "could not parse" in str(exc_info.value).lower()

    def test_extract_price_invalid_format_special_chars(self) -> None:
        """Should raise ValidationError for special characters."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("@#$%")
        assert "could not parse" in str(exc_info.value).lower()

    def test_extract_price_invalid_format_mixed_text(self) -> None:
        """Should raise ValidationError for text mixed with numbers."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("price: abc123")
        assert "could not parse" in str(exc_info.value).lower()

    def test_extract_price_invalid_format_no_digits(self) -> None:
        """Should raise ValidationError for string without any digits."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("free")
        assert "could not parse" in str(exc_info.value).lower()


class TestExtractPriceNoneInput:
    """Test extract_price with None input."""

    def test_extract_price_none_input(self) -> None:
        """Should raise ValidationError for None input."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price(None)  # type: ignore[arg-type]
        assert "none" in str(exc_info.value).lower()


class TestExtractPriceValidValues:
    """Test extract_price with valid positive values."""

    def test_extract_price_positive_integer(self) -> None:
        """Should parse positive integer."""
        result = extract_price("10")
        assert result == 10.0

    def test_extract_price_positive_decimal(self) -> None:
        """Should parse positive decimal."""
        result = extract_price("10.99")
        assert result == 10.99

    def test_extract_price_with_dollar_sign(self) -> None:
        """Should parse price with dollar sign."""
        result = extract_price("$10.99")
        assert result == 10.99

    def test_extract_price_with_whitespace(self) -> None:
        """Should parse price with surrounding whitespace."""
        result = extract_price("  $15.50  ")
        assert result == 15.5

    def test_extract_price_with_thousands_separator(self) -> None:
        """Should parse price with comma thousands separator."""
        result = extract_price("1,234.56")
        assert result == 1234.56


class TestExtractPriceWithCurrencyEdgeCases:
    """Test extract_price_with_currency edge cases."""

    def test_extract_price_with_currency_empty_string(self) -> None:
        """Should raise ValidationError for empty string."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price_with_currency("")
        assert "empty" in str(exc_info.value).lower()

    def test_extract_price_with_currency_whitespace_only(self) -> None:
        """Should raise ValidationError for whitespace-only string."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price_with_currency("   ")
        assert "empty" in str(exc_info.value).lower()

    def test_extract_price_with_currency_none(self) -> None:
        """Should raise ValidationError for None."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price_with_currency(None)
        assert "none" in str(exc_info.value).lower()

    def test_extract_price_with_currency_zero(self) -> None:
        """Should raise ValidationError for zero."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price_with_currency("0")
        assert "zero" in str(exc_info.value).lower()

    def test_extract_price_with_currency_negative(self) -> None:
        """Should raise ValidationError for negative."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price_with_currency("-10.00")
        assert "negative" in str(exc_info.value).lower()

    def test_extract_price_with_currency_invalid_format(self) -> None:
        """Should raise ValidationError for non-numeric."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price_with_currency("abc")
        assert "no numeric" in str(exc_info.value).lower() or "could not parse" in str(exc_info.value).lower()


class TestFormatPriceEdgeCases:
    """Test format_price edge cases."""

    def test_format_price_zero(self) -> None:
        """Should format zero correctly."""
        result = format_price(0.0)
        assert result == "$0.00"

    def test_format_price_negative(self) -> None:
        """Should format negative correctly (allows negative in formatting)."""
        result = format_price(-10.0)
        assert result == "$-10.00"

    def test_format_price_different_currencies(self) -> None:
        """Should format different currencies."""
        assert format_price(10.0, "USD") == "$10.00"
        assert format_price(10.0, "EUR") == "€10.00"
        assert format_price(10.0, "GBP") == "£10.00"

    def test_format_price_unknown_currency(self) -> None:
        """Should default to $ for unknown currency."""
        result = format_price(10.0, "XYZ")
        assert result == "$10.00"
