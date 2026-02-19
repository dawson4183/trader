"""Tests for ItemParser class."""

import pytest

from trader.exceptions import ValidationError
from trader.item_parser import ItemParser


class TestItemParserInit:
    """Test ItemParser initialization."""

    def test_init_with_required_selectors(self):
        """Test init accepts config with required_selectors."""
        config = {'required_selectors': ['.item', '.price']}
        parser = ItemParser(config)
        assert parser.required_selectors == ['.item', '.price']
        assert parser.config == config

    def test_init_missing_required_selectors_raises_error(self):
        """Test init raises ValidationError if required_selectors missing."""
        config = {'other_key': 'value'}
        with pytest.raises(ValidationError) as exc_info:
            ItemParser(config)
        assert 'required_selectors' in str(exc_info.value)

    def test_init_empty_config(self):
        """Test init with empty config raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ItemParser({})
        assert 'required_selectors' in str(exc_info.value)


class TestItemParserParse:
    """Test ItemParser parse method."""

    def test_parse_valid_html_structure(self):
        """Test parse validates HTML structure before parsing."""
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="abc123" data-price="10.99" data-name="Test Item">Test Item</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        items = parser.parse(html)
        assert len(items) == 1
        assert items[0]['item_hash'] == 'abc123'

    def test_parse_invalid_html_structure_raises_error(self):
        """Test parse raises ValidationError for invalid HTML structure."""
        html = """
        <html>
            <body>
                <div class="item">Test Item</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.missing', '.notfound']}
        parser = ItemParser(config)
        with pytest.raises(ValidationError) as exc_info:
            parser.parse(html)
        assert 'Missing required selectors' in str(exc_info.value)

    def test_parse_validates_prices(self):
        """Test parse validates each item's price during extraction."""
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="abc123" data-price="10.99" data-name="Item 1">Item 1</div>
                <div class="item" data-item-hash="def456" data-price="20.00" data-name="Item 2">Item 2</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        items = parser.parse(html)
        assert len(items) == 2
        assert items[0]['price'] == 10.99
        assert items[1]['price'] == 20.0

    def test_parse_invalid_price_raises_error(self):
        """Test parse raises ValidationError if any price is invalid."""
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="abc123" data-price="-5.00" data-name="Invalid Item">Invalid Item</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        with pytest.raises(ValidationError) as exc_info:
            parser.parse(html)
        assert 'Price must be greater than 0' in str(exc_info.value)

    def test_parse_zero_price_raises_error(self):
        """Test parse raises ValidationError if price is zero."""
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="abc123" data-price="0" data-name="Zero Price Item">Zero Price Item</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        with pytest.raises(ValidationError) as exc_info:
            parser.parse(html)
        assert 'Price must be greater than 0' in str(exc_info.value)

    def test_parse_deduplicates_items(self):
        """Test parse deduplicates items after extraction."""
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="abc123" data-price="10.99" data-name="Item 1">Item 1</div>
                <div class="item" data-item-hash="abc123" data-price="10.99" data-name="Duplicate">Duplicate</div>
                <div class="item" data-item-hash="def456" data-price="20.00" data-name="Item 2">Item 2</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        items = parser.parse(html)
        assert len(items) == 2
        assert items[0]['name'] == 'Item 1'  # First occurrence kept

    def test_parse_empty_html(self):
        """Test parse with no matching items returns empty list."""
        html = "<html><body></body></html>"
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        with pytest.raises(ValidationError) as exc_info:
            parser.parse(html)
        assert 'Missing required selectors' in str(exc_info.value)

    def test_parse_preserves_item_order(self):
        """Test parse preserves order of unique items."""
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="hash1" data-price="10.00" data-name="First">First</div>
                <div class="item" data-item-hash="hash2" data-price="20.00" data-name="Second">Second</div>
                <div class="item" data-item-hash="hash3" data-price="30.00" data-name="Third">Third</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        items = parser.parse(html)
        assert len(items) == 3
        assert items[0]['item_hash'] == 'hash1'
        assert items[1]['item_hash'] == 'hash2'
        assert items[2]['item_hash'] == 'hash3'

    def test_deduplicate_items_missing_hash_raises_error(self):
        """Test that deduplicate_items raises ValidationError for missing item_hash."""
        # This tests the underlying validator function behavior through ItemParser extraction
        # When we have items with explicit item_hash via data-item-hash attribute
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="abc123" data-price="10.99">Valid Item</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        # This should work fine - hash is provided
        items = parser.parse(html)
        assert len(items) == 1
        
        # Verify deduplicate_items from validators works with our items
        from trader.validators import deduplicate_items
        with pytest.raises(ValidationError) as exc_info:
            deduplicate_items([{'name': 'No Hash', 'price': 10.00}])
        assert 'item_hash' in str(exc_info.value)

    def test_parse_multiple_required_selectors(self):
        """Test parse validates multiple required selectors."""
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="abc123" data-price="10.99" data-name="Item">Item</div>
                <div class="price-tag">Price Info</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item', '.price-tag']}
        parser = ItemParser(config)
        items = parser.parse(html)
        assert len(items) >= 1

    def test_parse_extract_item_with_text_name(self):
        """Test parse extracts item with name from text content."""
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="abc123" data-price="15.50">Text Item Name</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        items = parser.parse(html)
        assert len(items) == 1
        assert items[0]['name'] == 'Text Item Name'
        assert items[0]['price'] == 15.50

    def test_parse_extract_item_with_data_name(self):
        """Test parse extracts item with name from data attribute."""
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="abc123" data-price="25.00" data-name="Data Item">Fallback Name</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        items = parser.parse(html)
        assert len(items) == 1
        assert items[0]['name'] == 'Data Item'  # data-name takes precedence
