"""Scraper module with status tracking.

Provides a Scraper class that tracks its runs and status in the database,
providing foundation for scraper status checks and health monitoring.

Also includes scraper_retry decorator with exponential backoff for network operations.
"""

import functools
import logging
import time
import traceback
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
        self._alert_sent: bool = False
        self._alert_module: Optional[Any] = None
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

    def import_alert_module(self) -> Optional[Any]:
        """Lazily import the alert module to avoid circular imports.

        Returns:
            The alert module if available, None otherwise.
        """
        if self._alert_module is None:
            try:
                from trader import alert as alert_mod
                self._alert_module = alert_mod
            except ImportError:
                return None
        return self._alert_module

    def send_critical_alert(self, message: str) -> bool:
        """Send a critical level alert via the alert module.

        Tracks that an alert was sent to avoid duplicate alerts.
        Uses lazy import to avoid circular dependency issues.

        Args:
            message: The alert message to send.

        Returns:
            True if alert was sent successfully, False otherwise.
        """
        # Avoid duplicate alerts
        if self._alert_sent:
            return False

        alert_mod = self.import_alert_module()
        if alert_mod is None:
            return False

        try:
            # Check if send_alert function exists
            if not hasattr(alert_mod, 'send_alert'):
                return False

            result = alert_mod.send_alert(message, "critical")
            if result:
                self._alert_sent = True
            return result
        except Exception:
            # Alert sending failed, but we don't want to break the scraper
            return False

    def scrape(self) -> Optional[int]:
        """Run the scraper with alert integration for critical failures.

        Starts a run, executes scraping work, and handles exceptions
        by sending critical alerts before re-raising. Records failures
        in the database and ensures proper cleanup.

        Returns:
            Number of items scraped, or None if no work done.

        Raises:
            Exception: Re-raises any exception after sending alert.
        """
        items_count = 0
        try:
            self.start_run()
            # Scraping work would go here - placeholder
            # Items would be scraped and counted
            items_count = self._do_scrape()
            self.end_run("completed", items_count)
            return items_count
        except Exception as e:
            # Get error message and stack trace excerpt
            error_msg = str(e)
            tb_str = traceback.format_exc(limit=5)  # Limit to 5 frames

            # Build alert message
            alert_msg = f"Scraper failed with error: {error_msg}\n\nStack trace:\n{tb_str}"

            # Record failure in database
            self.record_failure(error_msg, "critical")

            # Send critical alert before re-raising
            # If alert fails, log the error but still propagate exception
            try:
                alert_sent = self.send_critical_alert(alert_msg)
                if not alert_sent:
                    logging.getLogger(__name__).warning(
                        "Failed to send critical alert for scraper failure"
                    )
            except Exception as alert_err:
                logging.getLogger(__name__).error(
                    "Error sending alert: %s", alert_err
                )

            # Ensure run is marked as failed
            try:
                if self.current_run_id is not None:
                    self.end_run("failed", items_count)
            except Exception:
                pass  # Best effort cleanup

            # Re-raise the original exception
            raise

    def _do_scrape(self) -> int:
        """Placeholder for actual scraping work.

        This method should be overridden or replaced with actual
        scraping logic. Returns the number of items scraped.

        Returns:
            Number of items scraped.
        """
        # Placeholder - no actual scraping work
        return 0

    def reset_alert_flag(self) -> None:
        """Reset the alert sent flag for testing purposes.

        Allows tests to reset the alert tracking state between runs.
        """
        self._alert_sent = False


# Circuit Breaker Implementation - Story 3
import threading

from trader.exceptions import CircuitOpenError

T = TypeVar("T")

CircuitStateType = Literal["CLOSED", "OPEN", "HALF_OPEN"]


class CircuitBreaker:
    """Circuit breaker pattern implementation for resilient scraper operations.
    
    Implements the circuit breaker pattern with three states:
    - CLOSED: Normal operation, circuit allows calls through
    - OPEN: Too many failures, circuit rejects all calls immediately
    - HALF_OPEN: Recovery test mode, allows one test call to check health
    
    Transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After recovery_timeout seconds have passed
    - HALF_OPEN -> CLOSED: If the test call succeeds
    - HALF_OPEN -> OPEN: If the test call fails
    
    Thread-safe using threading.Lock for all state modifications.
    
    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit.
            Defaults to 10.
        recovery_timeout: Seconds to wait before testing recovery.
            Defaults to 60.
        current_state: Current state of the circuit.
        failure_count: Current number of consecutive failures.
        last_failure_time: Timestamp of the last failure, or None.
    """
    
    def __init__(
        self,
        failure_threshold: int = 10,
        recovery_timeout: float = 60.0,
    ) -> None:
        """Initialize the circuit breaker."""
        self.failure_threshold: int = failure_threshold
        self.recovery_timeout: float = recovery_timeout
        
        # Circuit state
        self._state: CircuitStateType = "CLOSED"
        self._failure_count: int = 0
        self._last_failure_time: Optional[float] = None
        
        # Thread safety
        self._lock: threading.Lock = threading.Lock()
    
    @property
    def current_state(self) -> CircuitStateType:
        """Get the current state of the circuit breaker."""
        with self._lock:
            return self._state
    
    @property
    def failure_count(self) -> int:
        """Get the current failure count."""
        with self._lock:
            return self._failure_count
    
    @property
    def last_failure_time(self) -> Optional[float]:
        """Get the timestamp of the last failure."""
        with self._lock:
            return self._last_failure_time
    
    def _can_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout
    
    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        self._state = "OPEN"
        self._last_failure_time = time.time()
    
    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        self._state = "HALF_OPEN"
    
    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        self._state = "CLOSED"
        self._failure_count = 0
        self._last_failure_time = None
    
    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            if self._state == "CLOSED":
                self._failure_count = 0
            elif self._state == "HALF_OPEN":
                self._transition_to_closed()
    
    def record_failure(self) -> None:
        """Record a failed operation and update circuit state."""
        with self._lock:
            if self._state == "CLOSED":
                self._failure_count += 1
                self._last_failure_time = time.time()
                if self._failure_count >= self.failure_threshold:
                    self._transition_to_open()
            elif self._state == "HALF_OPEN":
                self._failure_count += 1
                self._transition_to_open()
    
    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._state = "CLOSED"
            self._failure_count = 0
            self._last_failure_time = None
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with circuit breaker protection."""
        with self._lock:
            if self._state == "OPEN":
                if self._can_attempt_recovery():
                    self._transition_to_half_open()
                else:
                    raise CircuitOpenError(
                        f"Circuit breaker is OPEN after {self._failure_count} failures. "
                        f"Retry after {self.recovery_timeout} seconds."
                    )
            # HALF_OPEN and CLOSED states allow calls through
        
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise
