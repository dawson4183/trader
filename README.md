# Trader Package

A Python package for parsing trader items from HTML with comprehensive data validation.

## Features

- **HTML Structure Validation**: Ensure expected CSS selectors exist before parsing
- **Price Validation**: Validate that item prices are positive numbers
- **Item Deduplication**: Remove duplicate items based on unique hash values
- **Structured Logging**: JSON-formatted logging with webhook support for alerts
- **Database Support**: SQLite database connection management
- **Web Scraping**: HTTP scraper with proper error handling

## Installation

```bash
pip install -r requirements.txt
```

Or with pip:

```bash
pip install -e .
```

For development dependencies:

```bash
pip install -e ".[dev]"
```

## Quick Start

### HTML Structure Validation

Validate that HTML contains expected CSS selectors before parsing:

```python
from trader import validate_html_structure, ValidationError

html = """
<html>
    <body>
        <div class="item">
            <span class="name">Sword</span>
            <span class="price">99.99</span>
        </div>
    </body>
</html>
"""

# Define required CSS selectors
required_selectors = ["div.item", "span.name", "span.price"]

try:
    validate_html_structure(html, required_selectors)
    print("HTML structure is valid!")
except ValidationError as e:
    print(f"Validation failed: {e}")
```

### Price Validation

Ensure item prices are valid positive numbers:

```python
from trader import validate_price, ValidationError

item = {"name": "Magic Potion", "price": 15.50}

try:
    validate_price(item["price"])
    print(f"Price {item['price']} is valid!")
except ValidationError as e:
    print(f"Invalid price: {e}")
```

### Item Deduplication

Remove duplicate items based on their hash:

```python
from trader import deduplicate_items

items = [
    {"item_hash": "abc123", "name": "Item 1", "price": 10.0},
    {"item_hash": "def456", "name": "Item 2", "price": 20.0},
    {"item_hash": "abc123", "name": "Item 1 Duplicate", "price": 10.0},  # Duplicate
]

unique_items = deduplicate_items(items)
print(f"Reduced from {len(items)} to {len(unique_items)} unique items")
# Output: Reduced from 3 to 2 unique items
```

### Full Parsing Workflow

Complete example showing the full workflow:

```python
from trader import (
    validate_html_structure,
    validate_price,
    deduplicate_items,
    ValidationError,
    Scraper
)

# Fetch HTML from a URL
scraper = Scraper(timeout=30)
html = scraper.fetch_url("https://example.com/items")

if html is None:
    print("Failed to fetch HTML")
    exit(1)

# Validate HTML structure
required_selectors = ["div.item", "span.name", "span.price"]
try:
    validate_html_structure(html, required_selectors)
except ValidationError as e:
    print(f"Invalid HTML structure: {e}")
    exit(1)

# Parse items from HTML (implementation depends on your use case)
items = parse_items_from_html(html)  # Your parsing logic here

# Validate each item and build validated list
validated_items = []
for item in items:
    try:
        validate_price(item["price"])
        validated_items.append(item)
    except ValidationError as e:
        print(f"Skipping invalid item {item['name']}: {e}")

# Remove duplicates
unique_items = deduplicate_items(validated_items)
print(f"Successfully processed {len(unique_items)} unique items")
```

### Database Operations

Store and retrieve items from a SQLite database:

```python
from trader import DatabaseConnection, get_connection

# Using context manager (recommended)
with DatabaseConnection("trader.db") as db:
    # Create table
    db.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            item_hash TEXT UNIQUE,
            name TEXT,
            price REAL
        )
    """)
    
    # Insert items
    for item in unique_items:
        db.execute(
            "INSERT OR IGNORE INTO items (item_hash, name, price) VALUES (?, ?, ?)",
            (item["item_hash"], item["name"], item["price"])
        )
    
    # Query items
    results = db.execute("SELECT * FROM items WHERE price > ?", (50.0,))
    print(f"Found {len(results)} items over $50")
```

