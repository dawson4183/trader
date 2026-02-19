"""Comprehensive tests for the database module.

This module includes tests for all database components:
- ConnectionPool: Connection pooling with context managers
- Transaction: Transaction context manager for commit/rollback
- insert_items_batch: Batch insert operations with duplicate handling
- DatabaseManager: High-level database management with state recovery
"""

import os
import sqlite3
import tempfile
import threading
import unittest
from typing import Any
from unittest.mock import MagicMock

from trader.database import (
    ConnectionPool,
    DatabaseManager,
    Transaction,
    get_connection,
    insert_items_batch,
)
from trader.state import StateManager


class TestConnectionPool(unittest.TestCase):
    """Test cases for the ConnectionPool class."""

    def setUp(self) -> None:
        """Set up a temporary database for each test."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.addCleanup(os.close, self.db_fd)
        self.addCleanup(os.unlink, self.db_path)

        # Create a simple table for testing
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            conn.commit()

    def test_connection_pool_init(self) -> None:
        """Test ConnectionPool initialization with default and custom max_connections."""
        # Default max_connections = 5
        pool = ConnectionPool(self.db_path)
        self.assertEqual(pool.db_path, self.db_path)
        self.assertEqual(pool.max_connections, 5)
        self.assertEqual(pool.active_count, 0)
        self.assertEqual(pool.available_count, 0)
        pool.close()

        # Custom max_connections = 3
        pool = ConnectionPool(self.db_path, max_connections=3)
        self.assertEqual(pool.max_connections, 3)
        pool.close()

    def test_acquire_returns_connection(self) -> None:
        """Test that acquire() returns a valid SQLite connection."""
        pool = ConnectionPool(self.db_path)
        self.addCleanup(pool.close)

        conn = pool.acquire()
        self.assertIsInstance(conn, sqlite3.Connection)

        # Verify connection works
        cursor = conn.execute("SELECT 1")
        result = cursor.fetchone()
        self.assertEqual(result[0], 1)

        pool.release(conn)

    def test_acquire_tracks_active_connections(self) -> None:
        """Test that acquire() tracks active connections."""
        pool = ConnectionPool(self.db_path, max_connections=3)
        self.addCleanup(pool.close)

        self.assertEqual(pool.active_count, 0)

        conn1 = pool.acquire()
        self.assertEqual(pool.active_count, 1)

        conn2 = pool.acquire()
        self.assertEqual(pool.active_count, 2)

        pool.release(conn1)
        self.assertEqual(pool.active_count, 1)

        pool.release(conn2)
        self.assertEqual(pool.active_count, 0)

    def test_release_returns_connection_to_pool(self) -> None:
        """Test that release() returns connection to available pool."""
        pool = ConnectionPool(self.db_path)
        self.addCleanup(pool.close)

        conn = pool.acquire()
        self.assertEqual(pool.available_count, 0)

        pool.release(conn)
        self.assertEqual(pool.available_count, 1)
        self.assertEqual(pool.active_count, 0)

    def test_acquire_reuses_available_connections(self) -> None:
        """Test that acquire() reuses connections from the available pool."""
        pool = ConnectionPool(self.db_path)
        self.addCleanup(pool.close)

        conn1 = pool.acquire()
        pool.release(conn1)

        conn2 = pool.acquire()
        # Should be the same connection object
        self.assertIs(conn1, conn2)
        pool.release(conn2)

    def test_acquire_enforces_max_connections(self) -> None:
        """Test that acquire() enforces max_connections limit."""
        pool = ConnectionPool(self.db_path, max_connections=2)
        self.addCleanup(pool.close)

        conn1 = pool.acquire()
        conn2 = pool.acquire()

        # Third acquire should fail
        with self.assertRaises(RuntimeError) as ctx:
            pool.acquire()

        self.assertIn("Maximum connections", str(ctx.exception))

        pool.release(conn1)
        pool.release(conn2)

    def test_context_manager_acquires_and_releases(self) -> None:
        """Test context manager properly acquires and releases connections."""
        pool = ConnectionPool(self.db_path)
        self.addCleanup(pool.close)

        self.assertEqual(pool.active_count, 0)

        with pool as conn:
            self.assertEqual(pool.active_count, 1)
            self.assertIsInstance(conn, sqlite3.Connection)
            # Verify connection works
            cursor = conn.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)

        self.assertEqual(pool.active_count, 0)
        self.assertEqual(pool.available_count, 1)

    def test_context_manager_releases_on_exception(self) -> None:
        """Test that context manager releases connection even on exception."""
        pool = ConnectionPool(self.db_path)
        self.addCleanup(pool.close)

        self.assertEqual(pool.active_count, 0)

        try:
            with pool as conn:
                self.assertEqual(pool.active_count, 1)
                raise ValueError("Test exception")
        except ValueError:
            pass

        self.assertEqual(pool.active_count, 0)
        self.assertEqual(pool.available_count, 1)

    def test_context_manager_function(self) -> None:
        """Test get_connection context manager helper."""
        pool = ConnectionPool(self.db_path)
        self.addCleanup(pool.close)

        self.assertEqual(pool.active_count, 0)

        with get_connection(pool) as conn:
            self.assertEqual(pool.active_count, 1)
            self.assertIsInstance(conn, sqlite3.Connection)
            cursor = conn.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)

        self.assertEqual(pool.active_count, 0)

    def test_release_raises_on_invalid_connection(self) -> None:
        """Test that release() raises on connection not from pool."""
        pool = ConnectionPool(self.db_path)
        self.addCleanup(pool.close)

        # Create an independent connection
        other_conn = sqlite3.connect(self.db_path)
        self.addCleanup(other_conn.close)

        with self.assertRaises(ValueError) as ctx:
            pool.release(other_conn)

        self.assertIn("not from this pool", str(ctx.exception))

    def test_release_raises_on_already_released_connection(self) -> None:
        """Test that release() raises when connection already released."""
        pool = ConnectionPool(self.db_path)
        self.addCleanup(pool.close)

        conn = pool.acquire()
        pool.release(conn)

        with self.assertRaises(ValueError) as ctx:
            pool.release(conn)

        self.assertIn("not from this pool or already released", str(ctx.exception))

    def test_acquire_raises_on_closed_pool(self) -> None:
        """Test that acquire() raises on closed pool."""
        pool = ConnectionPool(self.db_path)
        pool.close()

        with self.assertRaises(RuntimeError) as ctx:
            pool.acquire()

        self.assertIn("Connection pool is closed", str(ctx.exception))

    def test_release_raises_on_closed_pool(self) -> None:
        """Test that release() raises on closed pool."""
        pool = ConnectionPool(self.db_path)
        conn = pool.acquire()
        pool.close()

        with self.assertRaises(RuntimeError) as ctx:
            pool.release(conn)

        self.assertIn("Connection pool is closed", str(ctx.exception))

    def test_close_closes_all_connections(self) -> None:
        """Test that close() closes all connections."""
        pool = ConnectionPool(self.db_path, max_connections=2)

        conn1 = pool.acquire()
        conn2 = pool.acquire()
        pool.release(conn2)  # Make conn2 available

        # Close should close both active and available connections
        pool.close()

        # Connections should be closed (operations will fail)
        with self.assertRaises(sqlite3.ProgrammingError):
            conn1.execute("SELECT 1")

        with self.assertRaises(sqlite3.ProgrammingError):
            conn2.execute("SELECT 1")

    def test_close_is_idempotent(self) -> None:
        """Test that close() can be called multiple times safely."""
        pool = ConnectionPool(self.db_path)
        pool.close()
        pool.close()  # Should not raise

    def test_thread_safety(self) -> None:
        """Test that pool is thread-safe with concurrent access."""
        pool = ConnectionPool(self.db_path, max_connections=5)
        self.addCleanup(pool.close)

        results = []
        errors = []

        def worker() -> None:
            try:
                with pool as conn:
                    cursor = conn.execute("SELECT 1")
                    results.append(cursor.fetchone()[0])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 10)
        self.assertEqual(pool.active_count, 0)  # All released

    def test_destructor_closes_connections(self) -> None:
        """Test that pool destructor closes connections."""
        pool = ConnectionPool(self.db_path)
        conn = pool.acquire()

        # Delete pool (simulating out of scope)
        pool.__del__()

        # Connection should be closed
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


class TestTransaction(unittest.TestCase):
    """Test cases for Transaction context manager."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.addCleanup(lambda: __import__('os').unlink(self.db_path))

        # Initialize the database with a test table
        self.pool = ConnectionPool(self.db_path)
        self.addCleanup(self.pool.close)

        with self.pool as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value INTEGER
                )
            ''')
            conn.commit()

    def test_transaction_enter_returns_cursor(self) -> None:
        """Test that __enter__ returns a cursor object."""
        with self.pool as conn:
            with Transaction(conn) as cursor:
                self.assertIsInstance(cursor, sqlite3.Cursor)

    def test_transaction_commit_on_success(self) -> None:
        """Test that transaction commits when no exception occurs."""
        with self.pool as conn:
            # Insert data within a transaction
            with Transaction(conn) as cursor:
                cursor.execute(
                    "INSERT INTO items (name, value) VALUES (?, ?)",
                    ("test", 42)
                )

        # Verify data was committed
        with self.pool as conn:
            cursor = conn.execute("SELECT name, value FROM items")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], ("test", 42))

    def test_transaction_rollback_on_exception(self) -> None:
        """Test that transaction rolls back when exception occurs."""
        with self.pool as conn:
            try:
                with Transaction(conn) as cursor:
                    cursor.execute(
                        "INSERT INTO items (name, value) VALUES (?, ?)",
                        ("test", 42)
                    )
                    # Raise an exception to trigger rollback
                    raise ValueError("Test exception")
            except ValueError:
                pass  # Expected

        # Verify data was NOT committed (rollback occurred)
        with self.pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 0)

    def test_transaction_propagates_exception_after_rollback(self) -> None:
        """Test that transaction propagates exceptions after rollback."""
        caught_exception: ValueError | None = None

        with self.pool as conn:
            try:
                with Transaction(conn) as cursor:
                    cursor.execute(
                        "INSERT INTO items (name, value) VALUES (?, ?)",
                        ("test", 42)
                    )
                    raise ValueError("Test exception to propagate")
            except ValueError as e:
                caught_exception = e

        # Verify the exception was propagated
        self.assertIsNotNone(caught_exception)
        self.assertEqual(str(caught_exception), "Test exception to propagate")

        # Verify data was NOT committed
        with self.pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 0)

    def test_transaction_with_explicit_connection(self) -> None:
        """Test Transaction works with explicitly acquired connections."""
        conn = self.pool.acquire()
        try:
            with Transaction(conn) as cursor:
                cursor.execute(
                    "INSERT INTO items (name, value) VALUES (?, ?)",
                    ("explicit", 100)
                )

            # Manual commit since we're using explicit connection
            conn.commit()

            # Verify data
            cursor = conn.execute("SELECT name, value FROM items")
            row = cursor.fetchone()
            self.assertEqual(row, ("explicit", 100))
        finally:
            self.pool.release(conn)

    def test_transaction_nested_contexts(self) -> None:
        """Test multiple transactions within same connection."""
        with self.pool as conn:
            # First transaction - success
            with Transaction(conn) as cursor:
                cursor.execute(
                    "INSERT INTO items (name, value) VALUES (?, ?)",
                    ("first", 1)
                )

            # Second transaction - success
            with Transaction(conn) as cursor:
                cursor.execute(
                    "INSERT INTO items (name, value) VALUES (?, ?)",
                    ("second", 2)
                )

            # Third transaction - failure
            try:
                with Transaction(conn) as cursor:
                    cursor.execute(
                        "INSERT INTO items (name, value) VALUES (?, ?)",
                        ("third", 3)
                    )
                    raise RuntimeError("Deliberate failure")
            except RuntimeError:
                pass

        # Verify results
        with self.pool as conn:
            cursor = conn.execute("SELECT name, value FROM items ORDER BY value")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0], ("first", 1))
            self.assertEqual(rows[1], ("second", 2))

    def test_transaction_multiple_inserts_in_transaction(self) -> None:
        """Test multiple inserts within a single transaction."""
        with self.pool as conn:
            with Transaction(conn) as cursor:
                cursor.execute(
                    "INSERT INTO items (name, value) VALUES (?, ?)",
                    ("item1", 10)
                )
                cursor.execute(
                    "INSERT INTO items (name, value) VALUES (?, ?)",
                    ("item2", 20)
                )
                cursor.execute(
                    "INSERT INTO items (name, value) VALUES (?, ?)",
                    ("item3", 30)
                )

        # Verify all inserted
        with self.pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 3)

    def test_transaction_integrity_error_rollback(self) -> None:
        """Test rollback on database integrity errors."""
        with self.pool as conn:
            # Insert first item
            with Transaction(conn) as cursor:
                cursor.execute(
                    "INSERT INTO items (name, value) VALUES (?, ?)",
                    ("unique_item", 42)
                )

        # Verify the first item was committed
        with self.pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 1)


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

    def test_insert_items_batch_all_duplicates(self) -> None:
        """Test edge case: all items are duplicates."""
        # First insert
        items = [
            {'name': 'Item 1', 'price': 10.0, 'url': 'http://example.com/1'},
            {'name': 'Item 2', 'price': 20.0, 'url': 'http://example.com/2'},
        ]
        insert_items_batch(self.pool, items)

        # Insert same items again (all duplicates)
        inserted, duplicates = insert_items_batch(self.pool, items)

        self.assertEqual(inserted, 0)  # Nothing inserted
        self.assertEqual(duplicates, 2)  # Both were duplicates

        # Verify total count is still 2
        with self.pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 2)

    def test_insert_items_batch_empty_list(self) -> None:
        """Test edge case: empty list returns (0, 0)."""
        items: list[dict[str, Any]] = []
        result = insert_items_batch(self.pool, items)

        self.assertEqual(result, (0, 0))

    def test_insert_items_batch_single_item(self) -> None:
        """Test edge case: single item batch."""
        items = [{'name': 'Single Item', 'price': 99.99, 'url': 'http://example.com/single'}]

        inserted, duplicates = insert_items_batch(self.pool, items)

        self.assertEqual(inserted, 1)
        self.assertEqual(duplicates, 0)

        # Verify item exists
        with self.pool as conn:
            cursor = conn.execute("SELECT name FROM items")
            row = cursor.fetchone()
            self.assertEqual(row[0], 'Single Item')

    def test_insert_items_batch_large_batch(self) -> None:
        """Test edge case: large batch of 500 items."""
        items = [
            {'name': f'Item {i}', 'price': float(i), 'url': f'http://example.com/{i}'}
            for i in range(500)
        ]

        inserted, duplicates = insert_items_batch(self.pool, items, batch_size=100)

        self.assertEqual(inserted, 500)
        self.assertEqual(duplicates, 0)

        # Verify all items exist
        with self.pool as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM items")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 500)

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
        items: list[dict[str, Any]] = [
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
        """Test edge case: empty list returns (0, 0)."""
        items: list[dict[str, Any]] = []
        result = self.db.insert_items_batch(items)

        self.assertEqual(result, (0, 0))

    def test_insert_items_batch_single_item(self) -> None:
        """Test edge case: single item batch."""
        items = [{'name': 'Single', 'price': 50.0, 'url': 'http://example.com/single'}]

        inserted, duplicates = self.db.insert_items_batch(items)

        self.assertEqual(inserted, 1)
        self.assertEqual(duplicates, 0)

    def test_insert_items_batch_with_state_manager_saves_initial_state(self) -> None:
        """Test that insert_items_batch saves state before starting."""
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


class TestDatabaseSchema(unittest.TestCase):
    """Test cases for the database schema."""

    def setUp(self) -> None:
        """Set up a temporary database for each test."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.addCleanup(os.close, self.db_fd)
        self.addCleanup(os.unlink, self.db_path)

    def _load_schema(self) -> None:
        """Load the schema into the temporary database."""
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'trader', 'schema.sql'
        )
        with sqlite3.connect(self.db_path) as conn:
            with open(schema_path, 'r') as f:
                conn.executescript(f.read())

    def test_schema_file_exists(self) -> None:
        """Test that the schema.sql file exists at trader/schema.sql."""
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'trader', 'schema.sql'
        )
        self.assertTrue(os.path.exists(schema_path), "schema.sql file should exist")

    def test_schema_creates_valid_database(self) -> None:
        """Test that the schema can be executed to create a valid SQLite database."""
        self._load_schema()
        # Verify database is valid by executing a simple query
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            self.assertIn('items', tables)

    def test_items_table_has_required_columns(self) -> None:
        """Test that items table has all required columns."""
        self._load_schema()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(items)")
            columns = {row[1]: row for row in cursor.fetchall()}

            # Check all required columns exist
            required_columns = ['id', 'name', 'price', 'url', 'scraped_at']
            for col in required_columns:
                self.assertIn(col, columns, f"Column {col} should exist")

            # Check column types and constraints
            # id: INTEGER PRIMARY KEY AUTOINCREMENT
            self.assertEqual(columns['id'][2], 'INTEGER')
            self.assertEqual(columns['id'][5], 1)  # primary key

            # name: TEXT NOT NULL
            self.assertEqual(columns['name'][2], 'TEXT')
            self.assertEqual(columns['name'][3], 1)  # not null

            # price: REAL
            self.assertEqual(columns['price'][2], 'REAL')
            self.assertEqual(columns['price'][3], 0)  # nullable

            # url: TEXT
            self.assertEqual(columns['url'][2], 'TEXT')
            self.assertEqual(columns['url'][3], 0)  # nullable

            # scraped_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            self.assertEqual(columns['scraped_at'][2], 'TIMESTAMP')
            self.assertEqual(columns['scraped_at'][4], 'CURRENT_TIMESTAMP')

    def test_items_url_index_exists(self) -> None:
        """Test that idx_items_url index exists for duplicate detection."""
        self._load_schema()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_items_url'"
            )
            index = cursor.fetchone()
            self.assertIsNotNone(index, "idx_items_url index should exist")

    def test_items_table_accepts_valid_data(self) -> None:
        """Test that the items table can accept valid insert statements."""
        self._load_schema()
        with sqlite3.connect(self.db_path) as conn:
            # Insert minimal valid data (name is required)
            conn.execute(
                "INSERT INTO items (name) VALUES (?)",
                ("Test Item",)
            )

            # Insert full data
            conn.execute(
                "INSERT INTO items (name, price, url) VALUES (?, ?, ?)",
                ("Another Item", 19.99, "http://example.com/item/1")
            )

            conn.commit()

            cursor = conn.execute("SELECT * FROM items ORDER BY id")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 2)

            # Check first row (minimal)
            self.assertEqual(rows[0][1], "Test Item")  # name
            self.assertIsNone(rows[0][2])  # price
            self.assertIsNone(rows[0][3])  # url
            self.assertIsNotNone(rows[0][4])  # scraped_at (auto-generated)

            # Check second row (full)
            self.assertEqual(rows[1][1], "Another Item")  # name
            self.assertEqual(rows[1][2], 19.99)  # price
            self.assertEqual(rows[1][3], "http://example.com/item/1")  # url

    def test_items_table_rejects_null_name(self) -> None:
        """Test that the items table rejects NULL name values."""
        self._load_schema()
        with sqlite3.connect(self.db_path) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO items (name, price) VALUES (?, ?)",
                    (None, 10.00)
                )


if __name__ == '__main__':
    unittest.main()
