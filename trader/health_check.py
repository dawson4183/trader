"""Health check module for monitoring system status.

Provides functions to check the health of various system components
including database connectivity, scraper status, and recent failures.
"""

import time
from typing import Dict, Any, Optional

from trader.database import DatabaseConnection


HealthStatusType = Dict[str, Any]


def check_database_connection(db_path: str = ":memory:") -> HealthStatusType:
    """Check database connectivity by executing a simple query.

    Executes a 'SELECT 1' query to verify the database is accessible
    and measures the response time.

    Args:
        db_path: Path to the SQLite database file. Defaults to in-memory.

    Returns:
        A dictionary containing:
            - 'status': 'ok' or 'error'
            - 'response_ms': Response time in milliseconds
            - 'error': Error message (only present if status is 'error')
    """
    return _check_database_connection_impl(db_path)


def _check_database_connection_impl(db_path: str) -> HealthStatusType:
    """Internal implementation for database connection check."""
    db = DatabaseConnection(db_path)
    
    try:
        start_time = time.perf_counter()
        result = db.execute("SELECT 1")
        end_time = time.perf_counter()
        
        # Calculate response time in milliseconds
        response_ms = round((end_time - start_time) * 1000, 3)
        
        if result and len(result) == 1 and result[0].get('1') == 1:
            return {
                "status": "ok",
                "response_ms": response_ms,
            }
        else:
            return {
                "status": "error",
                "response_ms": response_ms,
                "error": "Unexpected query result",
            }
    except Exception as e:
        return {
            "status": "error",
            "response_ms": 0.0,
            "error": str(e),
        }
    finally:
        db.close()