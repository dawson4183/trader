"""Tests for trader scraper module."""
import sqlite3

import pytest

from trader.scraper import Scraper
from trader.database import DatabaseConnection
from trader.schema import create_tables


class TestScraperClass:
    """Test cases for Scraper class existence and initialization."""

    def test_scraper_class_exists(self) -> None:
        """Verify Scraper class exists."""
        assert Scraper is not None
        assert callable(Scraper)

    def test_scraper_init_with_default_db(self) -> None:
        """Verify Scraper initializes with default database."""
        scraper = Scraper()
        assert scraper.db is not None
        assert isinstance(scraper.db, DatabaseConnection)
        assert scraper.current_run_id is None

    def test_scraper_init_with_custom_db(self) -> None:
        """Verify Scraper initializes with custom database."""
        db = DatabaseConnection()
        scraper = Scraper(db)
        assert scraper.db is db
        assert scraper.current_run_id is None

    def test_scraper_creates_tables_on_init(self) -> None:
        """Verify Scraper creates tables on initialization."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        # Verify tables exist
        result = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scraper_runs'"
        )
        assert len(result) == 1

        result = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scraper_failures'"
        )
        assert len(result) == 1


class TestStartRun:
    """Test cases for Scraper.start_run() method."""

    def test_start_run_creates_entry(self) -> None:
        """Verify start_run() creates entry in scraper_runs table."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        run_id = scraper.start_run()

        assert run_id is not None
        assert isinstance(run_id, int)

        # Verify entry in database
        result = db.execute("SELECT * FROM scraper_runs WHERE id = ?", (run_id,))
        assert len(result) == 1
        assert result[0]["status"] == "running"
        assert result[0]["items_count"] == 0

    def test_start_run_sets_current_run_id(self) -> None:
        """Verify start_run() sets current_run_id attribute."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        assert scraper.current_run_id is None

        run_id = scraper.start_run()

        assert scraper.current_run_id == run_id

    def test_start_run_raises_when_run_in_progress(self) -> None:
        """Verify start_run() raises when a run is already in progress."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()

        with pytest.raises(RuntimeError) as exc_info:
            scraper.start_run()

        assert "already in progress" in str(exc_info.value)

    def test_start_run_returns_unique_ids(self) -> None:
        """Verify each start_run() returns a unique ID."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        run_id1 = scraper.start_run()
        scraper.end_run("completed")

        run_id2 = scraper.start_run()
        scraper.end_run("completed")

        assert run_id1 != run_id2


class TestEndRun:
    """Test cases for Scraper.end_run() method."""

    def test_end_run_updates_status(self) -> None:
        """Verify end_run() updates run record with completion status."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        run_id = scraper.start_run()
        scraper.end_run("completed")

        result = db.execute("SELECT * FROM scraper_runs WHERE id = ?", (run_id,))
        assert result[0]["status"] == "completed"

    def test_end_run_updates_items_count(self) -> None:
        """Verify end_run() updates run record with items count."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        run_id = scraper.start_run()
        scraper.end_run("completed", items_count=42)

        result = db.execute("SELECT * FROM scraper_runs WHERE id = ?", (run_id,))
        assert result[0]["items_count"] == 42

    def test_end_run_sets_ended_at(self) -> None:
        """Verify end_run() sets ended_at timestamp."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        run_id = scraper.start_run()
        scraper.end_run("completed")

        result = db.execute("SELECT * FROM scraper_runs WHERE id = ?", (run_id,))
        assert result[0]["ended_at"] is not None

    def test_end_run_clears_current_run_id(self) -> None:
        """Verify end_run() clears current_run_id attribute."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        scraper.end_run("completed")

        assert scraper.current_run_id is None

    def test_end_run_accepts_failed_status(self) -> None:
        """Verify end_run() accepts 'failed' status."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        run_id = scraper.start_run()
        scraper.end_run("failed", items_count=0)

        result = db.execute("SELECT * FROM scraper_runs WHERE id = ?", (run_id,))
        assert result[0]["status"] == "failed"

    def test_end_run_raises_when_no_run_active(self) -> None:
        """Verify end_run() raises when no run is in progress."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        with pytest.raises(RuntimeError) as exc_info:
            scraper.end_run("completed")

        assert "No run is currently in progress" in str(exc_info.value)

    def test_end_run_rejects_running_status(self) -> None:
        """Verify end_run() rejects 'running' status."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()

        with pytest.raises(ValueError) as exc_info:
            scraper.end_run("running")

        assert "Cannot end a run with 'running' status" in str(exc_info.value)


