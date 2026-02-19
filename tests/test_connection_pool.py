"""Tests for the ConnectionPool class."""

import os
import sqlite3
import tempfile
import threading
import unittest

from trader.database import ConnectionPool, get_connection


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


if __name__ == '__main__':
    unittest.main()
