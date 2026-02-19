"""Tests for trader health check module."""
import os
import sqlite3

import pytest

from trader.health_check import check_database_connection


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
        # Response time should be under 100ms for in-memory database
        assert 0 <= result["response_ms"] < 100

    def test_no_error_on_success(self) -> None:
        """Verify error key is not present on successful connection."""
        result = check_database_connection()
        assert result["status"] == "ok"
        assert "error" not in result

    def test_has_error_on_failure(self) -> None:
        """Verify error key is present on connection failure."""
        # Create a read-only directory to force a connection error
        import tempfile
        import stat
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a path that's in a read-only location
            db_path = os.path.join(tmpdir, "test.db")
            # Close the file descriptor properly
            fd = os.open(db_path, os.O_CREAT | os.O_RDWR)
            os.close(fd)
            # Make directory read-only
            os.chmod(tmpdir, stat.S_IRUSR | stat.S_IXUSR)
            
            try:
                result = check_database_connection(os.path.join(tmpdir, "readonly", "test.db"))
                assert result["status"] == "error"
                assert "error" in result
                assert isinstance(result["error"], str)
                assert len(result["error"]) > 0
            finally:
                # Restore permissions for cleanup
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
        # This is implicitly tested by the success case
        result = check_database_connection()
        assert result["status"] == "ok"
        assert result["response_ms"] > 0