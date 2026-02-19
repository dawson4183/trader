# Trader Package

A Python package for parsing, validating, and deduplicating trading items from HTML sources.

## Features

- **HTML Structure Validation**: Verify required CSS selectors exist before parsing
- **Price Validation**: Ensure all prices are greater than 0
- **Item Deduplication**: Remove duplicate items based on item hash
- **Type-Safe**: Full type annotations with mypy support
- **Well-Tested**: Comprehensive test suite with pytest

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd trader

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Quick Start

### Basic Usage

```python
from trader import ItemParser, ValidationError

# Configure the parser with required CSS selectors
config = {
    'required_selectors': ['.item', '.price-tag', '.item-list']
}

# Create parser instance
parser = ItemParser(config)

# Parse HTML content
html = """
<html>
    <body>
        <div class="item-list">
            <div class="item" data-item-hash="abc123" data-price="19.99" data-name="Widget">
                Widget
            </div>
        </div>
        <div class="price-tag">Prices in USD</div>
    </body>
</html>
"""

try:
    items = parser.parse(html)
    for item in items:
        print(f"Name: {item['name']}, Price: {item['price']}, Hash: {item['item_hash']}")
except ValidationError as e:
    print(f"Validation failed: {e.message}")
```

### Using Validators Directly

```python
from trader import validate_html_structure, validate_price, deduplicate_items
from trader import ValidationError

# Validate HTML structure
html_content = "<html><div class='item'>Item</div></html>"
required_selectors = ['.item']

try:
    validate_html_structure(html_content, required_selectors)
    print("HTML structure is valid")
except ValidationError as e:
    print(f"Invalid HTML: {e.message}")

# Validate price
try:
    validate_price(19.99)
    print("Price is valid")
except ValidationError as e:
    print(f"Invalid price: {e.message}")

# Deduplicate items
items = [
    {'item_hash': 'hash1', 'name': 'Item 1', 'price': 10.00},
    {'item_hash': 'hash1', 'name': 'Duplicate', 'price': 10.00},
    {'item_hash': 'hash2', 'name': 'Item 2', 'price': 20.00},
]
unique_items = deduplicate_items(items)
print(f"Unique items: {len(unique_items)}")  # Output: 2
```

## API Reference

### ItemParser

The main class for parsing items from HTML.

#### `ItemParser(config)`

Initialize the parser with configuration.

**Args:**
- `config` (dict): Configuration dictionary containing:
  - `required_selectors` (List[str]): List of CSS selectors required in HTML

**Raises:**
- `ValidationError`: If config is missing `required_selectors` key

#### `ItemParser.parse(html)`

Parse HTML and extract items with validation.

**Args:**
- `html` (str): The HTML content to parse

**Returns:**
- `List[Dict[str, Any]]`: A list of unique item dictionaries

**Raises:**
- `ValidationError`: If HTML structure is invalid or any item has an invalid price

### Validators

#### `validate_html_structure(html, required_selectors)`

Validate that HTML contains all required CSS selectors.

**Args:**
- `html` (str): The HTML content to validate
- `required_selectors` (List[str]): List of CSS selectors that must be present

**Raises:**
- `ValidationError`: If any required selector is missing from the HTML

#### `validate_price(price)`

Validate that a price is greater than 0.

**Args:**
- `price` (float): The price value to validate

**Raises:**
- `ValidationError`: If price is less than or equal to 0

#### `deduplicate_items(items)`

Remove duplicate items based on item_hash.

**Args:**
- `items` (List[Dict[str, Any]]): List of item dictionaries

**Returns:**
- `List[Dict[str, Any]]`: List of unique items (first occurrence kept)

**Raises:**
- `ValidationError`: If any item is missing the `item_hash` key

### Exceptions

#### `ValidationError`

Raised when data validation fails.

```python
from trader import ValidationError

try:
    validate_price(-10.00)
except ValidationError as e:
    print(e.message)  # Access the error message
```

## Testing

Run the test suite with pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=trader --cov-report=html

# Run specific test file
pytest tests/test_integration.py

# Run with verbose output
pytest -v
```

### Type Checking

Run mypy for type checking:

```bash
mypy trader/
```

## Project Structure

```
trader/
├── trader/
│   ├── __init__.py          # Package exports
│   ├── __main__.py          # CLI entry point
│   ├── cli.py               # CLI implementation
│   ├── exceptions.py        # Custom exceptions
│   ├── item_parser.py       # ItemParser class
│   └── validators.py        # Validation functions
├── tests/
│   ├── __init__.py
│   ├── test_integration.py  # End-to-end integration tests
│   ├── test_item_parser.py  # ItemParser unit tests
│   ├── test_validators.py   # Validator unit tests
│   └── test_exceptions.py   # Exception tests
├── pyproject.toml           # Project configuration
├── requirements.txt         # Dependencies
└── README.md                # This file
```

## Development

### Setting Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-cov mypy
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=trader --cov-report=term-missing

# Type checking
mypy trader/
```

## License

MIT License - See LICENSE file for details.
