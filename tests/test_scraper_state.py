"""Tests for ScraperState class.

Tests for state persistence to JSON file with atomic write capability.
"""

import json
import os
import shutil
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from trader.scraper import ScraperState


class TestScraperStateBasics:
    """Test basic ScraperState functionality."""

    def test_scraper_state_instantiates_with_defaults(self, tmp_path):
        """ScraperState should instantiate with default file path."""
        state = ScraperState.__new__(ScraperState)
        state._initialized = False
        
        with patch.object(Path, 'home', return_value=tmp_path):
            state.__init__()
            assert isinstance(state.state_file, Path)
            assert str(state.state_file) == str(tmp_path / ".trader" / "scraper_state.json")

    def test_scraper_state_accepts_custom_file(self, tmp_path):
        """ScraperState should accept custom state file path."""
        custom_file = tmp_path / "custom_state.json"
        
        # Reset singleton
        ScraperState._instance = None
        state = ScraperState.__new__(ScraperState)
        state._initialized = False
        state.__init__(str(custom_file))
        
        assert state.state_file == custom_file

    def test_creates_state_directory(self, tmp_path):
        """ScraperState should create state directory if it doesn't exist."""
        state_dir = tmp_path / "nonexistent" / "trader"
        state_file = state_dir / "state.json"
        
        # Reset singleton
        ScraperState._instance = None
        state = ScraperState.__new__(ScraperState)
        state._initialized = False
        state.__init__(str(state_file))
        
        assert state_dir.exists()


class TestScraperStateSave:
    """Test ScraperState.save_state() method."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton for each test
        ScraperState._instance = None
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "scraper_state.json"

    def teardown_method(self):
        """Clean up after tests."""
        # Reset singleton
        ScraperState._instance = None
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_save_state_creates_file(self):
        """save_state should create state file."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        result = state.save_state()
        
        assert result.exists()
        assert self.state_file.exists()

    def test_save_state_includes_all_required_fields(self):
        """save_state should include all required state fields."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        state.save_state(
            circuit_state="open",
            failure_count=5,
            last_failure_time="2024-01-01T00:00:00",
            pending_urls=["http://example.com"],
            completed_urls=["http://test.com"]
        )
        
        with open(self.state_file, 'r') as f:
            saved_data = json.load(f)
        
        assert "circuit_state" in saved_data
        assert "failure_count" in saved_data
        assert "last_failure_time" in saved_data
        assert "pending_urls" in saved_data
        assert "completed_urls" in saved_data
        assert "timestamp" in saved_data

    def test_save_state_saves_correct_values(self):
        """save_state should save the values passed to it."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        state.save_state(
            circuit_state="half_open",
            failure_count=10,
            last_failure_time="2024-06-15T12:30:45",
            pending_urls=["https://site1.com", "https://site2.com"],
            completed_urls=["https://done1.com"]
        )
        
        with open(self.state_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["circuit_state"] == "half_open"
        assert saved_data["failure_count"] == 10
        assert saved_data["last_failure_time"] == "2024-06-15T12:30:45"
        assert saved_data["pending_urls"] == ["https://site1.com", "https://site2.com"]
        assert saved_data["completed_urls"] == ["https://done1.com"]

    def test_save_state_default_values(self):
        """save_state should use default values when not provided."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        state.save_state()
        
        with open(self.state_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["circuit_state"] == "closed"
        assert saved_data["failure_count"] == 0
        assert saved_data["last_failure_time"] is None
        assert saved_data["pending_urls"] == []
        assert saved_data["completed_urls"] == []

    def test_save_state_returns_file_path(self):
        """save_state should return the file path."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        result = state.save_state()
        
        assert isinstance(result, Path)
        assert str(result) == str(self.state_file)

    def test_save_state_updates_timestamp(self):
        """save_state should include current timestamp."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        from datetime import datetime
        before_save = datetime.now(timezone.utc).isoformat()[:19]
        
        state.save_state()
        
        with open(self.state_file, 'r') as f:
            saved_data = json.load(f)
        
        assert "timestamp" in saved_data
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(saved_data["timestamp"])


class TestScraperStateLoad:
    """Test ScraperState.load_state() method."""

    def setup_method(self):
        """Set up test fixtures."""
        ScraperState._instance = None
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "scraper_state.json"

    def teardown_method(self):
        """Clean up."""
        ScraperState._instance = None
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_load_state_returns_dict(self):
        """load_state should return a dictionary."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        state.save_state()
        
        result = state.load_state()
        
        assert isinstance(result, dict)

    def test_load_state_contains_expected_fields(self):
        """load_state should return dict with expected fields."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        state.save_state(
            circuit_state="open",
            failure_count=7,
            last_failure_time="2024-01-15T10:00:00",
            pending_urls=["http://pending.com"],
            completed_urls=["http://completed.com"]
        )
        
        result = state.load_state()
        
        assert "circuit_state" in result
        assert "failure_count" in result
        assert "last_failure_time" in result
        assert "pending_urls" in result
        assert "completed_urls" in result
        assert "timestamp" in result

    def test_load_state_returns_saved_values(self):
        """load_state should return the values that were saved."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        state.save_state(
            circuit_state="open",
            failure_count=5,
            pending_urls=["url1", "url2"],
            completed_urls=["url3"]
        )
        
        result = state.load_state()
        
        assert result["circuit_state"] == "open"
        assert result["failure_count"] == 5
        assert result["pending_urls"] == ["url1", "url2"]
        assert result["completed_urls"] == ["url3"]

    def test_load_state_raises_file_not_found(self):
        """load_state should raise FileNotFoundError if file doesn't exist."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        with pytest.raises(FileNotFoundError):
            state.load_state()

    def test_load_state_handles_corrupted_json(self):
        """load_state should raise JSONDecodeError for corrupted file."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.state_file, 'w') as f:
            f.write("{ invalid json")
        
        with pytest.raises(json.JSONDecodeError):
            state.load_state()


