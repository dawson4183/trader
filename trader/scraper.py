"""Scraper module with status tracking.

Provides a Scraper class that tracks its runs and status in the database,
providing foundation for scraper status checks and health monitoring.

Also includes scraper_retry decorator with exponential backoff for network operations.
"""

import functools
import time
import urllib.error
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from trader.database import DatabaseConnection
from trader.schema import create_tables

F = TypeVar("F", bound=Callable[..., Any])

# Network-related exceptions that trigger retry
NETWORK_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    urllib.error.HTTPError,
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    ConnectionRefusedError,
    ConnectionResetError,
    ConnectionAbortedError,
)


def scraper_retry(
    func: Optional[F] = None,
    *,
    max_attempts: int = 5,
    initial_delay: float = 10.0,
    max_delay: float = 240.0,
    backoff_multiplier: float = 2.0,
) -> Union[F, Callable[[F], F]]:
    """Retry decorator with exponential backoff for scraper network operations.

    Specialized retry decorator with specific parameters:
    - 5 max attempts
    - 10 second initial delay
    - 240 second maximum delay cap
    - 2.0 exponential backoff multiplier
    - Catches only network-related exceptions

    Args:
        func: The function to decorate (for bare decorator usage).
        max_attempts: Maximum number of retry attempts. Defaults to 5.
        initial_delay: Initial delay between retries in seconds. Defaults to 10.
        max_delay: Maximum delay cap between retries in seconds. Defaults to 240.
        backoff_multiplier: Multiplier for delay after each retry. Defaults to 2.0.

    Returns:
        Decorated function with retry logic.

    Example:
        >>> @scraper_retry
        ... def fetch_data(url: str) -> str:
        ...     return requests.get(url).text
        >>>
        >>> @scraper_retry(max_attempts=3)
        ... def fetch_with_custom_attempts(url: str) -> str:
        ...     return requests.get(url).text

    """

    def decorator(wrapped_func: F) -> F:
        @functools.wraps(wrapped_func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = initial_delay
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return wrapped_func(*args, **kwargs)
                except NETWORK_EXCEPTIONS as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay = min(
                            current_delay * backoff_multiplier, max_delay
                        )

            # All retries exhausted - re-raise the last exception
            if last_exception is not None:
                raise last_exception

            raise RuntimeError(f"Function failed after {max_attempts} attempts")

        return wrapper  # type: ignore

    if func is None:
        return decorator
    return decorator(func)

StatusType = Literal["idle", "running", "error"]
RunStatusType = Literal["running", "completed", "failed"]
FailureLevelType = Literal["warning", "error", "critical"]


class Scraper:
    """Scraper class that tracks runs and status in the database.

    This class provides methods to track scraper runs, record failures,
    and check the current status of the scraper.

    Args:
        db: DatabaseConnection instance. If not provided, a new
            in-memory connection is created.

    Attributes:
        db: The DatabaseConnection instance used for operations.
        current_run_id: The ID of the currently active run, or None if idle.
    """

    def __init__(self, db: Optional[DatabaseConnection] = None) -> None:
        """Initialize Scraper with database connection.

        Args:
            db: Optional DatabaseConnection instance. If not provided,
                a new in-memory connection is created.
        """
        if db is None:
            db = DatabaseConnection()
        self.db: DatabaseConnection = db
        self.current_run_id: Optional[int] = None
        # Ensure tables exist
        create_tables(self.db)

    def start_run(self) -> int:
        """Start a new scraper run.

        Creates an entry in the scraper_runs table with 'running' status.
        If a run is already active, it will be tracked.

        Returns:
            The ID of the created run record.

        Raises:
            RuntimeError: If a run is already in progress.
        """
        if self.current_run_id is not None:
            raise RuntimeError(
                f"Run {self.current_run_id} is already in progress. "
                "Call end_run() before starting a new run."
            )

        self.db.execute(
            "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
            ("running", 0)
        )

        # Get the ID of the inserted row
        row_result = self.db.execute(
            "SELECT id FROM scraper_runs WHERE status = ? ORDER BY started_at DESC LIMIT 1",
            ("running",)
        )

        self.current_run_id = row_result[0]["id"]
        return self.current_run_id

    def end_run(
        self,
        status: RunStatusType,
        items_count: int = 0
    ) -> None:
        """End the current scraper run.

        Updates the run record with completion status and item count.

        Args:
            status: The completion status ('completed' or 'failed').
            items_count: Number of items scraped during the run.

        Raises:
            RuntimeError: If no run is currently in progress.
            ValueError: If status is 'running' (cannot end with running status).
        """
        if self.current_run_id is None:
            raise RuntimeError("No run is currently in progress. Call start_run() first.")

        if status == "running":
            raise ValueError("Cannot end a run with 'running' status. Use 'completed' or 'failed'.")

        self.db.execute(
            """UPDATE scraper_runs
               SET status = ?, items_count = ?, ended_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status, items_count, self.current_run_id)
        )

        self.current_run_id = None

    def record_failure(
        self,
        error_message: str,
        level: FailureLevelType = "error"
    ) -> int:
        """Record a failure during a scraper run.

        Inserts a record into the scraper_failures table. If no run is
        active, creates a placeholder run to associate with the failure.

        Args:
            error_message: Description of the error that occurred.
            level: Severity level ('warning', 'error', or 'critical').

        Returns:
            The ID of the created failure record.
        """
        # If no active run, create a failed run to associate with
        if self.current_run_id is None:
            # Create a failed run record
            self.db.execute(
                "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
                ("failed", 0)
            )
            row_result = self.db.execute(
                "SELECT id FROM scraper_runs ORDER BY started_at DESC LIMIT 1"
            )
            run_id = row_result[0]["id"]
        else:
            run_id = self.current_run_id

        self.db.execute(
            """INSERT INTO scraper_failures (run_id, error_message, level)
               VALUES (?, ?, ?)""",
            (run_id, error_message, level)
        )

        # Get the ID of the inserted failure
        failure_result = self.db.execute(
            """SELECT id FROM scraper_failures
               WHERE run_id = ? ORDER BY occurred_at DESC LIMIT 1""",
            (run_id,)
        )

        failure_id: int = failure_result[0]["id"]
        return failure_id

    def get_status(self) -> StatusType:
        """Get the current status of the scraper.

        Returns the current status based on active runs and recent failures.

        Returns:
            'idle' if no run is active and no recent errors,
            'running' if a run is currently in progress,
            'error' if there are recent failures or the last run failed.
        """
        # Check if we have an active run in memory
        if self.current_run_id is not None:
            return "running"

        # Check database for any running runs
        running_runs = self.db.execute(
            "SELECT id FROM scraper_runs WHERE status = ?",
            ("running",)
        )

        if running_runs:
            # There's a run marked as running in the database
            self.current_run_id = running_runs[0]["id"]
            return "running"

        # Check for recent failures (last 24 hours)
        recent_failures = self.db.execute(
            """SELECT COUNT(*) as count FROM scraper_failures
               WHERE occurred_at > datetime('now', '-1 day')"""
        )

        if recent_failures and recent_failures[0]["count"] > 0:
            return "error"

        # Check if the most recent run failed
        last_run = self.db.execute(
            """SELECT status FROM scraper_runs
               ORDER BY started_at DESC LIMIT 1"""
        )

        if last_run and last_run[0]["status"] == "failed":
            return "error"

        return "idle"

    def get_current_run_id(self) -> Optional[int]:
        """Get the ID of the currently active run.

        Returns:
            The ID of the active run, or None if no run is in progress.
        """
        return self.current_run_id

    def get_run_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the history of scraper runs.

        Args:
            limit: Maximum number of runs to return.

        Returns:
            List of run records as dictionaries.
        """
        results = self.db.execute(
            """SELECT id, started_at, ended_at, status, items_count
               FROM scraper_runs
               ORDER BY started_at DESC
               LIMIT ?""",
            (limit,)
        )
        return results

    def get_recent_failures(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent scraper failures.

        Args:
            limit: Maximum number of failures to return.

        Returns:
            List of failure records as dictionaries.
        """
        results = self.db.execute(
            """SELECT id, run_id, error_message, level, occurred_at
               FROM scraper_failures
               ORDER BY occurred_at DESC
               LIMIT ?""",
            (limit,)
        )
        return results
