"""Health check module for monitoring system status.

Provides functions to check the health of various system components
including database connectivity, scraper status, and recent failures.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Literal

from trader.database import DatabaseConnection


ScraperHealthStatusType = Literal["ok", "error", "idle"]
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


def check_scraper_status(db_path: str = ":memory:") -> Dict[str, Any]:
    """Check the current status of the scraper and determine if it's healthy.

    Fetches the most recent scraper run from the database and analyzes
    the run history to determine if the scraper is functioning properly.
    Returns 'error' status if there are too many consecutive failures,
    'idle' if no runs in the last 24 hours, or 'ok' if running normally.

    Args:
        db_path: Path to the SQLite database file. Defaults to in-memory.

    Returns:
        A dictionary containing:
            - 'status': 'ok', 'error', or 'idle'
            - 'last_run_at': Timestamp of the most recent run (ISO format) or None
            - 'last_run_status': Status of the most recent run ('running', 'completed', 'failed') or None
            - 'consecutive_failures': Number of consecutive failed runs in last 5 runs
    """
    return _check_scraper_status_impl(db_path)


def _check_scraper_status_impl(db_path: str) -> Dict[str, Any]:
    """Internal implementation for scraper status check."""
    from trader.schema import create_tables
    
    db = DatabaseConnection(db_path)

    try:
        # Ensure tables exist
        create_tables(db)
        
        # Get the most recent scraper run
        latest_run_result = db.execute(
            """SELECT started_at, status
               FROM scraper_runs
               ORDER BY started_at DESC
               LIMIT 1"""
        )

        # Get last 5 runs to count consecutive failures (starting from most recent)
        recent_runs = db.execute(
            """SELECT status
               FROM scraper_runs
               ORDER BY started_at DESC
               LIMIT 5"""
        )

        # Calculate consecutive failures from the start (most recent runs)
        consecutive_failures = 0
        for run in recent_runs:
            if run["status"] == "failed":
                consecutive_failures += 1
            else:
                # Stop counting when we hit a non-failed run
                break

        # Determine last run info
        last_run_at: Optional[str] = None
        last_run_status: Optional[str] = None

        if latest_run_result:
            last_run_at = latest_run_result[0]["started_at"]
            last_run_status = latest_run_result[0]["status"]

        # Determine overall status
        status: ScraperHealthStatusType = "ok"

        # Check for error status (3+ consecutive failures) first - takes precedence
        if consecutive_failures >= 3:
            status = "error"
        elif last_run_at:
            # Check for idle status (no runs in last 24 hours)
            # SQLite returns timestamps in 'YYYY-%m-%d %H:%M:%S' format (no timezone info)
            try:
                last_run_time = datetime.strptime(last_run_at, "%Y-%m-%d %H:%M:%S")
                # Make it timezone-aware (assume UTC)
                last_run_time = last_run_time.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - last_run_time > timedelta(hours=24):
                    status = "idle"
            except (ValueError, AttributeError):
                # If we can't parse, check if it's ISO format
                try:
                    last_run_time = datetime.fromisoformat(last_run_at.replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) - last_run_time > timedelta(hours=24):
                        status = "idle"
                except (ValueError, AttributeError):
                    # If we can't parse, assume idle
                    status = "idle"
        else:
            # No runs at all
            status = "idle"

        return {
            "status": status,
            "last_run_at": last_run_at,
            "last_run_status": last_run_status,
            "consecutive_failures": consecutive_failures,
        }

    except Exception as e:
        return {
            "status": "error",
            "last_run_at": None,
            "last_run_status": None,
            "consecutive_failures": 0,
            "error": str(e),
        }

    finally:
        db.close()


def check_recent_failures(db_path: str = ":memory:") -> Dict[str, Any]:
    """Check for recent failures in the last 24 hours and summarize them.

    Queries the scraper_failures table for failures that occurred within
    the last 24 hours, groups them by message pattern (first 50 characters),
    and returns a summary including total counts and top error patterns.

    Args:
        db_path: Path to the SQLite database file. Defaults to in-memory.

    Returns:
        A dictionary containing:
            - 'total_24h': Total number of failures in last 24 hours (int)
            - 'critical_24h': Number of critical-level failures (int)
            - 'warning_24h': Number of warning-level failures (int)
            - 'top_errors': List of top 5 most frequent error patterns,
              each containing 'message' (first 50 chars) and 'count' (int)
        Returns empty dict if database is empty (no failures yet).
    """
    return _check_recent_failures_impl(db_path)


def _check_recent_failures_impl(db_path: str) -> Dict[str, Any]:
    """Internal implementation for recent failures check."""
    from trader.schema import create_tables

    db = DatabaseConnection(db_path)

    try:
        # Ensure tables exist
        create_tables(db)

        # Get failures in last 24 hours
        # SQLite datetime('now', '-24 hours') gives us local time, but for simplicity
        # We'll use UTC comparison since that's what CURRENT_TIMESTAMP stores
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")

        # Get total failures in last 24h
        total_result = db.execute(
            """SELECT COUNT(*) as count
               FROM scraper_failures
               WHERE occurred_at >= ?""",
            (cutoff_str,)
        )
        total_24h = total_result[0]["count"] if total_result else 0

        # Get critical failures count
        critical_result = db.execute(
            """SELECT COUNT(*) as count
               FROM scraper_failures
               WHERE occurred_at >= ? AND level = 'critical'""",
            (cutoff_str,)
        )
        critical_24h = critical_result[0]["count"] if critical_result else 0

        # Get warning failures count
        warning_result = db.execute(
            """SELECT COUNT(*) as count
               FROM scraper_failures
               WHERE occurred_at >= ? AND level = 'warning'""",
            (cutoff_str,)
        )
        warning_24h = warning_result[0]["count"] if warning_result else 0

        # Get top 5 errors grouped by first 50 chars of message
        top_errors_result = db.execute(
            """SELECT SUBSTR(error_message, 1, 50) as message, COUNT(*) as count
               FROM scraper_failures
               WHERE occurred_at >= ?
               GROUP BY SUBSTR(error_message, 1, 50)
               ORDER BY count DESC
               LIMIT 5""",
            (cutoff_str,)
        )

        top_errors = [
            {"message": row["message"], "count": row["count"]}
            for row in top_errors_result
        ]

        # Return empty dict if no failures
        if total_24h == 0:
            return {}

        return {
            "total_24h": total_24h,
            "critical_24h": critical_24h,
            "warning_24h": warning_24h,
            "top_errors": top_errors,
        }

    except Exception as e:
        # On error, return empty dict (empty database/no failures case)
        return {}

    finally:
        db.close()
