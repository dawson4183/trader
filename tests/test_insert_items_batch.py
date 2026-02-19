"""Tests for insert_items_batch function."""

import os
import sqlite3
import tempfile
import unittest

from trader.database import ConnectionPool, Transaction, insert_items_batch


class TestInsertItemsBatch(unittest.TestCase):
    """Test cases for insert_items_batch function."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.addCleanup(lambda: os.unlink(self.db_path))

        # Initialize the database with the items table
        self.pool = ConnectionPool(self.db_path)
        self.addCleanup(self.pool.close)

        with self.pool as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL,
                    url TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_items_url 
                ON items(url) WHERE url IS NOT NULL
            ''')
            conn.commit()

    def test_insert_items_batch_returns_tuple(self) -> None:
        """Test that insert_items_batch returns a tuple of (inserted, duplicates)."""
        items = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
            {'name': 'Item 2', 'price': 20.0, 'url': 'http://example.com/2'},
        ]

        result = insert_items_batch(self.pool, items)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        inserted_count, duplicate_count = result
        self.assertIsInstance(inserted_count, int)
        self.assertIsInstance(duplicate_count, int)

    def test_insert_items_batch_inserts_items(self) -> None:
        """Test that insert_items_batch correctly inserts items."""
        items = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
            {'name': 'Item 2', 'price': 20.0, 'url': 'http://example.com/2'},
            {'name': 'Item 3', 'price': 30.0, 'url': 'http://example.com/3'},
        ]

        inserted, duplicates = insert_items_batch(self.pool, items)

        self.assertEqual(inserted, 3)
        self.assertEqual(duplicates, 0)

        # Verify items exist in database
        with self.pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 3)

    def test_insert_items_batch_default_batch_size(self) -> None:
        """Test that default batch_size is 100."""
        # Create 150 items to test batching
        items = [
            {'name': f'Item {i}', 'price': float(i), 'url': f'http://example.com/{i}'}
            for i in range(150)
        ]

        inserted, duplicates = insert_items_batch(self.pool, items)

        self.assertEqual(inserted, 150)
        self.assertEqual(duplicates, 0)

        # Verify all items exist
        with self.pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 150)

    def test_insert_items_batch_custom_batch_size(self) -> None:
        """Test that custom batch_size parameter works."""
        items = [
            {'name': f'Item {i}', 'price': float(i), 'url': f'http://example.com/{i}'}
            for i in range(25)
        ]

        inserted, duplicates = insert_items_batch(self.pool, items, batch_size=10)

        self.assertEqual(inserted, 25)
        self.assertEqual(duplicates, 0)

    def test_insert_items_batch_ignores_duplicates(self) -> None:
        """Test that INSERT OR IGNORE handles duplicates."""
        # First insert
        items = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
            {'name': 'Item 2', 'price': 20.0, 'url': 'http://example.com/2'},
        ]
        insert_items_batch(self.pool, items)

        # Second insert with duplicates
        items_with_duplicates = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},  # Duplicate
            {'name': 'Item 3', 'price': 30.0, 'url': 'http://example.com/3'},  # New
        ]
        inserted, duplicates = insert_items_batch(self.pool, items_with_duplicates)

        self.assertEqual(inserted, 1)  # Only Item 3 inserted
        self.assertEqual(duplicates, 1)  # Item 1 was a duplicate

        # Verify total count
        with self.pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 3)

    def test_insert_items_batch_empty_list(self) -> None:
        """Test that empty list returns (0, 0)."""
        result = insert_items_batch(self.pool, [])

        self.assertEqual(result, (0, 0))

    def test_insert_items_batch_uses_connection_pool(self) -> None:
        """Test that insert_items_batch uses ConnectionPool context manager."""
        items = [
            {'name': 'Test Item', 'price': 99.99, 'url': 'http://example.com/test'},
        ]

        # Active connections should be 0 before and after
        self.assertEqual(self.pool.active_count, 0)
        insert_items_batch(self.pool, items)
        self.assertEqual(self.pool.active_count, 0)

    def test_insert_items_batch_uses_transaction(self) -> None:
        """Test that insert_items_batch uses Transaction context manager."""
        items = [
            {'name': 'Test Item', 'price': 99.99, 'url': 'http://example.com/test'},
        ]

        inserted, duplicates = insert_items_batch(self.pool, items)

        # Verify data was committed
        with self.pool as conn:
            cursor = conn.execute("SELECT name, price, url FROM items")
            row = cursor.fetchone()
            self.assertEqual(row[0], 'Test Item')
            self.assertEqual(row[1], 99.99)
            self.assertEqual(row[2], 'http://example.com/test')

    def test_insert_items_batch_handles_missing_optional_fields(self) -> None:
        """Test that insert_items_batch handles items with missing optional fields."""
        items = [
            {'name': 'Item With Price', 'price': 10.0},  # No url
            {'name': 'Item With URL', 'url': 'http://example.com/no-price'},  # No price
            {'name': 'Item Minimal'},  # Only name
        ]

        inserted, duplicates = insert_items_batch(self.pool, items)

        self.assertEqual(inserted, 3)

        # Verify items in database
        with self.pool as conn:
            cursor = conn.execute("SELECT name, price, url FROM items ORDER BY name")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0], ('Item Minimal', None, None))
            self.assertEqual(rows[1], ('Item With Price', 10.0, None))
            self.assertEqual(rows[2], ('Item With URL', None, 'http://example.com/no-price'))


if __name__ == '__main__':
    unittest.main()