"""Tests for trader schema module."""
import sqlite3

import pytest

from trader.database import DatabaseConnection
from trader.schema import (
    create_tables,
    drop_tables,
    table_exists,
    get_table_schema,
)


class TestCreateTables:
    """Test cases for create_tables function."""

    def test_create_tables_creates_scraper_runs(self) -> None:
        """Verify create_tables creates scraper_runs table."""
        db = DatabaseConnection()
        create_tables(db)

        assert table_exists(db, "scraper_runs")
        db.close()

    def test_create_tables_creates_scraper_failures(self) -> None:
        """Verify create_tables creates scraper_failures table."""
        db = DatabaseConnection()
        create_tables(db)

        assert table_exists(db, "scraper_failures")
        db.close()

    def test_create_tables_creates_health_checks(self) -> None:
        """Verify create_tables creates health_checks table."""
        db = DatabaseConnection()
        create_tables(db)

        assert table_exists(db, "health_checks")
        db.close()

    def test_create_tables_is_idempotent(self) -> None:
        """Verify create_tables can be called multiple times without error."""
        db = DatabaseConnection()

        # Call multiple times
        create_tables(db)
        create_tables(db)
        create_tables(db)

        # All tables should still exist
        assert table_exists(db, "scraper_runs")
        assert table_exists(db, "scraper_failures")
        assert table_exists(db, "health_checks")
        db.close()

    def test_create_tables_creates_default_connection(self) -> None:
        """Verify create_tables works without providing a connection."""
        # Should not raise and should create tables in new connection
        create_tables()

    def test_scraper_runs_columns(self) -> None:
        """Verify scraper_runs table has correct columns."""
        db = DatabaseConnection()
        create_tables(db)

        schema = get_table_schema(db, "scraper_runs")
        columns = {col["name"]: col for col in schema}

        assert "id" in columns
        assert "started_at" in columns
        assert "ended_at" in columns
        assert "status" in columns
        assert "items_count" in columns

        # Verify id is primary key
        assert columns["id"]["pk"] == 1

        db.close()

    def test_scraper_failures_columns(self) -> None:
        """Verify scraper_failures table has correct columns."""
        db = DatabaseConnection()
        create_tables(db)

        schema = get_table_schema(db, "scraper_failures")
        columns = {col["name"]: col for col in schema}

        assert "id" in columns
        assert "run_id" in columns
        assert "error_message" in columns
        assert "level" in columns
        assert "occurred_at" in columns

        # Verify id is primary key
        assert columns["id"]["pk"] == 1

        db.close()

    def test_health_checks_columns(self) -> None:
        """Verify health_checks table has correct columns."""
        db = DatabaseConnection()
        create_tables(db)

        schema = get_table_schema(db, "health_checks")
        columns = {col["name"]: col for col in schema}

        assert "id" in columns
        assert "check_type" in columns
        assert "status" in columns
        assert "details" in columns
        assert "checked_at" in columns

        # Verify id is primary key
        assert columns["id"]["pk"] == 1

        db.close()

    def test_scraper_failures_foreign_key(self) -> None:
        """Verify scraper_failures has foreign key to scraper_runs."""
        db = DatabaseConnection()
        create_tables(db)

        # Check foreign key info
        fk_info = db.execute("PRAGMA foreign_key_list(scraper_failures)")
        assert len(fk_info) == 1
        assert fk_info[0]["table"] == "scraper_runs"
        assert fk_info[0]["from"] == "run_id"
        assert fk_info[0]["to"] == "id"

        db.close()

    def test_indexes_created(self) -> None:
        """Verify indexes are created for performance."""
        db = DatabaseConnection()
        create_tables(db)

        indexes = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        index_names = {idx["name"] for idx in indexes}

        assert "idx_scraper_runs_status" in index_names
        assert "idx_scraper_runs_started_at" in index_names
        assert "idx_scraper_failures_run_id" in index_names
        assert "idx_scraper_failures_occurred_at" in index_names
        assert "idx_health_checks_type" in index_names
        assert "idx_health_checks_checked_at" in index_names

        db.close()


