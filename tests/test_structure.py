"""Tests for project structure validation."""
import os
from pathlib import Path


def test_trader_directory_exists():
    """Verify trader/ directory exists with __init__.py."""
    trader_dir = Path(__file__).parent.parent / "trader"
    assert trader_dir.exists(), "trader/ directory should exist"
    assert trader_dir.is_dir(), "trader/ should be a directory"
    init_file = trader_dir / "__init__.py"
    assert init_file.exists(), "trader/__init__.py should exist"


def test_tests_directory_exists():
    """Verify tests/ directory exists with __init__.py."""
    tests_dir = Path(__file__).parent.parent / "tests"
    assert tests_dir.exists(), "tests/ directory should exist"
    assert tests_dir.is_dir(), "tests/ should be a directory"
    init_file = tests_dir / "__init__.py"
    assert init_file.exists(), "tests/__init__.py should exist"


def test_pyproject_toml_exists():
    """Verify pyproject.toml exists."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml should exist"


def test_requirements_txt_exists():
    """Verify requirements.txt exists with required dependencies."""
    req_file = Path(__file__).parent.parent / "requirements.txt"
    assert req_file.exists(), "requirements.txt should exist"
    
    content = req_file.read_text()
    assert "beautifulsoup4" in content, "requirements.txt should list beautifulsoup4"
    assert "pytest" in content, "requirements.txt should list pytest"
    assert "mypy" in content, "requirements.txt should list mypy"


def test_trader_package_importable():
    """Verify trader package can be imported."""
    import trader
    assert trader is not None


def test_exceptions_module_exists():
    """Verify exceptions module exists with ValidationError."""
    from trader.exceptions import ValidationError
    assert issubclass(ValidationError, Exception)


def test_item_parser_module_exists():
    """Verify item_parser module exists with required functions."""
    from trader.item_parser import validate_html_structure
    from trader.item_parser import validate_price
    from trader.item_parser import deduplicate_items
    
    assert callable(validate_html_structure)
    assert callable(validate_price)
    assert callable(deduplicate_items)