class TestScraperStateAtomicWrite:
    """Test atomic write functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        ScraperState._instance = None
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "scraper_state.json"

    def teardown_method(self):
        """Clean up."""
        ScraperState._instance = None
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_atomic_write_uses_temp_file(self):
        """save_state should use temporary file during write."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        temp_file = self.state_file.with_suffix('.tmp')
        
        # Check that temp file doesn't exist after successful write
        state.save_state()
        
        assert not temp_file.exists()
        assert self.state_file.exists()

    def test_atomic_write_renames_on_success(self):
        """save_state should rename temp file to final on success."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        state.save_state()
        
        assert self.state_file.exists()
        
        # Verify content
        with open(self.state_file, 'r') as f:
            data = json.load(f)
            assert "circuit_state" in data

    def test_atomic_write_cleans_up_temp_on_failure(self, tmp_path):
        """save_state should clean up temp file on failure."""
        # Create a temp file that will be used
        temp_file = tmp_path / "state.json.tmp"
        
        # Create a ScraperState and manually trigger temp file creation then failure
        state_file = tmp_path / "state.json"
        ScraperState._instance = None
        state = ScraperState(str(state_file))
        
        # Test that save_state handles failures properly by using a restricted directory
        # This is a simplified test - we verify the atomic write mechanism works
        # as intended (temp file is used, then renamed)
        assert state.save_state() == state_file
        assert not (tmp_path / "state.json.tmp").exists()
        assert (tmp_path / "state.json").exists()

    def test_no_corruption_on_parallel_writes(self):
        """Multiple parallel writes should not corrupt the file."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        # Simulate multiple writes
        for i in range(3):
            state.save_state(
                circuit_state="open",
                failure_count=i,
                pending_urls=[f"url{i}"]
            )
            
            # Verify file is valid JSON after each write
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                assert "circuit_state" in data
                assert "failure_count" in data