class TestDropTables:
    """Test cases for drop_tables function."""

    def test_drop_tables_removes_all_tables(self) -> None:
        """Verify drop_tables removes all schema tables."""
        db = DatabaseConnection()
        create_tables(db)

        # Verify tables exist
        assert table_exists(db, "scraper_runs")
        assert table_exists(db, "scraper_failures")
        assert table_exists(db, "health_checks")

        drop_tables(db)

        # Verify tables are gone
        assert not table_exists(db, "scraper_runs")
        assert not table_exists(db, "scraper_failures")
        assert not table_exists(db, "health_checks")

        db.close()

    def test_drop_tables_safe_on_empty_db(self) -> None:
        """Verify drop_tables is safe when tables don't exist."""
        db = DatabaseConnection()

        # Should not raise even if tables don't exist
        drop_tables(db)

        db.close()


class TestTableExists:
    """Test cases for table_exists function."""

    def test_table_exists_returns_true_for_existing_table(self) -> None:
        """Verify table_exists returns True for created tables."""
        db = DatabaseConnection()
        create_tables(db)

        assert table_exists(db, "scraper_runs")
        assert table_exists(db, "scraper_failures")
        assert table_exists(db, "health_checks")

        db.close()

    def test_table_exists_returns_false_for_nonexistent_table(self) -> None:
        """Verify table_exists returns False for non-existent table."""
        db = DatabaseConnection()
        create_tables(db)

        assert not table_exists(db, "nonexistent_table")
        assert not table_exists(db, "other_table")

        db.close()


class TestGetTableSchema:
    """Test cases for get_table_schema function."""

    def test_get_table_schema_returns_columns(self) -> None:
        """Verify get_table_schema returns column information."""
        db = DatabaseConnection()
        create_tables(db)

        schema = get_table_schema(db, "scraper_runs")
        assert len(schema) == 5  # id, started_at, ended_at, status, items_count

        # Verify column structure
        for col in schema:
            assert "cid" in col
            assert "name" in col
            assert "type" in col
            assert "notnull" in col
            assert "dflt_value" in col
            assert "pk" in col

        db.close()

    def test_get_table_schema_empty_for_nonexistent_table(self) -> None:
        """Verify get_table_schema returns empty list for non-existent table."""
        db = DatabaseConnection()
        create_tables(db)

        schema = get_table_schema(db, "nonexistent_table")
        assert schema == []

        db.close()


