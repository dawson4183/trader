"""Integration tests for the trader module.

This module provides end-to-end tests covering the full parsing workflow,
including HTML validation, price validation, deduplication, and error handling.
"""

from typing import Any, Dict, List, cast

import pytest
from trader.item_parser import validate_html_structure, validate_price, deduplicate_items
from trader.exceptions import ValidationError


class TestIntegrationWorkflow:
    """End-to-end integration tests for the full parsing workflow."""

    def test_full_parsing_workflow_with_valid_html(self) -> None:
        """Test complete workflow with valid HTML and valid items.
        
        This test validates HTML structure, parsing items, validating prices,
        and deduplicating the final list.
        """
        # Sample HTML with items
        html = """
        <html>
            <body>
                <div class="item" data-id="1">
                    <span class="name">Sword of Truth</span>
                    <span class="price">99.99</span>
                </div>
                <div class="item" data-id="2">
                    <span class="name">Shield of Valor</span>
                    <span class="price">49.99</span>
                </div>
            </body>
        </html>
        """
        
        # Step 1: Validate HTML structure
        required_selectors = ["div.item", "span.name", "span.price"]
        validate_html_structure(html, required_selectors)
        
        # Step 2: Simulate parsed items (as if from HTML)
        items: List[Dict[str, Any]] = [
            {"item_hash": "abc123", "name": "Sword of Truth", "price": 99.99},
            {"item_hash": "def456", "name": "Shield of Valor", "price": 49.99},
        ]
        
        # Step 3: Validate prices for each item
        for item in items:
            validate_price(cast(float, item["price"]))
        
        # Step 4: Deduplicate items
        unique_items = deduplicate_items(items)
        
        # Assertions
        assert len(unique_items) == 2
        assert unique_items[0]["name"] == "Sword of Truth"
        assert unique_items[1]["name"] == "Shield of Valor"

    def test_error_handling_invalid_html_missing_selector(self) -> None:
        """Test error handling when HTML is missing required selectors."""
        html = """
        <html>
            <body>
                <div class="item">Example</div>
            </body>
        </html>
        """
        
        required_selectors = ["div.item", "span.price"]  # span.price doesn't exist
        
        with pytest.raises(ValidationError) as exc_info:
            validate_html_structure(html, required_selectors)
        
        assert "span.price" in str(exc_info.value)
        assert "Required CSS selector not found" in str(exc_info.value)

    def test_error_handling_invalid_html_empty(self) -> None:
        """Test error handling with empty HTML."""
        html = ""
        
        required_selectors = ["div.item"]
        
        with pytest.raises(ValidationError) as exc_info:
            validate_html_structure(html, required_selectors)
        
        assert "div.item" in str(exc_info.value)

    def test_error_handling_invalid_price_zero(self) -> None:
        """Test error handling when price is zero."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price(0)
        
        assert "greater than 0" in str(exc_info.value)
        assert "0" in str(exc_info.value)

    def test_error_handling_invalid_price_negative(self) -> None:
        """Test error handling when price is negative."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price(-10.5)
        
        assert "greater than 0" in str(exc_info.value)
        assert "-10.5" in str(exc_info.value)

    def test_deduplication_in_full_workflow(self) -> None:
        """Test deduplication when processing items through full workflow."""
        # HTML with items that will have duplicates
        html = """
        <html>
            <body>
                <div class="item">
                    <span class="name">Magic Potion</span>
                    <span class="price">15.00</span>
                </div>
            </body>
        </html>
        """
        
        # Validate HTML first
        validate_html_structure(html, ["div.item"])
        
        # Simulate items with duplicates (as if parsed from multiple pages)
        items: List[Dict[str, Any]] = [
            {"item_hash": "hash001", "name": "Magic Potion", "price": 15.00},
            {"item_hash": "hash002", "name": "Iron Sword", "price": 25.00},
            {"item_hash": "hash001", "name": "Magic Potion (duplicate)", "price": 15.00},  # Duplicate
            {"item_hash": "hash003", "name": "Leather Armor", "price": 35.00},
            {"item_hash": "hash002", "name": "Iron Sword (duplicate)", "price": 25.00},  # Duplicate
        ]
        
        # Validate all prices
        for item in items:
            validate_price(cast(float, item["price"]))
        
        # Deduplicate
        unique_items = deduplicate_items(items)
        
        # Should have 3 unique items
        assert len(unique_items) == 3
        
        # First occurrences should be kept
        assert unique_items[0]["name"] == "Magic Potion"
        assert unique_items[1]["name"] == "Iron Sword"
        assert unique_items[2]["name"] == "Leather Armor"
        
        # Verify hashes are unique
        hashes = {item["item_hash"] for item in unique_items}
        assert len(hashes) == 3

    def test_deduplication_error_missing_item_hash(self) -> None:
        """Test error handling when item is missing item_hash field."""
        items = [
            {"item_hash": "hash001", "name": "Valid Item"},
            {"name": "Invalid Item - No Hash"},  # Missing item_hash
        ]
        
        with pytest.raises(ValidationError) as exc_info:
            deduplicate_items(items)
        
        assert "item_hash" in str(exc_info.value)
        assert "missing" in str(exc_info.value).lower()

    def test_complete_workflow_with_edge_cases(self) -> None:
        """Test complete workflow with various edge cases."""
        # Complex HTML structure
        html = """
        <html>
            <head><title>Item Shop</title></head>
            <body>
                <div class="shop">
                    <div class="item" id="item1">
                        <h2 class="name">Rare Gem</h2>
                        <span class="price">999.99</span>
                        <span class="category">Gemstones</span>
                    </div>
                    <div class="item" id="item2">
                        <h2 class="name">Common Stone</h2>
                        <span class="price">0.01</span>
                        <span class="category">Rocks</span>
                    </div>
                </div>
            </body>
        </html>
        """
        
        # Step 1: Validate HTML
        required_selectors = [".shop", ".item", ".name", ".price", ".category"]
        validate_html_structure(html, required_selectors)
        
        # Step 2: Process items
        items: List[Dict[str, Any]] = [
            {"item_hash": "gem001", "name": "Rare Gem", "price": 999.99, "category": "Gemstones"},
            {"item_hash": "stone001", "name": "Common Stone", "price": 0.01, "category": "Rocks"},
        ]
        
        # Step 3: Validate prices (edge case: very small price)
        for item in items:
            validate_price(cast(float, item["price"]))
        
        # Step 4: Deduplicate (no duplicates in this case)
        unique_items = deduplicate_items(items)
        
        assert len(unique_items) == 2
        assert unique_items[0]["price"] == 999.99
        assert unique_items[1]["price"] == 0.01

    def test_integration_empty_items_list(self) -> None:
        """Test workflow with empty items list."""
        result = deduplicate_items([])
        assert result == []
    
    def test_integration_multiple_validation_errors(self) -> None:
        """Test handling multiple validation errors in sequence."""
        # First error: invalid HTML
        html = "<html><body></body></html>"
        
        with pytest.raises(ValidationError):
            validate_html_structure(html, [".item"])
        
        # After error, system should still work for valid inputs
        validate_html_structure(
            "<div class='item'></div>", 
            [".item"]
        )
        
        # Price validation
        validate_price(100.0)
        
        with pytest.raises(ValidationError):
            validate_price(-50.0)
        
        # Deduplication
        items = [{"item_hash": "hash001", "name": "Test"}]
        result = deduplicate_items(items)
        assert len(result) == 1
