"""Tests for test infrastructure and shared fixtures."""
import pytest
from bs4 import BeautifulSoup
from typing import Dict, Any


class TestConftestFixtures:
    """Test that all conftest fixtures work properly."""

    def test_sample_html_basic_fixture(self, sample_html_basic: str) -> None:
        """Verify sample_html_basic fixture returns valid HTML."""
        assert isinstance(sample_html_basic, str)
        assert "<html>" in sample_html_basic
        assert '<h1 class="title">Test Item</h1>' in sample_html_basic
        assert '<span class="price">$19.99</span>' in sample_html_basic

    def test_sample_html_no_price_fixture(self, sample_html_no_price: str) -> None:
        """Verify sample_html_no_price fixture lacks price element."""
        assert isinstance(sample_html_no_price, str)
        assert "price" not in sample_html_no_price
        assert "title" in sample_html_no_price

    def test_sample_html_no_title_fixture(self, sample_html_no_title: str) -> None:
        """Verify sample_html_no_title fixture lacks title element."""
        assert isinstance(sample_html_no_title, str)
        assert "<h1" not in sample_html_no_title
        assert "price" in sample_html_no_title

    def test_sample_html_empty_fixture(self, sample_html_empty: str) -> None:
        """Verify sample_html_empty fixture returns empty string."""
        assert sample_html_empty == ""

    def test_sample_html_invalid_fixture(self, sample_html_invalid: str) -> None:
        """Verify sample_html_invalid fixture returns malformed HTML."""
        assert isinstance(sample_html_invalid, str)
        assert "</html>" not in sample_html_invalid  # Unclosed

    def test_sample_html_multiple_items_fixture(self, sample_html_multiple_items: str) -> None:
        """Verify sample_html_multiple_items fixture has multiple items."""
        soup = BeautifulSoup(sample_html_multiple_items, 'html.parser')
        items = soup.find_all('div', class_='item')
        assert len(items) == 3

    def test_sample_selectors_fixture(self, sample_selectors: Dict[str, str]) -> None:
        """Verify sample_selectors fixture returns proper dict."""
        assert isinstance(sample_selectors, dict)
        assert 'title' in sample_selectors
        assert 'price' in sample_selectors
        assert 'description' in sample_selectors
        assert sample_selectors['title'] == '.title'

    def test_sample_item_fixture(self, sample_item: Dict[str, Any]) -> None:
        """Verify sample_item fixture returns proper dict."""
        assert isinstance(sample_item, dict)
        assert 'title' in sample_item
        assert 'price' in sample_item
        assert 'item_hash' in sample_item

    def test_sample_items_list_fixture(self, sample_items_list: list[Dict[str, Any]]) -> None:
        """Verify sample_items_list fixture returns list with items."""
        assert isinstance(sample_items_list, list)
        assert len(sample_items_list) == 4
        assert all('item_hash' in item for item in sample_items_list)

    def test_price_strings_valid_fixture(self, price_strings_valid: Dict[str, Dict[str, Any]]) -> None:
        """Verify price_strings_valid fixture returns proper structure."""
        assert isinstance(price_strings_valid, dict)
        assert 'simple_usd' in price_strings_valid
        assert 'eur_symbol' in price_strings_valid
        assert 'amount' in price_strings_valid['simple_usd']
        assert 'currency' in price_strings_valid['simple_usd']

    def test_price_strings_invalid_fixture(self, price_strings_invalid: list[str]) -> None:
        """Verify price_strings_invalid fixture returns list of invalid strings."""
        assert isinstance(price_strings_invalid, list)
        assert len(price_strings_invalid) >= 3
        assert '' in price_strings_invalid


class TestPytestDiscovery:
    """Test that pytest discovers tests correctly."""

    def test_trader_tests_directory_importable(self) -> None:
        """Verify trader.tests package can be imported."""
        from trader import tests
        assert tests is not None

    def test_conftest_importable(self) -> None:
        """Verify conftest.py can be imported from trader.tests."""
        import trader.tests.conftest as conftest_module
        assert conftest_module is not None
