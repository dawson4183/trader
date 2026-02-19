"""Database schema management module.

Provides functions for creating and managing the database schema
for health tracking, scraper runs, and failures.
"""

import sqlite3
from typing import Any, Dict, List, Optional

from trader.database import DatabaseConnection


# SQL DDL for creating tables
CREATE_SCRAPER_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS scraper_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
    items_count INTEGER DEFAULT 0
)
"""

CREATE_SCRAPER_FAILURES_TABLE = """
CREATE TABLE IF NOT EXISTS scraper_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    error_message TEXT NOT NULL,
    level TEXT NOT NULL CHECK(level IN ('warning', 'error', 'critical')),
    occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES scraper_runs(id) ON DELETE CASCADE
)
"""

CREATE_HEALTH_CHECKS_TABLE = """
CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('healthy', 'unhealthy')),
    details TEXT,
    checked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

# Create index for faster queries
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_scraper_runs_status ON scraper_runs(status)",
    "CREATE INDEX IF NOT EXISTS idx_scraper_runs_started_at ON scraper_runs(started_at)",
    "CREATE INDEX IF NOT EXISTS idx_scraper_failures_run_id ON scraper_failures(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_scraper_failures_occurred_at ON scraper_failures(occurred_at)",
    "CREATE INDEX IF NOT EXISTS idx_health_checks_type ON health_checks(check_type)",
    "CREATE INDEX IF NOT EXISTS idx_health_checks_checked_at ON health_checks(checked_at)",
]


def create_tables(db: Optional[DatabaseConnection] = None) -> None:
    """Create all database tables if they don't exist.

    This function is idempotent - it can be safely called multiple times
    without causing errors. Tables are only created if they don't already exist.

    Args:
        db: Optional DatabaseConnection instance. If not provided, a new
            in-memory connection is created.

    Raises:
        sqlite3.Error: If table creation fails.
    """
    if db is None:
        db = DatabaseConnection()

    # Create tables
    db.execute(CREATE_SCRAPER_RUNS_TABLE)
    db.execute(CREATE_SCRAPER_FAILURES_TABLE)
    db.execute(CREATE_HEALTH_CHECKS_TABLE)

    # Create indexes for performance
    for index_sql in CREATE_INDEXES:
        db.execute(index_sql)


def drop_tables(db: Optional[DatabaseConnection] = None) -> None:
    """Drop all schema tables.

    WARNING: This will delete all data in the tables. Use with caution.

    Args:
        db: Optional DatabaseConnection instance. If not provided, a new
            in-memory connection is created.

    Raises:
        sqlite3.Error: If table drop fails.
    """
    if db is None:
        db = DatabaseConnection()

    db.execute("DROP TABLE IF EXISTS scraper_failures")
    db.execute("DROP TABLE IF EXISTS health_checks")
    db.execute("DROP TABLE IF EXISTS scraper_runs")


def table_exists(db: DatabaseConnection, table_name: str) -> bool:
    """Check if a table exists in the database.

    Args:
        db: DatabaseConnection instance.
        table_name: Name of the table to check.

    Returns:
        True if the table exists, False otherwise.
    """
    result = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return len(result) > 0


def get_table_schema(db: DatabaseConnection, table_name: str) -> List[Dict[str, Any]]:
    """Get the schema information for a table.

    Args:
        db: DatabaseConnection instance.
        table_name: Name of the table.

    Returns:
        List of column information dictionaries.
    """
    result = db.execute(f"PRAGMA table_info({table_name})")
    return result
