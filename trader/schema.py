"""Database schema module for creating and managing tables.

Provides functions to create the necessary database tables for the trader
application including scraper runs and failures tracking.
"""

from trader.database import DatabaseConnection


def create_tables(db: DatabaseConnection) -> None:
    """Create all required database tables.

    Creates the following tables if they don't exist:
    - scraper_runs: Tracks scraper execution runs
    - scraper_failures: Records failures during scraping

    Args:
        db: DatabaseConnection instance to use.
    """
    # Create scraper_runs table
    db.execute(
        """CREATE TABLE IF NOT EXISTS scraper_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL DEFAULT 'running',
            items_count INTEGER DEFAULT 0,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ended_at TEXT
        )"""
    )

    # Create scraper_failures table
    db.execute(
        """CREATE TABLE IF NOT EXISTS scraper_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            error_message TEXT NOT NULL,
            level TEXT NOT NULL DEFAULT 'error',
            occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES scraper_runs(id)
        )"""
    )


def drop_tables(db: DatabaseConnection) -> None:
    """Drop all application tables.

    Args:
        db: DatabaseConnection instance to use.
    """
    db.execute("DROP TABLE IF EXISTS scraper_failures")
    db.execute("DROP TABLE IF EXISTS scraper_runs")
