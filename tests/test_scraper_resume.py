"""Tests for trader.scraper module resume capability (Story 5).

This module tests the ScraperState class and Scraper resume functionality
including state saving/loading and crash recovery.
"""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from trader.scraper import CircuitBreaker, Scraper, ScraperState
from trader.exceptions import CircuitOpenError


class TestScraperStateLoadState:
    """Test ScraperState.load_state() method."""

    def test_load_state_returns_state_from_json_file(self, tmp_path):
        """ScraperState.load_state() should return state dict from JSON file."""
        state_file = tmp_path / "state.json"
        expected_state = {
            "pending_urls": ["https://example.com/1", "https://example.com/2"],
            "completed_urls": ["https://example.com/0"],
            "circuit_state": {
                "state": "CLOSED",
                "failure_count": 0,
                "last_failure_time": None,
            },
        }
        with open(state_file, "w") as f:
            json.dump(expected_state, f)

        scraper_state = ScraperState(str(state_file))
        loaded = scraper_state.load_state()

        assert loaded["pending_urls"] == expected_state["pending_urls"]
        assert loaded["completed_urls"] == {"https://example.com/0"}
        assert loaded["circuit_state"]["state"] == "CLOSED"

    def test_load_state_returns_empty_state_if_file_missing(self, tmp_path):
        """ScraperState.load_state() returns empty state if file doesn't exist."""
        state_file = tmp_path / "nonexistent.json"
        scraper_state = ScraperState(str(state_file))
        loaded = scraper_state.load_state()

        assert loaded["pending_urls"] == []
        assert loaded["completed_urls"] == set()
        assert loaded["circuit_state"] == {}

    def test_load_state_returns_empty_state_if_corrupted(self, tmp_path):
        """ScraperState.load_state() returns empty state if file is corrupted."""
        state_file = tmp_path / "corrupted.json"
        with open(state_file, "w") as f:
            f.write("not valid json {{{")

        scraper_state = ScraperState(str(state_file))
        loaded = scraper_state.load_state()

        assert loaded["pending_urls"] == []
        assert loaded["completed_urls"] == set()
        assert loaded["circuit_state"] == {}

    def test_load_state_converts_completed_urls_to_set(self, tmp_path):
        """ScraperState.load_state() converts completed_urls list to set."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": ["url1", "url2", "url3"],
            "circuit_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper_state = ScraperState(str(state_file))
        loaded = scraper_state.load_state()

        assert isinstance(loaded["completed_urls"], set)
        assert loaded["completed_urls"] == {"url1", "url2", "url3"}


class TestScraperStateCircuitBreakerTransition:
    """Test that OPEN circuit transitions to HALF_OPEN on load."""

    def test_open_circuit_transitions_to_half_open_on_load(self, tmp_path):
        """If circuit was OPEN when saved, it enters HALF_OPEN on load."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": [],
            "circuit_state": {
                "state": "OPEN",
                "failure_count": 10,
                "last_failure_time": 1234567890.0,
            },
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper_state = ScraperState(str(state_file))
        loaded = scraper_state.load_state()

        assert loaded["circuit_state"]["state"] == "HALF_OPEN"

    def test_closed_circuit_remains_closed_on_load(self, tmp_path):
        """If circuit was CLOSED when saved, it stays CLOSED on load."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": [],
            "circuit_state": {
                "state": "CLOSED",
                "failure_count": 0,
            },
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper_state = ScraperState(str(state_file))
        loaded = scraper_state.load_state()

        assert loaded["circuit_state"]["state"] == "CLOSED"


class TestScraperInitWithStateFile:
    """Test Scraper.__init__ with optional state_file_path parameter."""

    def test_scraper_accepts_state_file_path_parameter(self, tmp_path):
        """Scraper.__init__ should accept optional state_file_path parameter."""
        state_file = tmp_path / "state.json"
        scraper = Scraper(timeout=30, state_file_path=str(state_file))
        assert scraper.state_file_path == str(state_file)
        assert scraper.state_manager is not None

    def test_scraper_works_without_state_file_path(self):
        """Scraper should work without state_file_path (backward compatible)."""
        scraper = Scraper(timeout=30)
        assert scraper.state_file_path is None
        assert scraper.state_manager is None

    def test_scraper_initializes_circuit_breaker_from_saved_state(self, tmp_path):
        """Scraper initializes circuit breaker state from saved state if present."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": [],
            "circuit_state": {
                "state": "CLOSED",
                "failure_count": 5,
                "last_failure_time": 1234567890.0,
                "failure_threshold": 10,
                "recovery_timeout": 60.0,
            },
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        assert scraper.circuit_breaker.failure_count == 5
        assert scraper.circuit_breaker.current_state == "CLOSED"

    def test_scraper_initializes_new_circuit_breaker_if_no_state(self, tmp_path):
        """Scraper creates new circuit breaker if no saved state."""
        state_file = tmp_path / "nonexistent.json"
        scraper = Scraper(state_file_path=str(state_file))
        assert scraper.circuit_breaker.current_state == "CLOSED"
        assert scraper.circuit_breaker.failure_count == 0


