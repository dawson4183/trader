"""Scraper module with status tracking and alerting.

Provides a Scraper class that tracks its execution status in the database
and sends alerts on critical failures.
"""

from typing import Any, Optional

from trader.database import DatabaseConnection
from trader.schema import create_tables


class Scraper:
    """Scraper with database-backed status tracking.

    This class handles web scraping with automatic tracking of
    execution runs and failures in the database.

    Attributes:
        db_path: Path to the SQLite database file.
        _current_run_id: ID of the current scraper run (if active).
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        """Initialize Scraper with database path.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._current_run_id: Optional[int] = None

    def _get_db(self) -> DatabaseConnection:
        """Get a database connection with tables created."""
        db = DatabaseConnection(self.db_path)
        create_tables(db)
        return db

    def start_run(self) -> int:
        """Start a new scraper run and return its ID.

        Returns:
            The ID of the newly created run.
        """
        db = self._get_db()
        db.execute(
            "INSERT INTO scraper_runs (status, items_count) VALUES ('running', 0)"
        )
        result = db.execute("SELECT last_insert_rowid() as id")
        self._current_run_id = result[0]["id"]
        db.close()
        return self._current_run_id

    def end_run(self, status: str = "completed", items_count: int = 0) -> None:
        """End the current scraper run.

        Args:
            status: Final status ('completed' or 'failed').
            items_count: Number of items scraped.
        """
        if self._current_run_id is None:
            return

        db = self._get_db()
        db.execute(
            """UPDATE scraper_runs 
               SET status = ?, items_count = ?, ended_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, items_count, self._current_run_id),
        )
        db.close()
        self._current_run_id = None

    def record_failure(self, error_message: str, level: str = "error") -> None:
        """Record a failure during scraping.

        Args:
            error_message: The error message.
            level: Failure level ('warning', 'error', or 'critical').
        """
        # Ensure we have a run to associate with
        if self._current_run_id is None:
            self.start_run()

        db = self._get_db()
        db.execute(
            """INSERT INTO scraper_failures (run_id, error_message, level)
               VALUES (?, ?, ?)""",
            (self._current_run_id, error_message, level),
        )
        db.close()

        # Send alert for critical failures
        if level == "critical":
            self._send_critical_alert(error_message)

    def _send_critical_alert(self, error_message: str) -> None:
        """Send a critical alert notification.

        Args:
            error_message: The error message to include in the alert.
        """
        try:
            from trader.alert import send_alert
            send_alert(f"Critical scraper failure: {error_message}", "critical")
        except Exception:
            pass  # Don't let alert failures break the scraper

    def get_status(self) -> str:
        """Get the current status of the scraper.

        Returns:
            'running', 'idle', 'error', or 'completed'.
        """
        db = self._get_db()

        # Check if there's a currently running scraper
        result = db.execute(
            """SELECT status FROM scraper_runs
               ORDER BY started_at DESC
               LIMIT 1"""
        )
        db.close()

        if not result:
            return "idle"

        return result[0]["status"]

    def get_current_run_id(self) -> Optional[int]:
        """Get the ID of the current scraper run.

        Returns:
            The run ID if a run is active, None otherwise.
        """
        return self._current_run_id

    def get_run_history(self, limit: int = 10) -> list:
        """Get the history of scraper runs.

        Args:
            limit: Maximum number of runs to return.

        Returns:
            List of run records.
        """
        db = self._get_db()
        result = db.execute(
            """SELECT * FROM scraper_runs
               ORDER BY started_at DESC
               LIMIT ?""",
            (limit,),
        )
        db.close()
        return result

    def get_recent_failures(self, limit: int = 10) -> list:
        """Get recent failures.

        Args:
            limit: Maximum number of failures to return.

        Returns:
            List of failure records.
        """
        db = self._get_db()
        result = db.execute(
            """SELECT * FROM scraper_failures
               ORDER BY occurred_at DESC
               LIMIT ?""",
            (limit,),
        )
        db.close()
        return result