class TestDataOperations:
    """Test cases for data operations on created tables."""

    def test_can_insert_scraper_run(self) -> None:
        """Verify scraper_runs accepts inserts."""
        db = DatabaseConnection()
        create_tables(db)

        db.execute(
            "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
            ("running", 0)
        )

        results = db.execute("SELECT * FROM scraper_runs")
        assert len(results) == 1
        assert results[0]["status"] == "running"
        assert results[0]["items_count"] == 0

        db.close()

    def test_can_insert_scraper_failure(self) -> None:
        """Verify scraper_failures accepts inserts with valid foreign key."""
        db = DatabaseConnection()
        create_tables(db)

        # First create a run
        db.execute(
            "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
            ("running", 10)
        )

        # Insert a failure referencing that run
        db.execute(
            "INSERT INTO scraper_failures (run_id, error_message, level) VALUES (?, ?, ?)",
            (1, "Connection timeout", "error")
        )

        results = db.execute("SELECT * FROM scraper_failures")
        assert len(results) == 1
        assert results[0]["error_message"] == "Connection timeout"
        assert results[0]["level"] == "error"

        db.close()

    def test_can_insert_health_check(self) -> None:
        """Verify health_checks accepts inserts."""
        db = DatabaseConnection()
        create_tables(db)

        db.execute(
            "INSERT INTO health_checks (check_type, status, details) VALUES (?, ?, ?)",
            ("database", "healthy", "Connection OK")
        )

        results = db.execute("SELECT * FROM health_checks")
        assert len(results) == 1
        assert results[0]["check_type"] == "database"
        assert results[0]["status"] == "healthy"
        assert results[0]["details"] == "Connection OK"

        db.close()

    def test_status_constraint_valid_values(self) -> None:
        """Verify scraper_runs status accepts valid values."""
        db = DatabaseConnection()
        create_tables(db)

        valid_statuses = ["running", "completed", "failed"]
        for status in valid_statuses:
            db.execute(
                "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
                (status, 0)
            )

        results = db.execute("SELECT * FROM scraper_runs")
        assert len(results) == 3

        db.close()

    def test_status_constraint_invalid_value_raises(self) -> None:
        """Verify scraper_runs status rejects invalid values."""
        db = DatabaseConnection()
        create_tables(db)

        with pytest.raises(sqlite3.Error):
            db.execute(
                "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
                ("invalid_status", 0)
            )

        db.close()

    def test_level_constraint_valid_values(self) -> None:
        """Verify scraper_failures level accepts valid values."""
        db = DatabaseConnection()
        create_tables(db)

        # Create a run first
        db.execute(
            "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
            ("running", 0)
        )

        valid_levels = ["warning", "error", "critical"]
        for level in valid_levels:
            db.execute(
                "INSERT INTO scraper_failures (run_id, error_message, level) VALUES (?, ?, ?)",
                (1, f"Error {level}", level)
            )

        results = db.execute("SELECT * FROM scraper_failures")
        assert len(results) == 3

        db.close()

    def test_level_constraint_invalid_value_raises(self) -> None:
        """Verify scraper_failures level rejects invalid values."""
        db = DatabaseConnection()
        create_tables(db)

        # Create a run first
        db.execute(
            "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
            ("running", 0)
        )

        with pytest.raises(sqlite3.Error):
            db.execute(
                "INSERT INTO scraper_failures (run_id, error_message, level) VALUES (?, ?, ?)",
                (1, "Error", "invalid_level")
            )

        db.close()

    def test_health_check_status_constraint_valid_values(self) -> None:
        """Verify health_checks status accepts valid values."""
        db = DatabaseConnection()
        create_tables(db)

        valid_statuses = ["healthy", "unhealthy"]
        for status in valid_statuses:
            db.execute(
                "INSERT INTO health_checks (check_type, status, details) VALUES (?, ?, ?)",
                ("test", status, None)
            )

        results = db.execute("SELECT * FROM health_checks")
        assert len(results) == 2

        db.close()

    def test_health_check_status_constraint_invalid_value_raises(self) -> None:
        """Verify health_checks status rejects invalid values."""
        db = DatabaseConnection()
        create_tables(db)

        with pytest.raises(sqlite3.Error):
            db.execute(
                "INSERT INTO health_checks (check_type, status, details) VALUES (?, ?, ?)",
                ("test", "invalid_status", None)
            )

        db.close()

    def test_foreign_key_enforcement(self) -> None:
        """Verify foreign key constraint is enforced."""
        db = DatabaseConnection()
        create_tables(db)

        # Enable foreign key enforcement (SQLite default is off)
        db.execute("PRAGMA foreign_keys = ON")

        # Try to insert a failure with non-existent run_id
        with pytest.raises(sqlite3.Error):
            db.execute(
                "INSERT INTO scraper_failures (run_id, error_message, level) VALUES (?, ?, ?)",
                (999, "Error", "error")
            )

        db.close()

    def test_cascade_delete(self) -> None:
        """Verify deleting a run cascades to its failures."""
        db = DatabaseConnection()
        create_tables(db)

        # Enable foreign key enforcement
        db.execute("PRAGMA foreign_keys = ON")

        # Create a run with failures
        db.execute(
            "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
            ("failed", 5)
        )
        db.execute(
            "INSERT INTO scraper_failures (run_id, error_message, level) VALUES (?, ?, ?)",
            (1, "Error 1", "error")
        )
        db.execute(
            "INSERT INTO scraper_failures (run_id, error_message, level) VALUES (?, ?, ?)",
            (1, "Error 2", "warning")
        )

        # Verify failures exist
        failures = db.execute("SELECT * FROM scraper_failures")
        assert len(failures) == 2

        # Delete the run
        db.execute("DELETE FROM scraper_runs WHERE id = 1")

        # Verify failures are gone
        failures = db.execute("SELECT * FROM scraper_failures")
        assert len(failures) == 0

        db.close()


class TestIntegrationWithContextManager:
    """Test integration with DatabaseConnection context manager."""

    def test_create_tables_within_context_manager(self) -> None:
        """Verify create_tables works within context manager."""
        with DatabaseConnection() as db:
            create_tables(db)

            assert table_exists(db, "scraper_runs")
            assert table_exists(db, "scraper_failures")
            assert table_exists(db, "health_checks")

    def test_data_persists_within_context(self) -> None:
        """Verify data operations work within context manager."""
        with DatabaseConnection() as db:
            create_tables(db)

            db.execute(
                "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
                ("completed", 42)
            )

            results = db.execute("SELECT * FROM scraper_runs")
            assert len(results) == 1
            assert results[0]["items_count"] == 42
