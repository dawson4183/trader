"""Tests for trader health check module."""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from trader.health_check import check_database_connection, check_scraper_status
from trader.database import DatabaseConnection
from trader.schema import create_tables


class TestCheckDatabaseConnection:
    """Test cases for check_database_connection() function."""

    def test_function_exists(self) -> None:
        """Verify check_database_connection function exists and is callable."""
        from trader import health_check
        assert hasattr(health_check, 'check_database_connection')
        assert callable(health_check.check_database_connection)

    def test_returns_dict(self) -> None:
        """Verify check_database_connection returns a dictionary."""
        result = check_database_connection()
        assert isinstance(result, dict)

    def test_returns_status_key(self) -> None:
        """Verify result contains 'status' key."""
        result = check_database_connection()
        assert "status" in result
        assert result["status"] in ("ok", "error")

    def test_returns_response_ms_key(self) -> None:
        """Verify result contains 'response_ms' key."""
        result = check_database_connection()
        assert "response_ms" in result
        assert isinstance(result["response_ms"], (int, float))

    def test_ok_status_on_valid_connection(self) -> None:
        """Verify status is 'ok' on valid connection."""
        result = check_database_connection()
        assert result["status"] == "ok"

    def test_response_ms_is_valid_number(self) -> None:
        """Verify response_ms is a non-negative number."""
        result = check_database_connection()
        assert result["response_ms"] >= 0

    def test_response_ms_in_milliseconds(self) -> None:
        """Verify response_ms is a reasonable millisecond value."""
        result = check_database_connection()
        assert 0 <= result["response_ms"] < 100

    def test_no_error_on_success(self) -> None:
        """Verify error key is not present on successful connection."""
        result = check_database_connection()
        assert result["status"] == "ok"
        assert "error" not in result

    def test_has_error_on_failure(self) -> None:
        """Verify error key is present on connection failure."""
        import tempfile
        import stat
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            fd = os.open(db_path, os.O_CREAT | os.O_RDWR)
            os.close(fd)
            os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)
            
            try:
                result = check_database_connection(os.path.join(tmpdir, "readonly", "test.db"))
                assert result["status"] == "error"
                assert "error" in result
                assert isinstance(result["error"], str)
                assert len(result["error"]) > 0
            finally:
                os.chmod(tmpdir, stat.S_IRWXU)

    def test_error_response_ms_is_zero(self) -> None:
        """Verify response_ms is 0 on connection failure."""
        import tempfile
        import stat
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            fd = os.open(db_path, os.O_CREAT | os.O_RDWR)
            os.close(fd)
            os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)
            
            try:
                result = check_database_connection(os.path.join(tmpdir, "readonly", "test.db"))
                assert result["status"] == "error"
                assert result["response_ms"] == 0.0
            finally:
                os.chmod(tmpdir, stat.S_IRWXU)

    def test_error_message_is_string(self) -> None:
        """Verify error message is a string."""
        import tempfile
        import stat
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            fd = os.open(db_path, os.O_CREAT | os.O_RDWR)
            os.close(fd)
            os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)
            
            try:
                result = check_database_connection(os.path.join(tmpdir, "readonly", "test.db"))
                assert result["status"] == "error"
                assert "error" in result
                assert isinstance(result["error"], str)
            finally:
                os.chmod(tmpdir, stat.S_IRWXU)

    def test_executes_select_1_query(self) -> None:
        """Verify the function executes a SELECT 1 query internally."""
        result = check_database_connection()
        assert result["status"] == "ok"
        assert result["response_ms"] > 0


