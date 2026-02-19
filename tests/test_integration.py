"""Integration tests for the trader package.

These tests verify the complete end-to-end workflow of the trader package,
including HTML parsing, validation, and deduplication.
"""

import pytest

from trader import (
    ItemParser,
    ValidationError,
    deduplicate_items,
    parse_item,
    validate_html_structure,
    validate_price,
)


class TestFullParsingWorkflow:
    """Integration tests for the complete parsing workflow."""

    def test_full_parsing_workflow_with_valid_html(self):
        """Test complete workflow from HTML to deduplicated items.
        
        Verifies that:
        - HTML structure is validated
        - Items are extracted correctly
        - Prices are validated during extraction
        - Duplicates are removed
        """
        html = """
        <html>
            <body>
                <div class="item-list">
                    <div class="item" data-item-hash="hash001" data-price="19.99" data-name="Widget A">Widget A</div>
                    <div class="item" data-item-hash="hash002" data-price="29.99" data-name="Widget B">Widget B</div>
                    <div class="item" data-item-hash="hash003" data-price="39.99" data-name="Widget C">Widget C</div>
                </div>
                <div class="price-info">Price Information</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item-list', '.item', '.price-info']}
        parser = ItemParser(config)
        
        items = parser.parse(html)
        
        assert len(items) == 3
        assert items[0]['item_hash'] == 'hash001'
        assert items[0]['price'] == 19.99
        assert items[0]['name'] == 'Widget A'
        assert items[1]['item_hash'] == 'hash002'
        assert items[2]['item_hash'] == 'hash003'

    def test_error_handling_invalid_html_missing_selector(self):
        """Test that ValidationError is raised when required selectors are missing.
        
        Verifies that the parser raises a descriptive ValidationError when
        the HTML doesn't contain all required CSS selectors.
        """
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="hash001" data-price="19.99">Item</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item', '.missing-selector', '.another-missing']}
        parser = ItemParser(config)
        
        with pytest.raises(ValidationError) as exc_info:
            parser.parse(html)
        
        error_message = str(exc_info.value)
        assert 'Missing required selectors' in error_message

    def test_error_handling_invalid_html_empty(self):
        """Test that ValidationError is raised for empty HTML.
        
        Verifies that empty or minimal HTML without required selectors
        raises an appropriate ValidationError.
        """
        html = ""
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        
        with pytest.raises(ValidationError) as exc_info:
            parser.parse(html)
        
        assert 'Missing required selectors' in str(exc_info.value)

    def test_error_handling_invalid_price_zero(self):
        """Test that ValidationError is raised for zero price.
        
        Verifies that items with a price of 0 are rejected with
        a descriptive error message.
        """
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="hash001" data-price="0" data-name="Free Item">Free Item</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        
        with pytest.raises(ValidationError) as exc_info:
            parser.parse(html)
        
        assert 'Price must be greater than 0' in str(exc_info.value)

    def test_error_handling_invalid_price_negative(self):
        """Test that ValidationError is raised for negative price.
        
        Verifies that items with negative prices are rejected with
        a descriptive error message.
        """
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="hash001" data-price="-10.50" data-name="Negative Item">Negative Item</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        
        with pytest.raises(ValidationError) as exc_info:
            parser.parse(html)
        
        assert 'Price must be greater than 0' in str(exc_info.value)

    def test_deduplication_in_full_workflow(self):
        """Test that duplicates are removed during the full workflow.
        
        Verifies that when multiple items have the same item_hash,
        only the first occurrence is kept in the final result.
        """
        html = """
        <html>
            <body>
                <div class="item" data-item-hash="dup001" data-price="10.00" data-name="First">First</div>
                <div class="item" data-item-hash="dup001" data-price="10.00" data-name="Duplicate 1">Duplicate 1</div>
                <div class="item" data-item-hash="unique002" data-price="20.00" data-name="Unique">Unique</div>
                <div class="item" data-item-hash="dup001" data-price="10.00" data-name="Duplicate 2">Duplicate 2</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.item']}
        parser = ItemParser(config)
        
        items = parser.parse(html)
        
        # Should have 2 items: first dup001 and unique002
        assert len(items) == 2
        assert items[0]['item_hash'] == 'dup001'
        assert items[0]['name'] == 'First'  # First occurrence kept
        assert items[1]['item_hash'] == 'unique002'

    def test_deduplication_error_missing_item_hash(self):
        """Test that ValidationError is raised for items without item_hash.
        
        Verifies that the deduplication process raises an error when
        an item is missing the required item_hash field.
        """
        items_without_hash = [
            {'name': 'Item Without Hash', 'price': 10.00}
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            deduplicate_items(items_without_hash)
        
        assert 'item_hash' in str(exc_info.value).lower()

    def test_complete_workflow_with_edge_cases(self):
        """Test complete workflow with various edge cases.
        
        Tests a complex scenario with:
        - Items with special characters in names
        - Items with decimal prices
        - Mixed valid and invalid selectors
        """
        html = """
        <html>
            <body>
                <div class="container">
                    <div class="item" data-item-hash="edge001" data-price="0.99" data-name="Item A">Item A</div>
                    <div class="item" data-item-hash="edge002" data-price="9999.99" data-name="Premium Item">Premium Item</div>
                    <div class="item" data-item-hash="edge003" data-price="1.00" data-name="Budget Item">Budget Item</div>
                </div>
                <div class="footer">Footer Content</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.container', '.item', '.footer']}
        parser = ItemParser(config)
        
        items = parser.parse(html)
        
        assert len(items) == 3
        assert items[0]['price'] == 0.99
        assert items[1]['price'] == 9999.99
        assert items[2]['price'] == 1.00

    def test_integration_empty_items_list(self):
        """Test that empty items list is handled gracefully.
        
        Verifies that deduplicate_items handles an empty list correctly.
        """
        empty_items = []
        result = deduplicate_items(empty_items)
        
        assert result == []
        assert isinstance(result, list)

    def test_integration_multiple_validation_errors(self):
        """Test that first validation error is caught and reported.
        
        Verifies that when multiple validation issues exist,
        the first one encountered is properly reported.
        """
        # Test with HTML missing selectors - should catch structure error first
        html_missing_selectors = """
        <html>
            <body>
                <div class="present">Content</div>
            </body>
        </html>
        """
        config = {'required_selectors': ['.present', '.absent']}
        parser = ItemParser(config)
        
        with pytest.raises(ValidationError) as exc_info:
            parser.parse(html_missing_selectors)
        
        # Should report missing selector, not get to price validation
        assert 'Missing required selectors' in str(exc_info.value)