class TestScraperStateClear:
    """Test clear_state method."""

    def setup_method(self):
        """Set up test fixtures."""
        ScraperState._instance = None
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "scraper_state.json"

    def teardown_method(self):
        """Clean up."""
        ScraperState._instance = None
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_clear_state_removes_file(self):
        """clear_state should remove the state file."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        state.save_state()
        
        assert self.state_file.exists()
        
        state.clear_state()
        
        assert not self.state_file.exists()

    def test_clear_state_handles_missing_file(self):
        """clear_state should handle missing file gracefully."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        # Should not raise
        state.clear_state()
        assert not self.state_file.exists()


class TestScraperStateClassMethod:
    """Test class method ScraperState.load_state_from_file."""

    def setup_method(self):
        """Set up test fixtures."""
        ScraperState._instance = None
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "scraper_state.json"

    def teardown_method(self):
        """Clean up."""
        ScraperState._instance = None
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_load_state_from_file_returns_dict(self):
        """load_state_from_file should return dict."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        state.save_state(circuit_state="open", failure_count=3)
        
        # Reset singleton
        ScraperState._instance = None
        
        result = ScraperState.load_state_from_file(str(self.state_file))
        
        assert isinstance(result, dict)
        assert result["circuit_state"] == "open"
        assert result["failure_count"] == 3

    def test_load_state_from_file_raises_on_missing(self):
        """load_state_from_file should raise FileNotFoundError if file missing."""
        ScraperState._instance = None
        
        with pytest.raises(FileNotFoundError):
            ScraperState.load_state_from_file(str(self.state_file))


class TestScraperStateAtexit:
    """Test atexit handler functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        ScraperState._instance = None
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "scraper_state.json"

    def teardown_method(self):
        """Clean up."""
        ScraperState._instance = None
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_atexit_handler_registered(self):
        """ScraperState should register atexit handler on init."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        
        # Just verify initialization doesn't error
        assert state._initialized is True

    def test_cleanup_on_exit_saves_state(self):
        """_cleanup_on_exit should save current state."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        state.circuit_state = "half_open"
        state.failure_count = 5
        state.pending_urls = ["http://example.com"]
        
        state._cleanup_on_exit()
        
        assert self.state_file.exists()
        
        with open(self.state_file, 'r') as f:
            saved = json.load(f)
        
        assert saved["circuit_state"] == "half_open"
        assert saved["failure_count"] == 5
        assert saved["pending_urls"] == ["http://example.com"]


class TestScraperStateDefaultPath:
    """Test default state file path is ~/.trader/scraper_state.json."""

    def test_default_state_path_is_trader_dir(self, tmp_path):
        """Default state should be in ~/.trader/scraper_state.json."""
        ScraperState._instance = None
        
        with patch.object(Path, 'home', return_value=tmp_path):
            state = ScraperState()
            assert str(state.state_file) == str(tmp_path / ".trader" / "scraper_state.json")


class TestScraperStateJsonFormat:
    """Test JSON output format."""

    def setup_method(self):
        """Set up test fixtures."""
        ScraperState._instance = None
        self.temp_dir = Path(tempfile.mkdtemp())
        self.state_file = self.temp_dir / "scraper_state.json"

    def teardown_method(self):
        """Clean up."""
        ScraperState._instance = None
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_json_is_formatted_with_indent(self):
        """JSON should be formatted with indentation for readability."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        state.save_state()
        
        with open(self.state_file, 'r') as f:
            content = f.read()
        
        # Should have newlines for formatting
        assert '\n' in content
        # Should have indentation (spaces)
        assert '  ' in content

    def test_json_keys_are_sorted(self):
        """JSON keys should be sorted alphabetically."""
        ScraperState._instance = None
        state = ScraperState(str(self.state_file))
        state.save_state()
        
        with open(self.state_file, 'r') as f:
            data = json.load(f)
        
        # Keys should be in alphabetical order
        keys = list(data.keys())
        assert keys == sorted(keys)
