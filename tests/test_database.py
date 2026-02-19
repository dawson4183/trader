"""Tests for trader database module."""
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from trader.database import DatabaseConnection, get_connection


class TestDatabaseConnection:
    """Test cases for DatabaseConnection class."""

    def test_database_connection_class_exists(self) -> None:
        """Verify DatabaseConnection class exists."""
        assert DatabaseConnection is not None
        assert callable(DatabaseConnection)

    def test_database_connection_init_with_default_path(self) -> None:
        """Verify DatabaseConnection initializes with default in-memory path."""
        db = DatabaseConnection()
        assert db.db_path == ":memory:"
        assert db._connection is None

    def test_database_connection_init_with_custom_path(self) -> None:
        """Verify DatabaseConnection initializes with custom path."""
        custom_path = "/tmp/test.db"
        db = DatabaseConnection(custom_path)
        assert db.db_path == custom_path
        assert db._connection is None

    def test_connect_returns_valid_connection(self) -> None:
        """Verify connect() returns a valid sqlite3 connection."""
        db = DatabaseConnection()
        conn = db.connect()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        db.close()

    def test_connect_same_connection_on_multiple_calls(self) -> None:
        """Verify connect() returns same connection on multiple calls."""
        db = DatabaseConnection()
        conn1 = db.connect()
        conn2 = db.connect()
        assert conn1 is conn2
        db.close()

    def test_close_properly_closes_connection(self) -> None:
        """Verify close() properly closes the connection."""
        db = DatabaseConnection()
        db.connect()
        assert db._connection is not None
        db.close()
        assert db._connection is None

    def test_close_on_unconnected_db_is_safe(self) -> None:
        """Verify close() is safe to call when not connected."""
        db = DatabaseConnection()
        db.close()  # Should not raise
        assert db._connection is None

    def test_execute_select_query(self) -> None:
        """Verify execute() runs SELECT queries and returns results."""
        db = DatabaseConnection()
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO test (name) VALUES ('Alice')")
        db.execute("INSERT INTO test (name) VALUES ('Bob')")

        results = db.execute("SELECT * FROM test ORDER BY id")

        assert len(results) == 2
        assert results[0]["id"] == 1
        assert results[0]["name"] == "Alice"
        assert results[1]["id"] == 2
        assert results[1]["name"] == "Bob"
        db.close()

    def test_execute_with_parameters(self) -> None:
        """Verify execute() supports parameterized queries."""
        db = DatabaseConnection()
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO test (name) VALUES (?)", ("Charlie",))

        results = db.execute("SELECT * FROM test WHERE name = ?", ("Charlie",))

        assert len(results) == 1
        assert results[0]["name"] == "Charlie"
        db.close()

    def test_execute_with_dict_parameters(self) -> None:
        """Verify execute() supports dictionary parameters."""
        db = DatabaseConnection()
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO test (name) VALUES (:name)", {"name": "David"})

        results = db.execute("SELECT * FROM test WHERE name = :name", {"name": "David"})

        assert len(results) == 1
        assert results[0]["name"] == "David"
        db.close()

    def test_execute_insert_returns_empty_list(self) -> None:
        """Verify execute() returns empty list for INSERT queries."""
        db = DatabaseConnection()
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        result = db.execute("INSERT INTO test (name) VALUES ('Eve')")

        assert result == []
        db.close()

    def test_execute_update_returns_empty_list(self) -> None:
        """Verify execute() returns empty list for UPDATE queries."""
        db = DatabaseConnection()
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO test (name) VALUES ('Frank')")
        result = db.execute("UPDATE test SET name = 'Updated' WHERE id = 1")

        assert result == []
        db.close()

    def test_execute_delete_returns_empty_list(self) -> None:
        """Verify execute() returns empty list for DELETE queries."""
        db = DatabaseConnection()
        db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        db.execute("INSERT INTO test (name) VALUES ('Grace')")
        result = db.execute("DELETE FROM test WHERE id = 1")

        assert result == []
        db.close()

    def test_context_manager_enters_with_connection(self) -> None:
        """Verify __enter__ returns DatabaseConnection with active connection."""
        with DatabaseConnection() as db:
            assert isinstance(db, DatabaseConnection)
            assert db._connection is not None
            assert isinstance(db._connection, sqlite3.Connection)

    def test_context_manager_exits_closes_connection(self) -> None:
        """Verify __exit__ closes the connection."""
        db = DatabaseConnection()
        with db:
            db.connect()
            assert db._connection is not None
        assert db._connection is None

    def test_context_manager_closes_on_exception(self) -> None:
        """Verify connection is closed even when exception occurs in context."""
        db = DatabaseConnection()
        try:
            with db:
                db.connect()
                raise ValueError("Test exception")
        except ValueError:
            pass
        assert db._connection is None

    def test_is_connected_returns_false_initially(self) -> None:
        """Verify is_connected() returns False before connect()."""
        db = DatabaseConnection()
        assert not db.is_connected()

    def test_is_connected_returns_true_after_connect(self) -> None:
        """Verify is_connected() returns True after connect()."""
        db = DatabaseConnection()
        db.connect()
        assert db.is_connected()
        db.close()

    def test_is_connected_returns_false_after_close(self) -> None:
        """Verify is_connected() returns False after close()."""
        db = DatabaseConnection()
        db.connect()
        db.close()
        assert not db.is_connected()

    def test_execute_persists_data_to_file(self) -> None:
        """Verify data persists when using file-based database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # First connection - create table and insert data
            db1 = DatabaseConnection(db_path)
            db1.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT)")
            db1.execute("INSERT INTO items (value) VALUES ('persistent')")
            db1.close()

            # Second connection - verify data exists
            db2 = DatabaseConnection(db_path)
            results = db2.execute("SELECT * FROM items")
            assert len(results) == 1
            assert results[0]["value"] == "persistent"
            db2.close()
        finally:
            os.unlink(db_path)

    def test_execute_raises_on_invalid_query(self) -> None:
        """Verify execute() raises sqlite3.Error on invalid query."""
        db = DatabaseConnection()
        with pytest.raises(sqlite3.Error):
            db.execute("INVALID SQL SYNTAX")
        db.close()


class TestGetConnection:
    """Test cases for get_connection factory function."""

    def test_get_connection_returns_database_connection(self) -> None:
        """Verify get_connection() returns a DatabaseConnection instance."""
        db = get_connection()
        assert isinstance(db, DatabaseConnection)

    def test_get_connection_uses_memory_by_default(self) -> None:
        """Verify get_connection() uses :memory: path by default."""
        db = get_connection()
        assert db.db_path == ":memory:"

    def test_get_connection_accepts_custom_path(self) -> None:
        """Verify get_connection() accepts custom database path."""
        custom_path = "/custom/path.db"
        db = get_connection(custom_path)
        assert db.db_path == custom_path

    def test_get_connection_functional(self) -> None:
        """Verify get_connection() returns functional connection."""
        db = get_connection()
        conn = db.connect()
        assert isinstance(conn, sqlite3.Connection)
        db.close()
