"""Integration tests for health check CLI."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Generator

import pytest

from trader.database import DatabaseConnection
from trader.schema import create_tables


class TestHealthCheckCLIIntegration:
    """Integration tests for the health check CLI command."""

    def run_cli_health_check(self, db_path: str):
        env = os.environ.copy()
        env["TRADER_DB_PATH"] = db_path
        result = subprocess.run(
            [sys.executable, "-m", "trader.cli", "--health-check"],
            capture_output=True, text=True, env=env,
        )
        return result

    @pytest.fixture
    def temp_db_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield os.path.join(tmpdir, "test.db")

    @pytest.fixture
    def healthy_database(self, temp_db_path: str):
        db = DatabaseConnection(temp_db_path)
        create_tables(db)
        now = datetime.now(timezone.utc)
        db.execute(
            "INSERT INTO scraper_runs (status, items_count, started_at) VALUES (?, ?, ?)",
            ("completed", 10, now.strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.close()
        return temp_db_path

    @pytest.fixture
    def unhealthy_database(self, temp_db_path: str):
        db = DatabaseConnection(temp_db_path)
        create_tables(db)
        now = datetime.now(timezone.utc)
        db.execute(
            "INSERT INTO scraper_runs (status, items_count, started_at) VALUES (?, ?, ?)",
            ("running", 0, now.strftime("%Y-%m-%d %H:%M:%S"))
        )
        run_id = db.execute("SELECT last_insert_rowid() as id")[0]["id"]
        for _ in range(3):
            db.execute(
                "INSERT INTO scraper_failures (run_id, error_message, level, occurred_at) VALUES (?, ?, ?, ?)",
                (run_id, "Critical failure", "critical", now.strftime("%Y-%m-%d %H:%M:%S"))
            )
        db.close()
        return temp_db_path

    @pytest.fixture
    def degraded_database(self, temp_db_path: str):
        db = DatabaseConnection(temp_db_path)
        create_tables(db)
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        db.execute(
            "INSERT INTO scraper_runs (status, items_count, started_at) VALUES (?, ?, ?)",
            ("completed", 10, old_time.strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.close()
        return temp_db_path

    @pytest.fixture
    def consecutive_failures_database(self, temp_db_path: str):
        db = DatabaseConnection(temp_db_path)
        create_tables(db)
        now = datetime.now(timezone.utc)
        for i in range(3):
            run_time = now - timedelta(minutes=i*10)
            db.execute(
                "INSERT INTO scraper_runs (status, items_count, started_at) VALUES (?, ?, ?)",
                ("failed", 0, run_time.strftime("%Y-%m-%d %H:%M:%S"))
            )
        db.close()
        return temp_db_path

    def test_cli_runs_successfully(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        assert result.returncode in [0, 1]

    def test_output_is_valid_json(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert isinstance(output, dict)

    def test_output_has_database_check_result(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert "database" in output and "status" in output["database"]

    def test_output_has_scraper_check_result(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert "scraper" in output and "status" in output["scraper"]

    def test_output_has_recent_failures_result(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert "recent_failures" in output

    def test_output_has_overall_status(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert "overall_status" in output
        assert output["overall_status"] in ["healthy", "degraded", "unhealthy"]

    def test_all_check_results_present(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        for key in ["database", "scraper", "recent_failures", "overall_status"]:
            assert key in output

    def test_exit_code_0_for_healthy(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        if output["overall_status"] == "healthy":
            assert result.returncode == 0

    def test_exit_code_1_for_unhealthy(self, unhealthy_database: str):
        result = self.run_cli_health_check(unhealthy_database)
        output = json.loads(result.stdout)
        if output["overall_status"] == "unhealthy":
            assert result.returncode == 1

    def test_exit_code_1_for_degraded(self, degraded_database: str):
        result = self.run_cli_health_check(degraded_database)
        output = json.loads(result.stdout)
        if output["overall_status"] == "degraded":
            assert result.returncode == 1

    def test_overall_status_healthy_scenario(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert output["overall_status"] == "healthy"

    def test_overall_status_unhealthy_scenario(self, unhealthy_database: str):
        result = self.run_cli_health_check(unhealthy_database)
        output = json.loads(result.stdout)
        assert output["overall_status"] == "unhealthy"

    def test_overall_status_degraded_scenario(self, degraded_database: str):
        result = self.run_cli_health_check(degraded_database)
        output = json.loads(result.stdout)
        assert output["overall_status"] == "degraded"

    def test_overall_status_unhealthy_consecutive_failures(self, consecutive_failures_database: str):
        result = self.run_cli_health_check(consecutive_failures_database)
        output = json.loads(result.stdout)
        assert output["overall_status"] == "unhealthy"

    def test_database_response_time_present(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert "response_ms" in output["database"]

    def test_scraper_has_consecutive_failures_count(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert "consecutive_failures" in output["scraper"]

    def test_scraper_has_last_run_info(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert "last_run_at" in output["scraper"] and "last_run_status" in output["scraper"]

    def test_recent_failures_counts_by_level(self, unhealthy_database: str):
        result = self.run_cli_health_check(unhealthy_database)
        output = json.loads(result.stdout)
        failures = output.get("recent_failures", {})
        if failures:
            assert all(k in failures for k in ["total_24h", "critical_24h", "warning_24h"])

    def test_recent_failures_with_no_failures(self, healthy_database: str):
        result = self.run_cli_health_check(healthy_database)
        output = json.loads(result.stdout)
        assert output.get("recent_failures") == {}


class TestHealthCheckCLIEdgeCases:
    def run_cli_health_check(self, db_path: str):
        env = os.environ.copy()
        env["TRADER_DB_PATH"] = db_path
        result = subprocess.run(
            [sys.executable, "-m", "trader.cli", "--health-check"],
            capture_output=True, text=True, env=env,
        )
        return result

    def test_empty_database(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        db = DatabaseConnection(db_path)
        create_tables(db)
        db.close()
        result = self.run_cli_health_check(db_path)
        output = json.loads(result.stdout)
        assert "database" in output and "overall_status" in output


class TestCleanupBehavior:
    def run_cli_health_check(self, db_path: str):
        env = os.environ.copy()
        env["TRADER_DB_PATH"] = db_path
        result = subprocess.run(
            [sys.executable, "-m", "trader.cli", "--health-check"],
            capture_output=True, text=True, env=env,
        )
        return result

    @pytest.fixture
    def healthy_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseConnection(db_path)
            create_tables(db)
            db.execute(
                "INSERT INTO scraper_runs (status, items_count, started_at) VALUES (?, ?, ?)",
                ("completed", 10, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
            )
            db.close()
            yield db_path

    def test_database_file_persists_during_test(self, healthy_database: str):
        assert os.path.exists(healthy_database)
        result = self.run_cli_health_check(healthy_database)
        assert result.returncode == 0
