"""Tests for trader validators."""

from typing import Any, Dict, List

import pytest

from trader.exceptions import ValidationError
from trader.validators import deduplicate_items, validate_html_structure, validate_price


class TestValidateHtmlStructure:
    """Test cases for validate_html_structure function."""

    def test_returns_true_when_all_selectors_exist(self) -> None:
        """Return True when all required selectors exist in HTML."""
        html = """
        <html>
            <body>
                <div class="item-name">Test Item</div>
                <span class="price">$10.00</span>
            </body>
        </html>
        """
        required_selectors = ['.item-name', '.price']

        result = validate_html_structure(html, required_selectors)

        assert result is True

    def test_raises_error_when_single_selector_missing(self) -> None:
        """Raise ValidationError when a single selector is missing."""
        html = """
        <html>
            <body>
                <div class="item-name">Test Item</div>
            </body>
        </html>
        """
        required_selectors = ['.item-name', '.price']

        with pytest.raises(ValidationError) as exc_info:
            validate_html_structure(html, required_selectors)

        assert 'Missing required selectors: .price' in str(exc_info.value)

    def test_raises_error_with_multiple_missing_selectors(self) -> None:
        """Raise ValidationError listing all missing selectors."""
        html = """
        <html>
            <body>
                <div class="item-name">Test Item>/div>
            </body>
        </html>
        """
        required_selectors = ['.nonexistent', '.missing']

        with pytest.raises(ValidationError) as exc_info:
            validate_html_structure(html, required_selectors)

        error_message = str(exc_info.value)
        assert 'Missing required selectors:' in error_message
        assert '.nonexistent' in error_message
        assert '.missing' in error_message

    def test_raises_error_with_partial_missing_selectors(self) -> None:
        """Raise ValidationError when some selectors are found but others missing."""
        html = """
        <div class="container">
            <h1 class="title">Title</h1>
        </div>
        """
        required_selectors = ['.container', '.title', '.description']

        with pytest.raises(ValidationError) as exc_info:
            validate_html_structure(html, required_selectors)

        error_message = str(exc_info.value)
        assert 'Missing required selectors: .description' == error_message

    def test_empty_selectors_list_returns_true(self) -> None:
        """Return True when no selectors are required."""
        html = "<html><body></body></html>"
        required_selectors: list[str] = []

        result = validate_html_structure(html, required_selectors)

        assert result is True

    def test_complex_css_selectors(self) -> None:
        """Handle complex CSS selectors like id, tag combinations, nested selectors."""
        html = """
        <html>
            <body>
                <div id="main">
                    <p class="content">Text</p>
                </div>
            </body>
        </html>
        """
        required_selectors = ['#main', 'div p', 'p.content']

        result = validate_html_structure(html, required_selectors)

        assert result is True

    def test_malformed_html_still_parses(self) -> None:
        """Handle malformed HTML gracefully with BeautifulSoup."""
        html = "<div class='item'><span class='price'>$5</div>"
        required_selectors = ['.item', '.price']

        result = validate_html_structure(html, required_selectors)

        assert result is True

    def test_error_message_format_matches_requirement(self) -> None:
        """Ensure error message format matches 'Missing required selectors: selector1, selector2'."""
        html = "<html></div>"
        required_selectors = ['.first', '.second']

        with pytest.raises(ValidationError) as exc_info:
            validate_html_structure(html, required_selectors)

        assert str(exc_info.value) == 'Missing required selectors: .first, .second'


class TestValidatePrice:
    """Test cases for validate_price function."""

    def test_returns_true_for_positive_integer(self) -> None:
        """Return True for valid positive integer price."""
        result = validate_price(10)

        assert result is True

    def test_returns_true_for_positive_float(self) -> None:
        """Return True for valid positive float price."""
        result = validate_price(10.99)

        assert result is True

    def test_raises_error_for_zero(self) -> None:
        """Raise ValidationError for zero price."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price(0)

        assert 'Price must be greater than 0, got: 0' == str(exc_info.value)

    def test_raises_error_for_negative_integer(self) -> None:
        """Raise ValidationError for negative integer price."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price(-5)

        assert 'Price must be greater than 0, got: -5' == str(exc_info.value)

    def test_raises_error_for_negative_float(self) -> None:
        """Raise ValidationError for negative float price."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price(-0.01)

        assert 'Price must be greater than 0, got: -0.01' == str(exc_info.value)

    def test_raises_error_for_none(self) -> None:
        """Raise ValidationError for None price."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price(None)  # type: ignore[arg-type]

        assert 'Price must be numeric' == str(exc_info.value)

    def test_raises_error_for_string(self) -> None:
        """Raise ValidationError for string price."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price("10.99")  # type: ignore[arg-type]

        assert 'Price must be numeric' == str(exc_info.value)

    def test_raises_error_for_list(self) -> None:
        """Raise ValidationError for list price."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price([10, 20])  # type: ignore[arg-type]

        assert 'Price must be numeric' == str(exc_info.value)

    def test_handles_small_positive_float(self) -> None:
        """Return True for small positive float price."""
        result = validate_price(0.01)

        assert result is True

    def test_error_message_matches_format_for_zero(self) -> None:
        """Ensure error message format matches 'Price must be greater than 0, got: {price}'."""
        with pytest.raises(ValidationError) as exc_info:
            validate_price(0)

        assert str(exc_info.value) == 'Price must be greater than 0, got: 0'