class TestScraperRestoresPendingUrls:
    """Test that Scraper restores pending_urls queue from saved state."""

    def test_scraper_restores_pending_urls_from_state(self, tmp_path):
        """Scraper restores pending_urls queue from saved state."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": ["https://example.com/1", "https://example.com/2"],
            "completed_urls": [],
            "circuit_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        assert scraper.pending_urls == ["https://example.com/1", "https://example.com/2"]

    def test_scraper_restores_empty_pending_urls_if_no_state(self, tmp_path):
        """Scraper has empty pending_urls if no state file."""
        state_file = tmp_path / "nonexistent.json"
        scraper = Scraper(state_file_path=str(state_file))
        assert scraper.pending_urls == []


class TestScraperRestoresCompletedUrls:
    """Test that Scraper restores completed_urls set to avoid re-fetching."""

    def test_scraper_restores_completed_urls_from_state(self, tmp_path):
        """Scraper restores completed_urls set from saved state."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": ["https://example.com/1", "https://example.com/2"],
            "circuit_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        assert scraper.completed_urls == {"https://example.com/1", "https://example.com/2"}

    def test_completed_urls_are_set_type(self, tmp_path):
        """completed_urls should be a set for O(1) lookup."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": ["url1", "url2"],
            "circuit_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        assert isinstance(scraper.completed_urls, set)


class TestScraperResumeContinuesFromPending:
    """Test that resume continues from pending URLs."""

    def test_scraper_add_urls_skips_completed(self, tmp_path):
        """add_urls should skip URLs already in completed_urls."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": ["https://example.com/pending"],
            "completed_urls": ["https://example.com/completed"],
            "circuit_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        scraper.add_urls([
            "https://example.com/pending",
            "https://example.com/completed",
            "https://example.com/new"
        ])

        # Should not add completed or duplicates
        assert "https://example.com/completed" not in scraper.pending_urls
        assert scraper.pending_urls.count("https://example.com/pending") == 1
        assert "https://example.com/new" in scraper.pending_urls

    def test_mark_completed_moves_url_to_completed(self, tmp_path):
        """mark_completed should move URL from pending to completed."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": ["https://example.com/1", "https://example.com/2"],
            "completed_urls": [],
            "circuit_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        scraper.mark_completed("https://example.com/1")

        assert "https://example.com/1" not in scraper.pending_urls
        assert "https://example.com/1" in scraper.completed_urls
        assert "https://example.com/2" in scraper.pending_urls


class TestScraperCompletedUrlsNotRefetched:
    """Test that completed URLs are not re-fetched after resume."""

    def test_fetch_url_checks_completed_urls(self, tmp_path):
        """Completed URLs should not be re-fetched after resume."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": ["https://example.com/fetched"],
            "circuit_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        
        # Simulate checking if URL was already fetched
        url = "https://example.com/fetched"
        assert url in scraper.completed_urls

    def test_add_urls_excludes_already_completed(self, tmp_path):
        """add_urls should not add URLs that are already completed."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": ["https://example.com/1"],
            "circuit_state": {},
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        scraper.add_urls(["https://example.com/1", "https://example.com/2"])

        assert "https://example.com/1" not in scraper.pending_urls
        assert "https://example.com/2" in scraper.pending_urls


class TestScraperCircuitBreakerRestoredCorrectly:
    """Test that circuit breaker state is restored correctly on resume."""

    def test_circuit_breaker_failure_count_restored(self, tmp_path):
        """Circuit breaker failure count should be restored from state."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": [],
            "circuit_state": {
                "state": "CLOSED",
                "failure_count": 7,
                "last_failure_time": None,
            },
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        assert scraper.circuit_breaker.failure_count == 7

    def test_circuit_breaker_state_restored_as_half_open(self, tmp_path):
        """Circuit breaker state HALF_OPEN when saved as OPEN (per load_state rule)."""
        state_file = tmp_path / "state.json"
        state_data = {
            "pending_urls": [],
            "completed_urls": [],
            "circuit_state": {
                "state": "OPEN",
                "failure_count": 10,
                "last_failure_time": 1234567890.0,
            },
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        # ScraperState.load_state() converts OPEN to HALF_OPEN
        assert scraper.circuit_breaker.current_state == "HALF_OPEN"

    def test_circuit_breaker_last_failure_time_restored(self, tmp_path):
        """Circuit breaker last_failure_time should be restored from state."""
        state_file = tmp_path / "state.json"
        expected_time = 1234567890.0
        state_data = {
            "pending_urls": [],
            "completed_urls": [],
            "circuit_state": {
                "state": "CLOSED",
                "failure_count": 0,
                "last_failure_time": expected_time,
            },
        }
        with open(state_file, "w") as f:
            json.dump(state_data, f)

        scraper = Scraper(state_file_path=str(state_file))
        assert scraper.circuit_breaker.last_failure_time == expected_time


class TestScraperSaveState:
    """Test Scraper.save_state() method."""

    def test_save_state_creates_json_file(self, tmp_path):
        """save_state should create a JSON file with current state."""
        state_file = tmp_path / "state.json"
        scraper = Scraper(state_file_path=str(state_file))
        scraper.pending_urls = ["https://example.com/1"]
        scraper.completed_urls = {"https://example.com/0"}

        scraper.save_state()

        assert os.path.exists(state_file)
        with open(state_file, "r") as f:
            saved = json.load(f)
        assert saved["pending_urls"] == ["https://example.com/1"]
        assert saved["completed_urls"] == ["https://example.com/0"]

    def test_save_state_without_state_file_does_nothing(self):
        """save_state should do nothing if no state_file_path set."""
        scraper = Scraper()
        # Should not raise any exception
        scraper.save_state()


class TestCircuitBreakerFromStateDict:
    """Test CircuitBreaker.from_state_dict() class method."""

    def test_from_state_dict_creates_circuit_breaker(self):
        """CircuitBreaker.from_state_dict creates instance from state dict."""
        state_dict = {
            "state": "CLOSED",
            "failure_count": 3,
            "last_failure_time": 1234567890.0,
            "failure_threshold": 10,
            "recovery_timeout": 60.0,
        }
        cb = CircuitBreaker.from_state_dict(state_dict)
        assert cb.current_state == "CLOSED"
        assert cb.failure_count == 3
        assert cb.last_failure_time == 1234567890.0

    def test_from_state_dict_uses_defaults_for_missing_values(self):
        """CircuitBreaker.from_state_dict uses defaults for missing values."""
        state_dict = {
            "state": "OPEN",
        }
        cb = CircuitBreaker.from_state_dict(state_dict)
        assert cb.current_state == "OPEN"
        assert cb.failure_count == 0
        assert cb.failure_threshold == 10


class TestCircuitBreakerGetStateDict:
    """Test CircuitBreaker.get_state_dict() method."""

    def test_get_state_dict_returns_serializeable_state(self):
        """get_state_dict returns state that can be serialized to JSON."""
        cb = CircuitBreaker(failure_threshold=10, recovery_timeout=60.0)
        state = cb.get_state_dict()
        
        # Should be JSON serializable
        json_str = json.dumps(state)
        loaded = json.loads(json_str)
        
        assert loaded["state"] == "CLOSED"
        assert loaded["failure_count"] == 0
        assert loaded["failure_threshold"] == 10
        assert loaded["recovery_timeout"] == 60.0
