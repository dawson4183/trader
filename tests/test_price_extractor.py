"""Tests for price extraction with edge cases."""
import pytest
from trader.price_extractor import extract_price, format_price, CURRENCY_SYMBOLS
from trader.exceptions import ValidationError


class TestPriceExtractionEmpty:
    """Test edge cases with empty or None inputs."""

    def test_extract_none_raises_error(self):
        """None input should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price(None)
        assert "None" in str(exc_info.value)

    def test_extract_empty_string_raises_error(self):
        """Empty string should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("")
        assert "empty" in str(exc_info.value).lower()

    def test_extract_whitespace_only_raises_error(self):
        """Whitespace-only string should raise ValidationError."""
        with pytest.raises(ValidationError):
            extract_price("   ")

    def test_extract_whitespace_around_valid_price(self):
        """Price with surrounding whitespace should work."""
        result = extract_price("  $19.99  ")
        assert result['amount'] == 19.99


class TestPriceExtractionZero:
    """Test edge cases with zero prices."""

    def test_extract_zero_dollars_raises_error(self):
        """Zero price should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("$0.00")
        assert "zero" in str(exc_info.value).lower()

    def test_extract_zero_without_currency_raises_error(self):
        """Zero without currency should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("0")
        assert "zero" in str(exc_info.value).lower()

    def test_extract_zero_with_spaces_raises_error(self):
        """Zero with spaces should raise ValidationError."""
        with pytest.raises(ValidationError):
            extract_price("  0.00  ")


class TestPriceExtractionInvalid:
    """Test edge cases with invalid price formats."""

    def test_extract_negative_price_raises_error(self):
        """Negative price should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("$-10.00")
        assert "negative" in str(exc_info.value).lower()

    def test_extract_negative_without_symbol_raises_error(self):
        """Negative without symbol should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("-5.99")
        assert "negative" in str(exc_info.value).lower()

    def test_extract_no_numeric_value_raises_error(self):
        """String with no numbers should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            extract_price("Free")
        assert "numeric" in str(exc_info.value).lower() or "parse" in str(exc_info.value).lower()

    def test_extract_only_currency_symbol_raises_error(self):
        """Only currency symbol should raise ValidationError."""
        with pytest.raises(ValidationError):
            extract_price("$")

    def test_extract_only_currency_code_raises_error(self):
        """Only currency code should raise ValidationError."""
        with pytest.raises(ValidationError):
            extract_price("USD")

    def test_extract_random_text_raises_error(self):
        """Random text should raise ValidationError."""
        with pytest.raises(ValidationError):
            extract_price("Contact for price")

    def test_extract_special_characters_only_raises_error(self):
        """Special characters only should raise ValidationError."""
        with pytest.raises(ValidationError):
            extract_price("!@#$%")


class TestPriceExtractionCurrencies:
    """Test extraction with different currencies."""

    def test_extract_usd_with_symbol(self):
        """USD with $ symbol."""
        result = extract_price("$19.99")
        assert result['amount'] == 19.99
        assert result['currency'] == 'USD'
        assert result['raw'] == '$19.99'

    def test_extract_eur_with_symbol(self):
        """EUR with € symbol."""
        result = extract_price("€50.00")
        assert result['amount'] == 50.00
        assert result['currency'] == 'EUR'

    def test_extract_gbp_with_symbol(self):
        """GBP with £ symbol."""
        result = extract_price("£99.99")
        assert result['amount'] == 99.99
        assert result['currency'] == 'GBP'

    def test_extract_jpy_with_symbol(self):
        """JPY with ¥ symbol."""
        result = extract_price("¥1000")
        assert result['amount'] == 1000.0
        assert result['currency'] == 'JPY'

    def test_extract_inr_with_symbol(self):
        """INR with ₹ symbol."""
        result = extract_price("₹500")
        assert result['amount'] == 500.0
        assert result['currency'] == 'INR'

    def test_extract_usd_with_code(self):
        """USD with code."""
        result = extract_price("25.99 USD")
        assert result['amount'] == 25.99
        assert result['currency'] == 'USD'

    def test_extract_eur_with_code(self):
        """EUR with code."""
        result = extract_price("100 EUR")
        assert result['amount'] == 100.0
        assert result['currency'] == 'EUR'

    def test_extract_gbp_with_code(self):
        """GBP with code."""
        result = extract_price("75 GBP")
        assert result['amount'] == 75.0
        assert result['currency'] == 'GBP'

    def test_extract_cad_with_code(self):
        """CAD with code."""
        result = extract_price("150 CAD")
        assert result['amount'] == 150.0
        assert result['currency'] == 'CAD'

    def test_extract_aud_with_code(self):
        """AUD with code."""
        result = extract_price("200 AUD")
        assert result['amount'] == 200.0
        assert result['currency'] == 'AUD'

    def test_extract_symbol_takes_precedence_over_code(self):
        """Symbol should take precedence when both present."""
        result = extract_price("$100 EUR")  # Ambiguous but $ wins
        assert result['currency'] == 'USD'

    def test_extract_currency_code_case_insensitive(self):
        """Currency codes should be case insensitive."""
        result = extract_price("50 eur")
        assert result['currency'] == 'EUR'


class TestPriceExtractionFormats:
    """Test various price formatting edge cases."""

    def test_extract_price_with_commas_thousands(self):
        """US format: 1,234.56"""
        result = extract_price("$1,234.56")
        assert result['amount'] == 1234.56

    def test_extract_price_with_commas_decimal_european(self):
        """European format: 1.234,56"""
        result = extract_price("€1.234,56")
        assert result['amount'] == 1234.56

    def test_extract_price_with_space_separator(self):
        """Price with space as thousands separator."""
        result = extract_price("$1 234.56")
        assert result['amount'] == 1234.56

    def test_extract_price_with_multiple_decimals(self):
        """Multiple decimal points should be handled by keeping last as decimal."""
        result = extract_price("$1.234.56")
        # This parses as 1234.56 (removing all but last dot)
        assert result['amount'] == 1234.56

    def test_extract_very_small_price(self):
        """Very small positive price."""
        result = extract_price("$0.01")
        assert result['amount'] == 0.01

    def test_extract_very_large_price(self):
        """Very large price."""
        result = extract_price("$1,000,000.00")
        assert result['amount'] == 1000000.00

    def test_extract_price_no_decimal(self):
        """Price without decimal places."""
        result = extract_price("$50")
        assert result['amount'] == 50.0

    def test_extract_price_single_decimal(self):
        """Price with single decimal place."""
        result = extract_price("$10.5")
        assert result['amount'] == 10.5


class TestPriceFormatting:
    """Test price formatting function."""

    def test_format_price_usd_default(self):
        """Default formatting with USD."""
        result = format_price(19.99)
        assert result == "$19.99"

    def test_format_price_eur(self):
        """Formatting with EUR."""
        result = format_price(50.00, 'EUR')
        assert result == "€50.00"

    def test_format_price_gbp(self):
        """Formatting with GBP."""
        result = format_price(99.99, 'GBP')
        assert result == "£99.99"

    def test_format_price_rounds_decimals(self):
        """Formatting rounds to 2 decimal places."""
        result = format_price(10.999, 'USD')
        assert result == "$11.00"

    def test_format_price_zero(self):
        """Formatting zero price."""
        result = format_price(0, 'USD')
        assert result == "$0.00"

    def test_format_price_unknown_currency(self):
        """Unknown currency uses default $."""
        result = format_price(100, 'XYZ')
        assert result.startswith('$')
