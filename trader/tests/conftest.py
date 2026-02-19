"""Shared pytest fixtures for trader package tests."""
from typing import Dict, Any, Generator
import pytest


@pytest.fixture
def sample_html_basic() -> str:
    """Return a basic HTML fixture with item structure."""
    return """
    <html>
        <body>
            <div class="item">
                <h1 class="title">Test Item</h1>
                <span class="price">$19.99</span>
                <p class="description">A test item description</p>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_html_no_price() -> str:
    """Return HTML fixture without price element."""
    return """
    <html>
        <body>
            <div class="item">
                <h1 class="title">Test Item</h1>
                <p class="description">A test item description</p>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_html_no_title() -> str:
    """Return HTML fixture without title element."""
    return """
    <html>
        <body>
            <div class="item">
                <span class="price">$19.99</span>
                <p class="description">A test item description</p>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_html_empty() -> str:
    """Return empty HTML fixture."""
    return ""


@pytest.fixture
def sample_html_invalid() -> str:
    """Return invalid/malformed HTML fixture."""
    return "<not-valid>unclosed tag"


@pytest.fixture
def sample_html_multiple_items() -> str:
    """Return HTML fixture with multiple items."""
    return """
    <html>
        <body>
            <div class="item">
                <h1 class="title">Item One</h1>
                <span class="price">$10.00</span>
            </div>
            <div class="item">
                <h1 class="title">Item Two</h1>
                <span class="price">$20.00</span>
            </div>
            <div class="item">
                <h1 class="title">Item Three</h1>
                <span class="price">$30.00</span>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def sample_selectors() -> Dict[str, str]:
    """Return standard CSS selectors for parsing."""
    return {
        'title': '.title',
        'price': '.price',
        'description': '.description'
    }


@pytest.fixture
def sample_item() -> Dict[str, Any]:
    """Return a sample parsed item."""
    return {
        'title': 'Test Item',
        'price': '$19.99',
        'description': 'A test item description',
        'item_hash': '12345'
    }


@pytest.fixture
def sample_items_list() -> list[Dict[str, Any]]:
    """Return a list of sample items for deduplication testing."""
    return [
        {'title': 'Item A', 'price': '$10', 'item_hash': 'hash1'},
        {'title': 'Item B', 'price': '$20', 'item_hash': 'hash2'},
        {'title': 'Item A Dup', 'price': '$10', 'item_hash': 'hash1'},  # Duplicate
        {'title': 'Item C', 'price': '$30', 'item_hash': 'hash3'},
    ]


@pytest.fixture
def price_strings_valid() -> Dict[str, Dict[str, Any]]:
    """Return valid price strings with expected parsed values."""
    return {
        'simple_usd': {'input': '$19.99', 'amount': 19.99, 'currency': 'USD'},
        'eur_symbol': {'input': '€50.00', 'amount': 50.00, 'currency': 'EUR'},
        'gbp_symbol': {'input': '£100', 'amount': 100.0, 'currency': 'GBP'},
        'with_code': {'input': '25.00 CAD', 'amount': 25.00, 'currency': 'CAD'},
        'jpy_symbol': {'input': '¥1000', 'amount': 1000.0, 'currency': 'JPY'},
        'no_symbol': {'input': '15.50', 'amount': 15.50, 'currency': 'USD'},
        'with_comma': {'input': '$1,234.56', 'amount': 1234.56, 'currency': 'USD'},
    }


@pytest.fixture
def price_strings_invalid() -> list[str]:
    """Return invalid price strings that should raise ValidationError."""
    return [
        '',           # Empty string
        '   ',        # Whitespace only
        'abc',        # No numbers
        '-$10.00',    # Negative (handled as invalid after parsing)
    ]


# Fixtures for parser.py module

@pytest.fixture
def parser_html_basic() -> str:
    """Return HTML fixture with .item-name, .price, and data-hash for parser.py."""
    return """
    <html>
        <body>
            <div class="item" data-hash="abc123xyz">
                <h1 class="item-name">Test Item</h1>
                <span class="price">$19.99</span>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def parser_html_no_item_name() -> str:
    """Return HTML fixture without .item-name element."""
    return """
    <html>
        <body>
            <div class="item" data-hash="abc123xyz">
                <span class="price">$19.99</span>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def parser_html_no_price() -> str:
    """Return HTML fixture without .price element."""
    return """
    <html>
        <body>
            <div class="item" data-hash="abc123xyz">
                <h1 class="item-name">Test Item</h1>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def parser_html_no_data_hash() -> str:
    """Return HTML fixture without data-hash attribute."""
    return """
    <html>
        <body>
            <div class="item">
                <h1 class="item-name">Test Item</h1>
                <span class="price">$19.99</span>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def parser_html_empty_hash() -> str:
    """Return HTML fixture with empty data-hash attribute."""
    return """
    <html>
        <body>
            <div class="item" data-hash="">
                <h1 class="item-name">Test Item</h1>
                <span class="price">$19.99</span>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def parser_html_empty() -> str:
    """Return empty HTML fixture for parser.py."""
    return ""


@pytest.fixture
def parser_html_whitespace() -> str:
    """Return whitespace-only HTML fixture for parser.py."""
    return "   \n\t   "
