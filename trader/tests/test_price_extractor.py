"""Tests for price extraction functionality."""
import pytest
from trader.price_extractor import extract_price
from trader.exceptions import ValidationError


class TestExtractPrice:
    """Tests for extract_price function."""
    
    def test_extract_price_usd_prefix(self) -> None:
        """Test extracting price with $ prefix."""
        assert extract_price('$10.99') == 10.99
        
    def test_extract_price_euro_prefix(self) -> None:
        """Test extracting price with € prefix."""
        assert extract_price('€20.50') == 20.50
        
    def test_extract_price_pound_prefix(self) -> None:
        """Test extracting price with £ prefix."""
        assert extract_price('£15.00') == 15.00
        
    def test_extract_price_whitespace_stripping(self) -> None:
        """Test that whitespace is stripped from price strings."""
        assert extract_price('  $10.99  ') == 10.99
        assert extract_price('\t€20.50\n') == 20.50
        assert extract_price('  £15.00  ') == 15.00
        
    def test_extract_price_no_symbol(self) -> None:
        """Test extracting price without currency symbol."""
        assert extract_price('10.99') == 10.99
        assert extract_price('100') == 100.0
        
    def test_extract_price_with_comma(self) -> None:
        """Test extracting price with comma thousands separator."""
        assert extract_price('$1,234.56') == 1234.56
        assert extract_price('€1,000') == 1000.0
        
    def test_extract_price_empty_raises_error(self) -> None:
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError, match="empty"):
            extract_price('')
            
    def test_extract_price_whitespace_only_raises_error(self) -> None:
        """Test that whitespace-only string raises ValidationError."""
        with pytest.raises(ValidationError, match="empty"):
            extract_price('   ')
        with pytest.raises(ValidationError, match="empty"):
            extract_price('\t\n  ')
            
    def test_extract_price_none_raises_error(self) -> None:
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError, match="None"):
            extract_price(None)  # type: ignore
            
    def test_extract_price_invalid_raises_error(self) -> None:
        """Test that unparseable strings raise ValidationError."""
        with pytest.raises(ValidationError, match="parse"):
            extract_price('abc')
        with pytest.raises(ValidationError, match="parse"):
            extract_price('no price here')
            
    def test_extract_price_negative_raises_error(self) -> None:
        """Test that negative prices raise ValidationError."""
        with pytest.raises(ValidationError, match="negative"):
            extract_price('-$10.00')
        with pytest.raises(ValidationError, match="negative"):
            extract_price('-10.00')
            
    def test_extract_price_zero_raises_error(self) -> None:
        """Test that zero price raises ValidationError."""
        with pytest.raises(ValidationError, match="zero"):
            extract_price('$0.00')
        with pytest.raises(ValidationError, match="zero"):
            extract_price('0')
            
    def test_extract_price_integer(self) -> None:
        """Test extracting integer prices."""
        assert extract_price('$100') == 100.0
        assert extract_price('€50') == 50.0
        
    def test_extract_price_large_number(self) -> None:
        """Test extracting large prices."""
        assert extract_price('$1,000,000.00') == 1000000.0
        assert extract_price('€999,999.99') == 999999.99
