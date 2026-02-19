"""Tests for trader/parser.py module."""
import pytest
from trader.parser import parse_item, validate_html_structure
from trader.exceptions import ValidationError


class TestParseItem:
    """Test cases for parse_item() function."""
    
    def test_parse_item_extracts_item_name(self, parser_html_basic: str) -> None:
        """Test that parse_item() extracts item_name from .item-name selector."""
        result = parse_item(parser_html_basic)
        assert result['item_name'] == 'Test Item'
    
    def test_parse_item_extracts_price(self, parser_html_basic: str) -> None:
        """Test that parse_item() extracts price from .price selector."""
        result = parse_item(parser_html_basic)
        assert result['price'] == '$19.99'
    
    def test_parse_item_extracts_item_hash(self, parser_html_basic: str) -> None:
        """Test that parse_item() extracts item_hash from data-hash attribute."""
        result = parse_item(parser_html_basic)
        assert result['item_hash'] == 'abc123xyz'
    
    def test_parse_item_returns_dict_with_all_fields(self, parser_html_basic: str) -> None:
        """Test that parse_item() returns dict with all required fields."""
        result = parse_item(parser_html_basic)
        assert isinstance(result, dict)
        assert 'item_name' in result
        assert 'price' in result
        assert 'item_hash' in result
    
    def test_parse_item_raises_validation_error_for_empty_html(self, parser_html_empty: str) -> None:
        """Test that parse_item() raises ValidationError for empty HTML."""
        with pytest.raises(ValidationError, match="HTML content is empty"):
            parse_item(parser_html_empty)
    
    def test_parse_item_raises_validation_error_for_whitespace_html(self, parser_html_whitespace: str) -> None:
        """Test that parse_item() raises ValidationError for whitespace-only HTML."""
        with pytest.raises(ValidationError, match="HTML content is empty"):
            parse_item(parser_html_whitespace)
    
    def test_parse_item_raises_validation_error_for_missing_item_name(self, parser_html_no_item_name: str) -> None:
        """Test that parse_item() raises ValidationError when .item-name is missing."""
        with pytest.raises(ValidationError, match="Could not find item name element with selector '.item-name'"):
            parse_item(parser_html_no_item_name)
    
    def test_parse_item_raises_validation_error_for_missing_price(self, parser_html_no_price: str) -> None:
        """Test that parse_item() raises ValidationError when .price is missing."""
        with pytest.raises(ValidationError, match="Could not find price element with selector '.price'"):
            parse_item(parser_html_no_price)
    
    def test_parse_item_raises_validation_error_for_missing_data_hash(self, parser_html_no_data_hash: str) -> None:
        """Test that parse_item() raises ValidationError when data-hash is missing."""
        with pytest.raises(ValidationError, match="Could not find element with 'data-hash' attribute"):
            parse_item(parser_html_no_data_hash)
    
    def test_parse_item_raises_validation_error_for_empty_data_hash(self, parser_html_empty_hash: str) -> None:
        """Test that parse_item() raises ValidationError when data-hash is empty."""
        with pytest.raises(ValidationError, match="Element with 'data-hash' attribute has empty value"):
            parse_item(parser_html_empty_hash)
    
    def test_parse_item_extracts_from_different_element_with_data_hash(self) -> None:
        """Test that parse_item() can find data-hash on any element."""
        html = """
        <html>
            <body>
                <div data-hash="different-hash">
                    <h1 class="item-name">Another Item</h1>
                    <span class="price">€25.00</span>
                </div>
            </body>
        </html>
        """
        result = parse_item(html)
        assert result['item_hash'] == 'different-hash'
        assert result['item_name'] == 'Another Item'
        assert result['price'] == '€25.00'


class TestValidateHtmlStructure:
    """Test cases for validate_html_structure() function."""
    
    def test_validate_html_structure_passes_for_valid_html(self, parser_html_basic: str) -> None:
        """Test that validate_html_structure() passes for valid HTML."""
        # Should not raise any exception
        validate_html_structure(parser_html_basic)
    
    def test_validate_html_structure_raises_for_empty_html(self, parser_html_empty: str) -> None:
        """Test that validate_html_structure() raises ValidationError for empty HTML."""
        with pytest.raises(ValidationError, match="HTML content is empty"):
            validate_html_structure(parser_html_empty)
    
    def test_validate_html_structure_raises_for_missing_item_name(self, parser_html_no_item_name: str) -> None:
        """Test that validate_html_structure() raises when .item-name is missing."""
        with pytest.raises(ValidationError, match="Required element not found: .item-name"):
            validate_html_structure(parser_html_no_item_name)
    
    def test_validate_html_structure_raises_for_missing_price(self, parser_html_no_price: str) -> None:
        """Test that validate_html_structure() raises when .price is missing."""
        with pytest.raises(ValidationError, match="Required element not found: .price"):
            validate_html_structure(parser_html_no_price)
    
    def test_validate_html_structure_raises_for_missing_data_hash(self, parser_html_no_data_hash: str) -> None:
        """Test that validate_html_structure() raises when data-hash is missing."""
        with pytest.raises(ValidationError, match="Required attribute not found: data-hash"):
            validate_html_structure(parser_html_no_data_hash)
    
    def test_validate_html_structure_strips_text_content(self) -> None:
        """Test that parse_item() strips whitespace from extracted text."""
        html = """
        <html>
            <body>
                <div class="item" data-hash="hash123">
                    <h1 class="item-name">   Item With Whitespace   </h1>
                    <span class="price">  $100.00  </span>
                </div>
            </body>
        </html>
        """
        result = parse_item(html)
        assert result['item_name'] == 'Item With Whitespace'
        assert result['price'] == '$100.00'
        assert result['item_hash'] == 'hash123'