### Structured Logging

Use JSON-formatted logging for your applications:

```python
import logging
from trader import JsonFormatter, WebhookHandler

# Set up JSON formatter
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())

logger = logging.getLogger("my_app")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Log with context
logger.info(
    "Item processed",
    extra={"item_id": "abc123", "price": 99.99, "action": "parsed"}
)
# Output: {"timestamp": "2024-01-15T10:30:45.123456+00:00", "level": "INFO", 
#          "message": "Item processed", "context": {"item_id": "abc123", "price": 99.99, "action": "parsed"}}

# Add webhook handler for errors (optional)
webhook_handler = WebhookHandler(webhook_url="https://hooks.example.com/alerts")
logger.addHandler(webhook_handler)
```

## API Reference

### Validation Functions

#### `validate_html_structure(html: str, required_selectors: List[str]) -> None`

Validate that HTML contains expected CSS selectors before parsing.

**Args:**
- `html`: The HTML content to validate
- `required_selectors`: List of CSS selectors that must be present

**Raises:**
- `ValidationError`: If any required selector is not found in the HTML

---

#### `validate_price(price: float) -> None`

Validate that price is greater than 0.

**Args:**
- `price`: The price value to validate

**Raises:**
- `ValidationError`: If price is not greater than 0

---

#### `deduplicate_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]`

Remove duplicate items based on item_hash field.

**Args:**
- `items`: List of item dictionaries, each containing an 'item_hash' key

**Returns:**
- List of unique items (first occurrence kept)

**Raises:**
- `ValidationError`: If an item is missing the 'item_hash' field

---

### Classes

#### `Scraper`

HTTP scraper for fetching web content.

```python
scraper = Scraper(timeout=30)
content = scraper.fetch_url("https://example.com")
```

---

#### `DatabaseConnection`

Manages SQLite database connections with context manager support.

```python
with DatabaseConnection("trader.db") as db:
    results = db.execute("SELECT * FROM items")
```

---

#### `ValidationError`

Exception raised when data validation fails.

```python
from trader import ValidationError

try:
    validate_price(-10)
except ValidationError as e:
    print(f"Validation failed: {e}")
```

---

#### `JsonFormatter`

Custom JSON formatter for structured logging.

---

#### `WebhookHandler`

Custom logging handler that POSTs ERROR and CRITICAL logs to a webhook.

## Testing

Run the test suite:

```bash
pytest -v
```

Run with coverage:

```bash
pytest --cov=trader --cov-report=term-missing
```

Run integration tests only:

```bash
pytest tests/test_integration.py -v
```

## Type Checking

Run mypy type checker:

```bash
mypy trader/ tests/
```

## Configuration

### Environment Variables

The following environment variables can be used to configure logging:

- `LOG_LEVEL`: Logging level (default: INFO)
- `LOG_FORMAT`: JSON log format template
- `LOG_RETENTION_DAYS`: Log retention period in days (default: 7)
- `WEBHOOK_URL`: Webhook URL for error alerts

Example:

```bash
export LOG_LEVEL=DEBUG
export WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Project Structure

```
trader/
├── __init__.py          # Package exports and main API
├── exceptions.py        # Custom exception classes
├── item_parser.py       # Validation and deduplication functions
├── scraper.py          # HTTP scraping utilities
├── database.py         # Database connection management
├── logging_utils.py    # Structured logging utilities
└── config.py           # Configuration settings

tests/
├── test_item_parser.py     # Unit tests for validation functions
├── test_integration.py     # Integration tests
├── test_scraper.py         # Scraper tests
├── test_database.py        # Database tests
├── test_logging_utils.py   # Logging tests
└── test_config.py          # Config tests
```

## License

This project is private and proprietary.

## Contributing

1. Ensure tests pass: `pytest -v`
2. Ensure type checking passes: `mypy trader/ tests/`
3. Follow Google-style docstrings for all public functions
4. Add tests for new functionality