class TestRecordFailure:
    """Test cases for Scraper.record_failure() method."""

    def test_record_failure_inserts_into_table(self) -> None:
        """Verify record_failure() inserts into scraper_failures table."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        run_id = scraper.start_run()
        failure_id = scraper.record_failure("Connection timeout", "error")

        assert failure_id is not None
        assert isinstance(failure_id, int)

        result = db.execute("SELECT * FROM scraper_failures WHERE id = ?", (failure_id,))
        assert len(result) == 1
        assert result[0]["run_id"] == run_id
        assert result[0]["error_message"] == "Connection timeout"
        assert result[0]["level"] == "error"

    def test_record_failure_accepts_warning_level(self) -> None:
        """Verify record_failure() accepts 'warning' level."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        failure_id = scraper.record_failure("Minor issue", "warning")

        result = db.execute("SELECT * FROM scraper_failures WHERE id = ?", (failure_id,))
        assert result[0]["level"] == "warning"

    def test_record_failure_accepts_critical_level(self) -> None:
        """Verify record_failure() accepts 'critical' level."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        failure_id = scraper.record_failure("Critical error", "critical")

        result = db.execute("SELECT * FROM scraper_failures WHERE id = ?", (failure_id,))
        assert result[0]["level"] == "critical"

    def test_record_failure_creates_run_if_none_active(self) -> None:
        """Verify record_failure() creates run if none is active."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        # No active run
        assert scraper.current_run_id is None

        failure_id = scraper.record_failure("Error without run", "error")

        result = db.execute("SELECT * FROM scraper_failures WHERE id = ?", (failure_id,))
        assert len(result) == 1

        # Verify a run was created
        runs = db.execute("SELECT * FROM scraper_runs")
        assert len(runs) == 1
        assert runs[0]["status"] == "failed"


class TestGetStatus:
    """Test cases for Scraper.get_status() method."""

    def test_get_status_returns_idle_initially(self) -> None:
        """Verify get_status() returns 'idle' when no runs exist."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        status = scraper.get_status()

        assert status == "idle"

    def test_get_status_returns_running_after_start(self) -> None:
        """Verify get_status() returns 'running' after start_run()."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        status = scraper.get_status()

        assert status == "running"

    def test_get_status_returns_idle_after_completed_run(self) -> None:
        """Verify get_status() returns 'idle' after completed run."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        scraper.end_run("completed")
        status = scraper.get_status()

        assert status == "idle"

    def test_get_status_returns_error_after_failed_run(self) -> None:
        """Verify get_status() returns 'error' after failed run."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        scraper.end_run("failed")
        status = scraper.get_status()

        assert status == "error"

    def test_get_status_returns_error_with_recent_failures(self) -> None:
        """Verify get_status() returns 'error' with recent failures."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        scraper.record_failure("Some error", "error")
        scraper.end_run("completed")

        status = scraper.get_status()

        assert status == "error"

    def test_get_status_detects_running_in_database(self) -> None:
        """Verify get_status() detects runs marked as running in database."""
        db = DatabaseConnection()
        create_tables(db)

        # Insert a running run directly (simulating a crash/restart scenario)
        db.execute(
            "INSERT INTO scraper_runs (status, items_count) VALUES (?, ?)",
            ("running", 0)
        )

        scraper = Scraper(db)
        status = scraper.get_status()

        assert status == "running"


class TestGetCurrentRunId:
    """Test cases for Scraper.get_current_run_id() method."""

    def test_get_current_run_id_returns_none_initially(self) -> None:
        """Verify get_current_run_id() returns None initially."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        assert scraper.get_current_run_id() is None

    def test_get_current_run_id_returns_id_during_run(self) -> None:
        """Verify get_current_run_id() returns ID during run."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        run_id = scraper.start_run()

        assert scraper.get_current_run_id() == run_id

    def test_get_current_run_id_returns_none_after_end(self) -> None:
        """Verify get_current_run_id() returns None after end_run()."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        scraper.end_run("completed")

        assert scraper.get_current_run_id() is None