class TestDeduplicateItems:
    """Test cases for deduplicate_items function."""

    def test_returns_empty_list_for_empty_input(self) -> None:
        """Return empty list when input is empty."""
        items: List[Dict[str, Any]] = []

        result = deduplicate_items(items)

        assert result == []

    def test_returns_same_list_for_all_unique_items(self) -> None:
        """Return same list when all items have unique item_hash."""
        items = [
            {'item_hash': 'abc123', 'name': 'Item 1'},
            {'item_hash': 'def456', 'name': 'Item 2'},
            {'item_hash': 'ghi789', 'name': 'Item 3'},
        ]

        result = deduplicate_items(items)

        assert result == items

    def test_removes_duplicate_items_keeps_first(self) -> None:
        """Remove duplicates and keep first occurrence."""
        items = [
            {'item_hash': 'abc123', 'name': 'First'},
            {'item_hash': 'def456', 'name': 'Item 2'},
            {'item_hash': 'abc123', 'name': 'Duplicate'},
        ]

        result = deduplicate_items(items)

        assert len(result) == 2
        assert result[0]['name'] == 'First'
        assert result[1]['name'] == 'Item 2'

    def test_preserves_order_of_unique_items(self) -> None:
        """Preserve original order for unique items."""
        items = [
            {'item_hash': 'hash3', 'name': 'Third'},
            {'item_hash': 'hash1', 'name': 'First'},
            {'item_hash': 'hash2', 'name': 'Second'},
        ]

        result = deduplicate_items(items)

        assert result[0]['name'] == 'Third'
        assert result[1]['name'] == 'First'
        assert result[2]['name'] == 'Second'

    def test_removes_multiple_duplicates(self) -> None:
        """Remove multiple duplicate items correctly."""
        items = [
            {'item_hash': 'abc123', 'name': 'First'},
            {'item_hash': 'abc123', 'name': 'Duplicate 1'},
            {'item_hash': 'def456', 'name': 'Unique'},
            {'item_hash': 'abc123', 'name': 'Duplicate 2'},
            {'item_hash': 'def456', 'name': 'Duplicate 3'},
        ]

        result = deduplicate_items(items)

        assert len(result) == 2
        assert result[0]['name'] == 'First'
        assert result[1]['name'] == 'Unique'

    def test_raises_error_when_item_missing_item_hash(self) -> None:
        """Raise ValidationError when item is missing item_hash key."""
        items = [
            {'item_hash': 'abc123', 'name': 'Valid'},
            {'name': 'Invalid'},  # Missing item_hash
        ]

        with pytest.raises(ValidationError) as exc_info:
            deduplicate_items(items)

        error_message = str(exc_info.value)
        assert 'Item missing item_hash:' in error_message

    def test_raises_error_for_item_with_none_hash(self) -> None:
        """Handle item_hash with None value as valid (not duplicate of another None)."""
        items = [
            {'item_hash': None, 'name': 'First'},
            {'item_hash': None, 'name': 'Second'},
        ]

        result = deduplicate_items(items)

        assert len(result) == 1
        assert result[0]['name'] == 'First'

    def test_handles_various_types_for_item_hash(self) -> None:
        """Handle various hashable types for item_hash."""
        items = [
            {'item_hash': 'string', 'name': 'String'},
            {'item_hash': 123, 'name': 'Integer'},
            {'item_hash': 45.67, 'name': 'Float'},
        ]

        result = deduplicate_items(items)

        assert len(result) == 3

    def test_returns_new_list_does_not_modify_original(self) -> None:
        """Return a new list without modifying the original."""
        items = [
            {'item_hash': 'abc123', 'name': 'First'},
            {'item_hash': 'abc123', 'name': 'Duplicate'},
        ]
        original_length = len(items)

        result = deduplicate_items(items)

        assert len(result) == 1
        assert len(items) == original_length  # Original unchanged
        assert result is not items  # New list returned
