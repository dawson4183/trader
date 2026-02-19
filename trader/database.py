"""Database module with connection pooling for SQLite."""

import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator, Optional, Set


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
