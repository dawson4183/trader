"""Tests for the Transaction context manager."""

import sqlite3
import tempfile
import unittest

from trader.database import ConnectionPool, Transaction


class TestTransaction(unittest.TestCase):
    """Test cases for Transaction class."""
    
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


if __name__ == '__main__':
    unittest.main()