"""Tests for trader validators."""

import pytest

from trader.exceptions import ValidationError
from trader.validators import validate_html_structure


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
