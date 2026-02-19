"""Database connection management module.

Provides a DatabaseConnection class for SQLite database operations
with context manager support.
"""

import sqlite3
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager


class DatabaseConnection:
    """Manages SQLite database connections.

    This class provides a high-level interface for SQLite database operations
    with support for connection pooling and context manager protocol.

    Args:
        db_path: Path to the SQLite database file. Defaults to ":memory:".
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize DatabaseConnection with database path.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Create and return a database connection.

        Returns:
            A valid sqlite3 connection object.

        Raises:
            sqlite3.Error: If connection fails.
        """
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            # Enable row factory for dictionary-like access
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def close(self) -> None:
        """Close the database connection.

        This method safely closes the connection if it exists.
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def execute(
        self,
        query: str,
        parameters: Optional[Union[tuple, Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results.

        Args:
            query: The SQL query to execute.
            parameters: Optional parameters for parameterized queries.

        Returns:
            A list of dictionaries containing query results.

        Raises:
            sqlite3.Error: If query execution fails.
        """
        conn = self.connect()
        cursor = conn.cursor()

        if parameters is None:
            cursor.execute(query)
        else:
            cursor.execute(query, parameters)

        # Fetch results if it's a SELECT query
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
        else:
            conn.commit()
            result = []

        cursor.close()
        return result

    def __enter__(self) -> "DatabaseConnection":
        """Enter context manager.

        Returns:
            The DatabaseConnection instance with active connection.
        """
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ) -> None:
        """Exit context manager and close connection.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        self.close()

    def is_connected(self) -> bool:
        """Check if database connection is active.

        Returns:
            True if connection exists, False otherwise.
        """
        return self._connection is not None


def get_connection(db_path: str = ":memory:") -> DatabaseConnection:
    """Factory function to create a DatabaseConnection.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A new DatabaseConnection instance.
    """
    return DatabaseConnection(db_path)