class TestGetRunHistory:
    """Test cases for Scraper.get_run_history() method."""

    def test_get_run_history_returns_list(self) -> None:
        """Verify get_run_history() returns a list."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        history = scraper.get_run_history()

        assert isinstance(history, list)

    def test_get_run_history_returns_runs(self) -> None:
        """Verify get_run_history() returns run records."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        scraper.end_run("completed", items_count=10)

        history = scraper.get_run_history()

        assert len(history) == 1
        assert history[0]["status"] == "completed"
        assert history[0]["items_count"] == 10

    def test_get_run_history_respects_limit(self) -> None:
        """Verify get_run_history() respects the limit parameter."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        # Create 5 runs
        for _ in range(5):
            scraper.start_run()
            scraper.end_run("completed")

        history = scraper.get_run_history(limit=3)

        assert len(history) == 3

    def test_get_run_history_orders_by_started_at_desc(self) -> None:
        """Verify get_run_history() orders by started_at descending."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        # Create runs with different status
        scraper.start_run()
        scraper.end_run("completed")

        scraper.start_run()
        scraper.end_run("failed")

        history = scraper.get_run_history()

        # Most recent should be first
        assert history[0]["status"] == "failed"
        assert history[1]["status"] == "completed"


class TestGetRecentFailures:
    """Test cases for Scraper.get_recent_failures() method."""

    def test_get_recent_failures_returns_list(self) -> None:
        """Verify get_recent_failures() returns a list."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        failures = scraper.get_recent_failures()

        assert isinstance(failures, list)

    def test_get_recent_failures_returns_failures(self) -> None:
        """Verify get_recent_failures() returns failure records."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        scraper.record_failure("Error 1", "error")
        scraper.record_failure("Error 2", "warning")
        scraper.end_run("failed")

        failures = scraper.get_recent_failures()

        assert len(failures) == 2
        assert failures[0]["error_message"] == "Error 2"
        assert failures[1]["error_message"] == "Error 1"

    def test_get_recent_failures_respects_limit(self) -> None:
        """Verify get_recent_failures() respects the limit parameter."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        for i in range(5):
            scraper.record_failure(f"Error {i}", "error")
        scraper.end_run("failed")

        failures = scraper.get_recent_failures(limit=3)

        assert len(failures) == 3

    def test_get_recent_failures_orders_by_occurred_at_desc(self) -> None:
        """Verify get_recent_failures() orders by occurred_at descending."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        scraper.start_run()
        scraper.record_failure("First error", "error")
        scraper.record_failure("Second error", "error")
        scraper.end_run("failed")

        failures = scraper.get_recent_failures()

        # Most recent should be first
        assert failures[0]["error_message"] == "Second error"
        assert failures[1]["error_message"] == "First error"


class TestIntegration:
    """Integration tests for Scraper workflow."""

    def test_full_scraper_workflow(self) -> None:
        """Verify full scraper workflow works correctly."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        # Start a run
        assert scraper.get_status() == "idle"

        run_id = scraper.start_run()
        assert scraper.get_status() == "running"
        assert scraper.get_current_run_id() == run_id

        # Record some items and failures
        scraper.record_failure("Minor issue", "warning")
        scraper.record_failure("Serious issue", "error")

        # End the run
        scraper.end_run("completed", items_count=100)
        assert scraper.get_status() == "error"  # Due to recent failures
        assert scraper.get_current_run_id() is None

        # Check history
        history = scraper.get_run_history()
        assert len(history) == 1
        assert history[0]["items_count"] == 100

        failures = scraper.get_recent_failures()
        assert len(failures) == 2

    def test_multiple_runs(self) -> None:
        """Verify multiple runs work correctly."""
        db = DatabaseConnection()
        scraper = Scraper(db)

        # Run 1 - completed successfully
        scraper.start_run()
        scraper.end_run("completed", items_count=50)

        # Run 2 - failed
        scraper.start_run()
        scraper.record_failure("Fatal error", "critical")
        scraper.end_run("failed", items_count=10)

        # Run 3 - completed with warnings
        scraper.start_run()
        scraper.record_failure("Warning", "warning")
        scraper.end_run("completed", items_count=75)

        history = scraper.get_run_history()
        assert len(history) == 3

        # Verify order (most recent first)
        assert history[0]["items_count"] == 75
        assert history[1]["items_count"] == 10
        assert history[2]["items_count"] == 50

    def test_scraper_with_context_manager_db(self) -> None:
        """Verify Scraper works with DatabaseConnection context manager."""
        with DatabaseConnection() as db:
            scraper = Scraper(db)

            run_id = scraper.start_run()
            scraper.end_run("completed", items_count=25)

            history = scraper.get_run_history()
            assert len(history) == 1
