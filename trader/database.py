"""Database module with connection pooling for SQLite."""

import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Set, Tuple


class ConnectionPool:
    """A connection pool for SQLite databases with context manager support.
    
    The pool maintains a set of connections and enforces a maximum number
    of concurrent connections. Connections are acquired and released through
    context managers or explicit acquire/release methods.
    
    Attributes:
        db_path: Path to the SQLite database file.
        max_connections: Maximum number of concurrent connections allowed.
        active_connections: Set of currently active (checked out) connections.
    """
    
    def __init__(self, db_path: str, max_connections: int = 5) -> None:
        """Initialize the connection pool.
        
        Args:
            db_path: Path to the SQLite database file.
            max_connections: Maximum number of concurrent connections allowed.
        """
        self.db_path: str = db_path
        self.max_connections: int = max_connections
        self._available_connections: list[sqlite3.Connection] = []
        self._active_connections: Set[sqlite3.Connection] = set()
        self._lock = threading.Lock()
        self._closed = False
        self._thread_local = threading.local()
    
    @property
    def active_count(self) -> int:
        """Return the number of currently active connections."""
        with self._lock:
            return len(self._active_connections)
    
    @property
    def available_count(self) -> int:
        """Return the number of available connections in the pool."""
        with self._lock:
            return len(self._available_connections)
    
    def acquire(self) -> sqlite3.Connection:
        """Acquire a connection from the pool.
        
        Returns:
            An SQLite connection object.
            
        Raises:
            RuntimeError: If the pool is closed or max connections exceeded.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError("Connection pool is closed")
            
            # Check if we have available connections in the pool
            if self._available_connections:
                conn = self._available_connections.pop()
                self._active_connections.add(conn)
                return conn
            
            # Check if we can create a new connection
            total_connections = len(self._active_connections) + len(self._available_connections)
            if total_connections >= self.max_connections:
                raise RuntimeError(
                    f"Maximum connections ({self.max_connections}) exceeded"
                )
            
            # Create a new connection with thread-safety disabled
            # since we're managing connections via the pool's lock
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._active_connections.add(conn)
            return conn
    
    def release(self, conn: sqlite3.Connection) -> None:
        """Release a connection back to the pool.
        
        Args:
            conn: The connection to release.
            
        Raises:
            RuntimeError: If the pool is closed.
            ValueError: If the connection is not from this pool.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError("Connection pool is closed")
            
            if conn not in self._active_connections:
                raise ValueError("Connection is not from this pool or already released")
            
            self._active_connections.discard(conn)
            self._available_connections.append(conn)
    
    def __enter__(self) -> sqlite3.Connection:
        """Context manager entry - acquire a connection.
        
        Returns:
            An SQLite connection object.
        """
        conn = self.acquire()
        # Store the connection in thread-local for __exit__ to access
        self._thread_local.current_connection = conn
        return conn
    
    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object]
    ) -> None:
        """Context manager exit - release the connection.
        
        Args:
            exc_type: The exception type if an exception occurred.
            exc_val: The exception value if an exception occurred.
            exc_tb: The traceback if an exception occurred.
        """
        # Retrieve the connection from thread-local storage
        conn = getattr(self._thread_local, 'current_connection', None)
        if conn is not None:
            self.release(conn)
            delattr(self._thread_local, 'current_connection')
    
    def close(self) -> None:
        """Close all connections and shutdown the pool."""
        with self._lock:
            if self._closed:
                return
            
            self._closed = True
            
            # Close all active connections
            for conn in self._active_connections:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass  # Ignore errors during cleanup
            self._active_connections.clear()
            
            # Close all available connections
            for conn in self._available_connections:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass  # Ignore errors during cleanup
            self._available_connections.clear()
    
    def __del__(self) -> None:
        """Destructor to ensure connections are closed."""
        self.close()


