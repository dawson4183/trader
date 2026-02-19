"""Tests for HTML parser with mocked fixtures."""
import pytest
from trader.item_parser import parse_item, validate_html_structure
from trader.exceptions import ValidationError


# Mock HTML fixtures
SIMPLE_ITEM_HTML = """
<html>
<body>
    <div class="product">
        <h1 class="title">Vintage Camera</h1>
        <span class="price">$199.99</span>
        <p class="description">A beautiful vintage camera from 1960s</p>
    </div>
</body>
</html>
"""

COMPLEX_ITEM_HTML = """
<html>
<body>
    <article data-item-id="12345">
        <header>
            <h2 class="product-name">Leather Jacket</h2>
            <div class="pricing">
                <span class="current-price">€249.00</span>
                <span class="old-price">€300.00</span>
            </div>
        </header>
        <section class="details">
            <p class="condition">Excellent condition</p>
            <span class="location">Berlin, Germany</span>
        </section>
    </article>
</body>
</html>
"""

MISSING_SELECTOR_HTML = """
<html>
<body>
    <div class="item">
        <span class="name">Only Name Available</span>
    </div>
</body>
</html>
"""

EMPTY_HTML = ""

MALFORMED_HTML = "<div><span>Unclosed tags"


class TestParseItem:
    """Test parse_item() function with various HTML fixtures."""

    def test_parse_simple_item(self):
        """Parse a simple item with basic selectors."""
        selectors = {
            'title': '.title',
            'price': '.price',
            'description': '.description'
        }
        
        result = parse_item(SIMPLE_ITEM_HTML, selectors)
        
        assert result['title'] == 'Vintage Camera'
        assert result['price'] == '$199.99'
        assert result['description'] == 'A beautiful vintage camera from 1960s'
        assert 'item_hash' in result

    def test_parse_complex_nested_item(self):
        """Parse item with complex nested structure."""
        selectors = {
            'name': '.product-name',
            'price': '.current-price',
            'condition': '.condition',
            'location': '.location'
        }
        
        result = parse_item(COMPLEX_ITEM_HTML, selectors)
        
        assert result['name'] == 'Leather Jacket'
        assert result['price'] == '€249.00'
        assert result['condition'] == 'Excellent condition'
        assert result['location'] == 'Berlin, Germany'
        assert 'item_hash' in result

    def test_parse_missing_selector_raises_error(self):
        """Should raise ValidationError when selector not found."""
        selectors = {
            'name': '.name',
            'price': '.price',  # Missing in HTML
            'description': '.description'  # Missing in HTML
        }
        
        with pytest.raises(ValidationError) as exc_info:
            parse_item(MISSING_SELECTOR_HTML, selectors)
        
        assert 'price' in str(exc_info.value) or 'description' in str(exc_info.value)

    def test_parse_empty_html_raises_error(self):
        """Should raise ValidationError for empty HTML."""
        selectors = {'title': 'h1'}
        
        with pytest.raises(ValidationError):
            parse_item(EMPTY_HTML, selectors)

    def test_parse_malformed_html(self):
        """Should handle malformed HTML gracefully."""
        selectors = {'content': 'span'}
        
        result = parse_item(MALFORMED_HTML, selectors)
        
        assert 'content' in result
        assert 'item_hash' in result

    def test_parse_item_hash_consistency(self):
        """Same content should produce same hash."""
        selectors = {'title': '.title'}
        
        result1 = parse_item(SIMPLE_ITEM_HTML, selectors)
        result2 = parse_item(SIMPLE_ITEM_HTML, selectors)
        
        assert result1['item_hash'] == result2['item_hash']

    def test_parse_different_content_different_hash(self):
        """Different content should produce different hashes."""
        html1 = '<div class="title">Item A</div>'
        html2 = '<div class="title">Item B</div>'
        selectors = {'title': '.title'}
        
        result1 = parse_item(html1, selectors)
        result2 = parse_item(html2, selectors)
        
        assert result1['item_hash'] != result2['item_hash']


class TestValidateHtmlStructure:
    """Test validate_html_structure() with mocked fixtures."""

    def test_valid_single_selector(self):
        """Single required selector present."""
        html = '<div class="product"><span class="price">$10</span></div>'
        validate_html_structure(html, ['.price'])  # Should not raise

    def test_valid_multiple_selectors(self):
        """All required selectors present."""
        html = '<div class="product"><h1>Title</h1><span class="price">$10</span></div>'
        validate_html_structure(html, ['h1', '.price'])  # Should not raise

    def test_missing_single_selector(self):
        """Single required selector missing."""
        html = '<div class="product"><span class="name">Item</span></div>'
        
        with pytest.raises(ValidationError) as exc_info:
            validate_html_structure(html, ['.price'])
        
        assert '.price' in str(exc_info.value)

    def test_missing_multiple_selectors(self):
        """Multiple required selectors missing."""
        html = '<div class="product">No relevant content</div>'
        
        with pytest.raises(ValidationError) as exc_info:
            validate_html_structure(html, ['.title', '.price', '.description'])
        
        error_msg = str(exc_info.value)
        assert '.title' in error_msg

    def test_partial_missing_selectors(self):
        """Some selectors present, some missing."""
        html = '<div><h1 class="title">Title</h1></div>'
        
        with pytest.raises(ValidationError) as exc_info:
            validate_html_structure(html, ['.title', '.price', '.image'])
        
        assert '.price' in str(exc_info.value) or '.image' in str(exc_info.value)

    def test_empty_selector_list(self):
        """Empty selector list should always pass."""
        html = '<div>Anything</div>'
        validate_html_structure(html, [])  # Should not raise

    def test_nested_selectors(self):
        """Nested CSS selectors."""
        html = '<div class="container"><article><span class="price">$5</span></article></div>'
        validate_html_structure(html, ['.container article .price'])  # Should not raise

    def test_id_selectors(self):
        """ID-based CSS selectors."""
        html = '<div id="main"><p id="description">Text</p></div>'
        validate_html_structure(html, ['#main', '#description'])  # Should not raise

    def test_attribute_selectors(self):
        """Attribute-based CSS selectors."""
        html = '<div data-item="123"><span class="title">Item</span></div>'
        validate_html_structure(html, ['[data-item]', '.title'])  # Should not raise