class TestCheckScraperStatus:
    """Test cases for check_scraper_status() function."""

    def test_function_exists(self) -> None:
        """Verify check_scraper_status function exists and is callable."""
        from trader import health_check
        assert hasattr(health_check, 'check_scraper_status')
        assert callable(health_check.check_scraper_status)

    def test_returns_dict(self) -> None:
        """Verify check_scraper_status returns a dictionary."""
        result = check_scraper_status()
        assert isinstance(result, dict)

    def test_returns_status_key(self) -> None:
        """Verify result contains 'status' key."""
        result = check_scraper_status()
        assert "status" in result
        assert result["status"] in ("ok", "error", "idle")

    def test_returns_last_run_at_key(self) -> None:
        """Verify result contains 'last_run_at' key."""
        result = check_scraper_status()
        assert "last_run_at" in result

    def test_returns_last_run_status_key(self) -> None:
        """Verify result contains 'last_run_status' key."""
        result = check_scraper_status()
        assert "last_run_status" in result

    def test_returns_consecutive_failures_key(self) -> None:
        """Verify result contains 'consecutive_failures' key."""
        result = check_scraper_status()
        assert "consecutive_failures" in result
        assert isinstance(result["consecutive_failures"], int)

    def test_idle_status_when_no_runs(self) -> None:
        """Verify status is 'idle' when no scraper runs exist."""
        result = check_scraper_status()
        assert result["status"] == "idle"
        assert result["last_run_at"] is None
        assert result["last_run_status"] is None
        assert result["consecutive_failures"] == 0

    def test_fetches_most_recent_run(self) -> None:
        """Verify function fetches most recent scraper run from database."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseConnection(db_path)
            create_tables(db)
            
            db.execute(
                "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
                ("completed", 100)
            )
            
            runs = db.execute("SELECT started_at FROM scraper_runs ORDER BY started_at DESC")
            expected_time = runs[0]["started_at"]
            
            db.close()
            
            result = check_scraper_status(db_path)
            assert result["last_run_status"] == "completed"
            assert result["last_run_at"] == expected_time

    def test_counts_consecutive_failures_in_last_5_runs(self) -> None:
        """Verify function counts consecutive failures from last 5 runs."""
        import tempfile
        import os
        from datetime import datetime
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseConnection(db_path)
            create_tables(db)
            
            now = datetime.now()
            
            for i in range(3):
                timestamp = (now - timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    """INSERT INTO scraper_runs (status, items_count, started_at)
                       VALUES (?, ?, ?)""",
                    ("failed", 0, timestamp)
                )
            
            for i in range(3, 5):
                timestamp = (now - timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    """INSERT INTO scraper_runs (status, items_count, started_at)
                       VALUES (?, ?, ?)""",
                    ("completed", 100, timestamp)
                )
            
            db.close()
            
            result = check_scraper_status(db_path)
            assert result["consecutive_failures"] == 3

    def test_error_status_when_consecutive_failures_gte_3(self) -> None:
        """Verify status is 'error' when consecutive_failures >= 3."""
        import tempfile
        import os
        from datetime import datetime
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseConnection(db_path)
            create_tables(db)
            
            now = datetime.now()
            
            for i in range(3):
                timestamp = (now - timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    """INSERT INTO scraper_runs (status, items_count, started_at)
                       VALUES (?, ?, ?)""",
                    ("failed", 0, timestamp)
                )
            
            db.close()
            
            result = check_scraper_status(db_path)
            assert result["status"] == "error"

    def test_idle_status_when_no_runs_in_last_24_hours(self) -> None:
        """Verify status is 'idle' when no runs in last 24 hours."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseConnection(db_path)
            create_tables(db)
            
            old_time = datetime.now(timezone.utc) - timedelta(hours=25)
            db.execute(
                """INSERT INTO scraper_runs (status, items_count, started_at)
                   VALUES (?, ?, ?)""",
                ("completed", 100, old_time.strftime("%Y-%m-%d %H:%M:%S"))
            )
            
            db.close()
            
            result = check_scraper_status(db_path)
            assert result["status"] == "idle"

    def test_ok_status_when_recent_run(self) -> None:
        """Verify status is 'ok' when there is a recent successful run."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseConnection(db_path)
            create_tables(db)
            
            recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
            db.execute(
                """INSERT INTO scraper_runs (status, items_count, started_at)
                   VALUES (?, ?, ?)""",
                ("completed", 100, recent_time.strftime("%Y-%m-%d %H:%M:%S"))
            )
            
            db.close()
            
            result = check_scraper_status(db_path)
            assert result["status"] == "ok"

    def test_error_takes_precedence_over_idle(self) -> None:
        """Verify error status takes precedence over idle status."""
        import tempfile
        import os
        from datetime import datetime
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseConnection(db_path)
            create_tables(db)
            
            now = datetime.now()
            
            for i in range(3):
                timestamp = (now - timedelta(hours=25, seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    """INSERT INTO scraper_runs (status, items_count, started_at)
                       VALUES (?, ?, ?)""",
                    ("failed", 0, timestamp)
                )
            
            db.close()
            
            result = check_scraper_status(db_path)
            assert result["status"] == "error"

    def test_returns_timestamp_in_last_run_at(self) -> None:
        """Verify last_run_at contains a timestamp string."""
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseConnection(db_path)
            create_tables(db)
            
            db.execute(
                "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
                ("completed", 100)
            )
            
            db.close()
            
            result = check_scraper_status(db_path)
            assert result["last_run_at"] is not None
            assert isinstance(result["last_run_at"], str)
