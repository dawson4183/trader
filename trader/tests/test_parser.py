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

    def test_parse_item_valid_html(self, parser_html_basic: str) -> None:
        """Test that parse_item() parses complete item correctly from valid HTML."""
        result = parse_item(parser_html_basic)
        assert result == {
            'item_name': 'Test Item',
            'price': '$19.99',
            'item_hash': 'abc123xyz'
        }

    def test_parse_item_missing_name(self, parser_html_no_item_name: str) -> None:
        """Test that parse_item() raises ValidationError when .item-name is missing."""
        with pytest.raises(ValidationError, match="Could not find item name element with selector '.item-name'"):
            parse_item(parser_html_no_item_name)

    def test_parse_item_missing_price(self, parser_html_no_price: str) -> None:
        """Test that parse_item() raises ValidationError when .price is missing."""
        with pytest.raises(ValidationError, match="Could not find price element with selector '.price'"):
            parse_item(parser_html_no_price)

    def test_parse_item_missing_hash(self, parser_html_no_data_hash: str) -> None:
        """Test that parse_item() raises ValidationError when data-hash is missing."""
        with pytest.raises(ValidationError, match="Could not find element with 'data-hash' attribute"):
            parse_item(parser_html_no_data_hash)

    def test_parse_item_malformed_html(self) -> None:
        """Test that parse_item() handles BeautifulSoup parsing errors gracefully."""
        # BeautifulSoup handles malformed HTML gracefully, but we test with something
        # that could cause issues - test with HTML that has valid structure but
        # unusual content that might cause parsing issues
        malformed_html = "<not-valid>unclosed tag"
        # BeautifulSoup is lenient and will still parse this without raising,
        # but it won't find our required elements, so it should raise ValidationError
        with pytest.raises(ValidationError):
            parse_item(malformed_html)


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

    # Story 4.0: Additional validate_html_structure tests
    
    def test_validate_html_structure_single_selector(self) -> None:
        """Test validate_html_structure() with single CSS selector - validates single selector."""
        html = """
        <html><body>
            <div data-hash="abc">
                <span class="item-name">Test</span>
                <span class="price">$10</span>
            </div>
        </body></html>
        """
        # Should pass without raising
        validate_html_structure(html)
        # Verify by using select_one to validate single .item-name selector
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        assert soup.select_one('.item-name') is not None

    def test_validate_html_structure_multiple_selectors(self) -> None:
        """Test validate_html_structure() validates all required selectors are present."""
        html = """
        <html><body>
            <div data-hash="abc">
                <span class="item-name">Test</span>
                <span class="price">$10</span>
            </div>
        </body></html>
        """
        # Should pass - all 3 selectors (.item-name, .price, data-hash) are present
        validate_html_structure(html)

    def test_validate_html_structure_partial_missing(self) -> None:
        """Test validate_html_structure() fails when some selectors are missing."""
        # Missing .price but has .item-name and data-hash
        html_missing_price = """
        <html><body>
            <div data-hash="abc">
                <span class="item-name">Test</span>
            </div>
        </body></html>
        """
        with pytest.raises(ValidationError, match="Required element not found: .price"):
            validate_html_structure(html_missing_price)
        
        # Missing .item-name but has .price and data-hash
        html_missing_name = """
        <html><body>
            <div data-hash="abc">
                <span class="price">$10</span>
            </div>
        </body></html>
        """
        with pytest.raises(ValidationError, match="Required element not found: .item-name"):
            validate_html_structure(html_missing_name)
        
        # Missing data-hash but has .item-name and .price
        html_missing_hash = """
        <html><body>
            <div>
                <span class="item-name">Test</span>
                <span class="price">$10</span>
            </div>
        </body></html>
        """
        with pytest.raises(ValidationError, match="Required attribute not found: data-hash"):
            validate_html_structure(html_missing_hash)

    def test_validate_html_structure_nested_selector(self) -> None:
        """Test validate_html_structure() handles nested CSS selectors."""
        html = """
        <html><body>
            <div class="container" data-hash="abc">
                <div class="inner">
                    <h2 class="item-name">Nested Item</h2>
                    <div class="price-wrapper">
                        <span class="price">$25.00</span>
                    </div>
                </div>
            </div>
        </body></html>
        """
        # Should find elements even when nested deeply
        validate_html_structure(html)

    def test_validate_html_structure_empty_html(self) -> None:
        """Test validate_html_structure() raises ValidationError for empty HTML."""
        with pytest.raises(ValidationError, match="HTML content is empty"):
            validate_html_structure("")
        
        # Also test whitespace-only HTML
        with pytest.raises(ValidationError, match="HTML content is empty"):
            validate_html_structure("   \n\t   ")

    def test_validate_html_structure_complex_selectors(self) -> None:
        """Test validate_html_structure() handles attribute selectors like [data-hash]."""
        # Test with data-hash on different element types
        html_div = """
        <html><body>
            <div class="item" data-hash="hash-123">
                <span class="item-name">Item A</span>
                <span class="price">$10</span>
            </div>
        </body></html>
        """
        validate_html_structure(html_div)
        
        html_span = """
        <html><body>
            <span data-hash="hash-456">
                <b class="item-name">Item B</b>
                <i class="price">$20</i>
            </span>
        </body></html>
        """
        validate_html_structure(html_span)
        
        html_custom = """
        <html><body>
            <custom-element data-hash="custom-789">
                <p class="item-name">Item C</p>
                <div class="price">$30</div>
            </custom-element>
        </body></html>
        """
        validate_html_structure(html_custom)
