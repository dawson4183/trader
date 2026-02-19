import pytest
from trader.item_parser import validate_html_structure, validate_price, deduplicate_items
from trader.exceptions import ValidationError


def test_validate_html_structure_valid():
    html = "<html><body><div class='item'>Test</div></body></html>"
    validate_html_structure(html, ["div.item"])  # Should not raise


def test_validate_html_structure_missing_selector():
    html = "<html><body><div class='item'>Test</div></body></html>"
    with pytest.raises(ValidationError) as exc_info:
        validate_html_structure(html, ["div.missing", "span.notfound"])
    assert "div.missing" in str(exc_info.value)


def test_validate_price_valid():
    validate_price(10.99)  # Should not raise
    validate_price(0.01)   # Should not raise


def test_validate_price_zero():
    with pytest.raises(ValidationError) as exc_info:
        validate_price(0)
    assert "greater than 0" in str(exc_info.value)


def test_validate_price_negative():
    with pytest.raises(ValidationError) as exc_info:
        validate_price(-5.0)
    assert "greater than 0" in str(exc_info.value)


def test_deduplicate_items_empty():
    result = deduplicate_items([])
    assert result == []


def test_deduplicate_items_unique():
    items = [
        {"item_hash": "abc123", "name": "Item 1"},
        {"item_hash": "def456", "name": "Item 2"},
    ]
    result = deduplicate_items(items)
    assert len(result) == 2


def test_deduplicate_items_with_duplicates():
    items = [
        {"item_hash": "abc123", "name": "Item 1"},
        {"item_hash": "abc123", "name": "Item 1 Duplicate"},
        {"item_hash": "def456", "name": "Item 2"},
    ]
    result = deduplicate_items(items)
    assert len(result) == 2
    assert result[0]["name"] == "Item 1"  # First occurrence kept


def test_deduplicate_items_missing_hash():
    items = [{"name": "No Hash"}]
    with pytest.raises(ValidationError) as exc_info:
        deduplicate_items(items)
    assert "item_hash" in str(exc_info.value)
