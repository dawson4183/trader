"""Tests for logging integration in trader.item_parser module."""

import json
import logging
from unittest.mock import patch

import pytest
from trader.item_parser import validate_html_structure, validate_price, deduplicate_items
from trader.exceptions import ValidationError


class TestValidateHtmlStructureLogging:
    """Test logging in validate_html_structure function."""

    def test_logs_warning_on_missing_selector(self, caplog):
        """Should log WARNING when CSS selector is not found."""
        caplog.set_level(logging.WARNING)
        html = "<html><body><div class='item'>Test</div></body></html>"
        
        with pytest.raises(ValidationError):
            validate_html_structure(html, ["div.missing"])
        
        # Verify warning was logged
        assert any(
            record.levelno == logging.WARNING and "CSS selector not found" in record.message
            for record in caplog.records
        )

    def test_log_contains_selector_context(self, caplog):
        """Warning log should contain selector in context."""
        caplog.set_level(logging.WARNING)
        html = "<html><body><div class='item'>Test</div></body></html>"
        
        with pytest.raises(ValidationError):
            validate_html_structure(html, ["span.notfound"])
        
        # Find the warning record
        warning_record = next(
            record for record in caplog.records
            if record.levelno == logging.WARNING and "CSS selector not found" in record.message
        )
        
        # Check context
        assert warning_record.selector == "span.notfound"
        assert warning_record.html_length == len(html)

    def test_logs_for_each_missing_selector(self, caplog):
        """Should log for the first missing selector found."""
        caplog.set_level(logging.WARNING)
        html = "<html><body></body></html>"
        
        with pytest.raises(ValidationError):
            validate_html_structure(html, ["div.first", "span.second"])
        
        # Should have exactly one warning (first missing selector triggers exception)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "first" in warnings[0].selector


class TestValidatePriceLogging:
    """Test logging in validate_price function."""

    def test_logs_warning_on_zero_price(self, caplog):
        """Should log WARNING when price is zero."""
        caplog.set_level(logging.WARNING)
        
        with pytest.raises(ValidationError):
            validate_price(0)
        
        assert any(
            record.levelno == logging.WARNING and "price must be greater than 0" in record.message
            for record in caplog.records
        )

    def test_logs_warning_on_negative_price(self, caplog):
        """Should log WARNING when price is negative."""
        caplog.set_level(logging.WARNING)
        
        with pytest.raises(ValidationError):
            validate_price(-5.0)
        
        assert any(
            record.levelno == logging.WARNING and "price must be greater than 0" in record.message
            for record in caplog.records
        )

    def test_log_contains_price_context(self, caplog):
        """Warning log should contain price value and validation rule."""
        caplog.set_level(logging.WARNING)
        
        with pytest.raises(ValidationError):
            validate_price(-10.5)
        
        # Find the warning record
        warning_record = next(
            record for record in caplog.records
            if record.levelno == logging.WARNING
        )
        
        assert warning_record.price == -10.5
        assert warning_record.validation_rule == "price > 0"


class TestDeduplicateItemsLogging:
    """Test logging in deduplicate_items function."""

    def test_logs_info_with_deduplication_stats(self, caplog):
        """Should log INFO with deduplication statistics."""
        caplog.set_level(logging.INFO)
        
        items = [
            {"item_hash": "abc123", "name": "Item 1"},
            {"item_hash": "abc123", "name": "Item 1 Duplicate"},
            {"item_hash": "def456", "name": "Item 2"},
        ]
        
        deduplicate_items(items)
        
        # Verify info was logged
        assert any(
            record.levelno == logging.INFO and "Deduplication completed" in record.message
            for record in caplog.records
        )

    def test_log_contains_correct_stats(self, caplog):
        """INFO log should contain correct statistics."""
        caplog.set_level(logging.INFO)
        
        items = [
            {"item_hash": "hash1", "name": "Item 1"},
            {"item_hash": "hash1", "name": "Duplicate 1"},
            {"item_hash": "hash2", "name": "Item 2"},
            {"item_hash": "hash1", "name": "Duplicate 2"},
        ]
        
        deduplicate_items(items)
        
        # Find the info record
        info_record = next(
            record for record in caplog.records
            if record.levelno == logging.INFO and "Deduplication completed" in record.message
        )
        
        assert info_record.total_items == 4
        assert info_record.unique_items == 2
        assert info_record.duplicates_removed == 2
        assert info_record.deduplication_rate == 0.5

    def test_no_log_on_empty_list(self, caplog):
        """Should not log deduplication stats when items list is empty."""
        caplog.set_level(logging.INFO)
        
        result = deduplicate_items([])
        
        assert result == []
        # Should not have any deduplication logs
        dedup_logs = [
            r for r in caplog.records
            if "Deduplication completed" in r.message
        ]
        assert len(dedup_logs) == 0

    def test_logs_error_on_missing_hash(self, caplog):
        """Should log ERROR when item is missing item_hash field."""
        caplog.set_level(logging.ERROR)
        
        items = [{"name": "No Hash"}]
        
        with pytest.raises(ValidationError):
            deduplicate_items(items)
        
        # Verify error was logged
        assert any(
            record.levelno == logging.ERROR and "missing item_hash" in record.message
            for record in caplog.records
        )

    def test_error_log_contains_context(self, caplog):
        """ERROR log should contain item context."""
        caplog.set_level(logging.ERROR)
        
        items = [{"name": "No Hash", "price": 10.99}]
        
        with pytest.raises(ValidationError):
            deduplicate_items(items)
        
        # Find the error record
        error_record = next(
            record for record in caplog.records
            if record.levelno == logging.ERROR
        )
        
        assert error_record.item_keys == ["name", "price"]
        assert "No Hash" in error_record.item_preview


class TestLoggingFormat:
    """Test that item_parser logs are properly formatted as JSON."""

    def test_warning_logs_are_valid_json(self):
        """Warning logs should be valid JSON when using JsonFormatter."""
        import io
        from trader.logging_utils import JsonFormatter
        
        # Set up a handler with JsonFormatter using StringIO
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(JsonFormatter())
        
        # Get the item_parser logger and add our handler
        logger = logging.getLogger("trader.item_parser")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        
        html = "<html><body></body></html>"
        
        with pytest.raises(ValidationError):
            validate_html_structure(html, ["div.missing"])
        
        # Get the logged output
        output = log_capture.getvalue()
        
        # Should be valid JSON
        if output.strip():
            parsed = json.loads(output.strip())
            assert "CSS selector not found" in parsed["message"]
            assert parsed["level"] == "WARNING"
        
        # Clean up handler
        logger.removeHandler(handler)


class TestLoggerInitialization:
    """Test that logger is properly initialized in item_parser module."""

    def test_module_has_logger_instance(self):
        """item_parser module should have a logger instance."""
        import trader.item_parser as item_parser
        
        assert hasattr(item_parser, "logger")
        assert isinstance(item_parser.logger, logging.Logger)
        assert item_parser.logger.name == "trader.item_parser"
