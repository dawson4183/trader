"""Tests for DatabaseManager class."""

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from trader.database import ConnectionPool, DatabaseManager, Transaction, insert_items_batch


class TestDatabaseManager(unittest.TestCase):
    """Test cases for DatabaseManager class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.addCleanup(lambda: os.unlink(self.db_path))

        # Initialize the database with the items table
        conn = sqlite3.connect(self.db_path)
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
        conn.close()

        self.db = DatabaseManager(self.db_path)
        self.addCleanup(self.db.close)

    def test_database_manager_initializes_with_default_values(self) -> None:
        """Test that DatabaseManager initializes with correct default values."""
        self.assertEqual(self.db.db_path, self.db_path)
        self.assertEqual(self.db.max_connections, 5)
        self.assertEqual(self.db.batch_size, 100)

    def test_database_manager_initializes_with_custom_values(self) -> None:
        """Test that DatabaseManager initializes with custom values."""
        db = DatabaseManager(self.db_path, max_connections=10, batch_size=50)
        self.addCleanup(db.close)

        self.assertEqual(db.db_path, self.db_path)
        self.assertEqual(db.max_connections, 10)
        self.assertEqual(db.batch_size, 50)

    def test_connection_pool_property_returns_connection_pool(self) -> None:
        """Test that connection_pool property returns a ConnectionPool instance."""
        pool = self.db.connection_pool

        self.assertIsInstance(pool, ConnectionPool)
        self.assertEqual(pool.db_path, self.db_path)
        self.assertEqual(pool.max_connections, 5)

    def test_connection_pool_property_same_instance(self) -> None:
        """Test that connection_pool property returns the same instance."""
        pool1 = self.db.connection_pool
        pool2 = self.db.connection_pool

        self.assertIs(pool1, pool2)

    def test_insert_items_batch_delegates_to_function(self) -> None:
        """Test that insert_items_batch method inserts items."""
        items = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
            {'name': 'Item 2', 'price': 20.0, 'url': 'http://example.com/2'},
        ]

        inserted, duplicates = self.db.insert_items_batch(items)

        self.assertEqual(inserted, 2)
        self.assertEqual(duplicates, 0)

        # Verify items exist in database
        pool = self.db.connection_pool
        with pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 2)

    def test_insert_items_batch_uses_default_batch_size(self) -> None:
        """Test that insert_items_batch uses default batch_size from instance."""
        db = DatabaseManager(self.db_path, batch_size=10)
        self.addCleanup(db.close)

        # Create 25 items to test batching
        items = [
            {'name': f'Item {i}', 'price': float(i), 'url': f'http://example.com/{i}'}
            for i in range(25)
        ]

        inserted, duplicates = db.insert_items_batch(items)

        self.assertEqual(inserted, 25)
        self.assertEqual(duplicates, 0)

    def test_insert_items_batch_custom_batch_size(self) -> None:
        """Test that insert_items_batch accepts custom batch_size parameter."""
        items = [
            {'name': f'Item {i}', 'price': float(i), 'url': f'http://example.com/{i}'}
            for i in range(25)
        ]

        # Use custom batch_size of 5
        inserted, duplicates = self.db.insert_items_batch(items, batch_size=5)

        self.assertEqual(inserted, 25)
        self.assertEqual(duplicates, 0)

    def test_insert_items_batch_ignores_duplicates(self) -> None:
        """Test that insert_items_batch handles duplicates correctly."""
        # First insert
        items = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
            {'name': 'Item 2', 'price': 20.0, 'url': 'http://example.com/2'},
        ]
        self.db.insert_items_batch(items)

        # Second insert with duplicates
        items_with_duplicates = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},  # Duplicate
            {'name': 'Item 3', 'price': 30.0, 'url': 'http://example.com/3'},  # New
        ]
        inserted, duplicates = self.db.insert_items_batch(items_with_duplicates)

        self.assertEqual(inserted, 1)  # Only Item 3 inserted
        self.assertEqual(duplicates, 1)  # Item 1 was a duplicate

    def test_insert_items_batch_empty_list(self) -> None:
        """Test that empty list returns (0, 0)."""
        result = self.db.insert_items_batch([])

        self.assertEqual(result, (0, 0))

    def test_insert_items_batch_with_state_manager_saves_initial_state(self) -> None:
        """Test that insert_items_batch saves state before starting."""
        from trader.state import StateManager

        state_manager = MagicMock(spec=StateManager)
        state_manager.save = MagicMock()
        state_manager.record_item = MagicMock()

        items = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
        ]

        self.db.insert_items_batch(items, state_manager=state_manager)

        # Should save initial state before starting
        state_manager.save.assert_called_once()

    def test_insert_items_batch_with_state_manager_records_items(self) -> None:
        """Test that insert_items_batch records items with state manager."""
        from trader.state import StateManager

        state_manager = MagicMock(spec=StateManager)
        state_manager.save = MagicMock()
        state_manager.record_item = MagicMock()

        items = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
            {'name': 'Item 2', 'price': 20.0, 'url': 'http://example.com/2'},
            {'name': 'Item 3', 'price': 30.0, 'url': 'http://example.com/3'},
        ]

        self.db.insert_items_batch(items, state_manager=state_manager, batch_size=2)

        # Should record each item (3 items total)
        self.assertEqual(state_manager.record_item.call_count, 3)

    def test_insert_items_batch_with_state_manager_saves_on_crash(self) -> None:
        """Test that insert_items_batch saves state on exception."""
        from trader.state import StateManager

        state_manager = MagicMock(spec=StateManager)
        state_manager.save = MagicMock()
        state_manager.record_item = MagicMock()
        state_manager.save_on_crash = MagicMock()

        # Create a mock pool that raises an exception
        mock_pool = MagicMock()
        mock_pool.__enter__ = MagicMock(side_effect=Exception("Database error"))
        mock_pool.__exit__ = MagicMock()

        # Replace the pool with our mock
        self.db._pool = mock_pool

        items = [{'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'}]

        with self.assertRaises(Exception) as context:
            self.db.insert_items_batch(items, state_manager=state_manager)

        self.assertIn("Database error", str(context.exception))
        # Should save state on crash
        state_manager.save_on_crash.assert_called_once()

    def test_context_manager(self) -> None:
        """Test that DatabaseManager works as a context manager."""
        items = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
        ]

        with DatabaseManager(self.db_path) as db:
            inserted, duplicates = db.insert_items_batch(items)
            self.assertEqual(inserted, 1)

        # After exiting context, pool should be closed
        self.assertTrue(db.connection_pool._closed)

    def test_close_releases_resources(self) -> None:
        """Test that close properly cleans up resources."""
        db = DatabaseManager(self.db_path)
        db.close()

        # Pool should be closed
        self.assertTrue(db.connection_pool._closed)

    def test_pool_reused_across_batches(self) -> None:
        """Test that the same pool is used across multiple operations."""
        items1 = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
        ]
        items2 = [
            {'name': 'Item 2', 'price': 20.0, 'url': 'http://example.com/2'},
        ]

        pool_before = self.db.connection_pool

        self.db.insert_items_batch(items1)
        self.db.insert_items_batch(items2)

        pool_after = self.db.connection_pool

        # Should be the same pool instance
        self.assertIs(pool_before, pool_after)

        # Verify items exist
        with self.db.connection_pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 2)


if __name__ == '__main__':
    unittest.main()