@contextmanager
def get_connection(pool: ConnectionPool) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for getting a connection from the pool.
    
    Args:
        pool: The ConnectionPool to acquire from.
        
    Yields:
        An SQLite connection from the pool.
    """
    conn = pool.acquire()
    try:
        yield conn
    finally:
        pool.release(conn)


class Transaction:
    """Transaction context manager for database operations.
    
    Wraps database operations in transactions with automatic commit on
    success and rollback on exception. Works with connections from the
    connection pool.
    
    Example:
        pool = ConnectionPool("test.db")
        with pool:
            with Transaction(get_current_connection()):
                cursor.execute("INSERT INTO items ...")
    """
    
    def __init__(self, connection: sqlite3.Connection) -> None:
        """Initialize the transaction with a database connection.
        
        Args:
            connection: An active SQLite database connection.
        """
        self.connection: sqlite3.Connection = connection
        self.cursor: Optional[sqlite3.Cursor] = None
    
    def __enter__(self) -> sqlite3.Cursor:
        """Enter the transaction context and return a cursor.
        
        Returns:
            A cursor object for executing database operations.
        """
        self.cursor = self.connection.cursor()
        return self.cursor
    
    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object]
    ) -> None:
        """Exit the transaction context with commit/rollback.
        
        If no exception occurred, commits the transaction.
        If an exception occurred, rolls back the transaction and
        propagates the exception.
        
        Args:
            exc_type: The exception type if an exception occurred.
            exc_val: The exception value if an exception occurred.
            exc_tb: The traceback if an exception occurred.
        """
        try:
            if exc_type is None:
                # No exception - commit the transaction
                self.connection.commit()
            else:
                # Exception occurred - rollback the transaction
                self.connection.rollback()
        finally:
            # Clean up the cursor
            if self.cursor is not None:
                self.cursor.close()
                self.cursor = None


def insert_items_batch(
    pool: ConnectionPool,
    items: List[Dict[str, Any]],
    batch_size: int = 100
) -> Tuple[int, int]:
    """Insert items into the database in batches using INSERT OR IGNORE.

    Batches items into groups of specified size and inserts them into
    the items table. Uses INSERT OR IGNORE to handle duplicates without
    raising errors. Each batch is wrapped in a transaction.

    Args:
        pool: The ConnectionPool to use for database connections.
        items: List of item dictionaries with keys 'name', 'price', 'url'.
        batch_size: Number of items to insert per batch. Default is 100.

    Returns:
        A tuple of (inserted_count, duplicate_count) where:
        - inserted_count: Number of rows actually inserted
        - duplicate_count: Number of rows skipped due to duplicates
    """
    if not items:
        return (0, 0)

    total_inserted = 0
    total_duplicates = 0

    # Process items in batches
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        
        with pool as conn:
            with Transaction(conn) as cursor:
                # Build the INSERT OR IGNORE query with placeholders
                placeholders = ', '.join(['(?, ?, ?)'] * len(batch))
                query = f"INSERT OR IGNORE INTO items (name, price, url) VALUES {placeholders}"
                
                # Flatten the batch data into a single list of values
                values: List[Any] = []
                for item in batch:
                    values.append(item.get('name'))
                    values.append(item.get('price'))
                    values.append(item.get('url'))
                
                cursor.execute(query, values)
                batch_inserted = cursor.rowcount
                total_inserted += batch_inserted
                total_duplicates += len(batch) - batch_inserted

    return (total_inserted, total_duplicates)


class DatabaseManager:
    """High-level database manager with connection pooling and batch operations.

    The DatabaseManager encapsulates the ConnectionPool and provides
    convenience methods for common database operations. It integrates
    with StateManager for crash recovery during batch operations.

    Attributes:
        db_path: Path to the SQLite database file.
        max_connections: Maximum number of concurrent connections allowed.
        batch_size: Default batch size for batch insert operations.
        pool: The underlying ConnectionPool instance.
    """

    def __init__(
        self,
        db_path: str,
        max_connections: int = 5,
        batch_size: int = 100
    ) -> None:
        """Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file.
            max_connections: Maximum number of concurrent connections allowed.
            batch_size: Default batch size for batch insert operations.
        """
        self.db_path: str = db_path
        self.max_connections: int = max_connections
        self.batch_size: int = batch_size
        self._pool: ConnectionPool = ConnectionPool(db_path, max_connections)

    @property
    def connection_pool(self) -> ConnectionPool:
        """Return the underlying ConnectionPool instance."""
        return self._pool

    def insert_items_batch(
        self,
        items: List[Dict[str, Any]],
        batch_size: Optional[int] = None,
        state_manager: Optional[Any] = None
    ) -> Tuple[int, int]:
        """Insert items into the database in batches using INSERT OR IGNORE.

        Batches items into groups of specified size and inserts them into
        the items table. Uses INSERT OR IGNORE to handle duplicates without
        raising errors. Each batch is wrapped in a transaction.

        If state_manager is provided, it will be used for crash recovery:
        - State is saved before starting batch inserts
        - State is updated after each successful batch
        - State is saved on exception for crash recovery

        Args:
            items: List of item dictionaries with keys 'name', 'price', 'url'.
            batch_size: Number of items to insert per batch. Uses 
                instance default if None.
            state_manager: Optional StateManager for crash recovery. If
                provided, state will be saved before and during batch
                operations.

        Returns:
            A tuple of (inserted_count, duplicate_count) where:
            - inserted_count: Number of rows actually inserted
            - duplicate_count: Number of rows skipped due to duplicates
        """
        from .state import StateManager

        use_batch_size = batch_size if batch_size is not None else self.batch_size

        if not items:
            return (0, 0)

        # Save initial state if StateManager provided
        if state_manager is not None:
            state_manager.save()

        total_inserted = 0
        total_duplicates = 0

        try:
            # Process items in batches
            for i in range(0, len(items), use_batch_size):
                batch = items[i:i + use_batch_size]
                
                with self._pool as conn:
                    with Transaction(conn) as cursor:
                        # Build the INSERT OR IGNORE query with placeholders
                        placeholders = ', '.join(['(?, ?, ?)'] * len(batch))
                        query = f"INSERT OR IGNORE INTO items (name, price, url) VALUES {placeholders}"
                        
                        # Flatten the batch data into a single list of values
                        values: List[Any] = []
                        for item in batch:
                            values.append(item.get('name'))
                            values.append(item.get('price'))
                            values.append(item.get('url'))
                        
                        cursor.execute(query, values)
                        batch_inserted = cursor.rowcount
                        total_inserted += batch_inserted
                        total_duplicates += len(batch) - batch_inserted
                
                # Update state manager after each batch
                if state_manager is not None:
                    for _ in batch:
                        state_manager.record_item()

        except Exception:
            # Save state on crash for recovery
            if state_manager is not None:
                state_manager.save_on_crash()
            raise

        return (total_inserted, total_duplicates)

    def close(self) -> None:
        """Close the database manager and shutdown the connection pool."""
        self._pool.close()

    def __enter__(self) -> "DatabaseManager":
        """Context manager entry - return self."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object]
    ) -> None:
        """Context manager exit - close the pool."""
        self.close()

    def __del__(self) -> None:
        """Destructor to ensure the pool is closed."""
        self.close()
