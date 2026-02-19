"""Tests for ScraperState persistence functionality."""
import json
import os
import time
import tempfile
import atexit
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from trader.error_handling import ScraperState, CircuitState


class TestScraperStateBasic:
    """Test basic ScraperState functionality."""

    def test_default_state_file_path(self):
        """Should use ~/.trader/scraper_state.json as default."""
        state = ScraperState()
        expected = Path.home() / ".trader" / "scraper_state.json"
        assert state.state_file == expected

    def test_custom_state_file_path(self):
        """Should accept custom state file path."""
        custom_path = Path("/tmp/custom_state.json")
        state = ScraperState(state_file=custom_path)
        assert state.state_file == custom_path

    def test_default_initial_values(self):
        """Should have correct default initial values."""
        state = ScraperState()
        assert state.circuit_state == CircuitState.CLOSED
        assert state.failure_count == 0
        assert state.last_failure_time is None
        assert state.pending_urls == []
        assert state.completed_urls == []

    def test_custom_initial_values(self):
        """Should accept custom initial values."""
        state = ScraperState(
            circuit_state=CircuitState.OPEN,
            failure_count=5,
            last_failure_time=1234567890.0,
            pending_urls=["http://example.com/1"],
            completed_urls=["http://example.com/2"]
        )
        assert state.circuit_state == CircuitState.OPEN
        assert state.failure_count == 5
        assert state.last_failure_time == 1234567890.0
        assert state.pending_urls == ["http://example.com/1"]
        assert state.completed_urls == ["http://example.com/2"]


class TestScraperStateSave:
    """Test ScraperState save_state functionality."""

    def test_save_state_creates_file(self, tmp_path):
        """Should create state file on save_state() call."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        
        state.save_state()
        
        assert state_file.exists()

    def test_save_state_creates_directory(self, tmp_path):
        """Should create parent directories if they don't exist."""
        state_file = tmp_path / "subdir" / "nested" / "state.json"
        state = ScraperState(state_file=state_file)
        
        state.save_state()
        
        assert state_file.exists()

    def test_save_state_contains_expected_fields(self, tmp_path):
        """Saved state should contain all expected fields."""
        state_file = tmp_path / "state.json"
        state = ScraperState(
            state_file=state_file,
            circuit_state=CircuitState.OPEN,
            failure_count=10,
            last_failure_time=1234567890.0,
            pending_urls=["http://example.com/pending1", "http://example.com/pending2"],
            completed_urls=["http://example.com/done1"]
        )
        
        state.save_state()
        
        with open(state_file, 'r') as f:
            saved = json.load(f)
        
        assert saved["circuit_state"] == "OPEN"
        assert saved["failure_count"] == 10
        assert saved["last_failure_time"] == 1234567890.0
        assert saved["pending_urls"] == ["http://example.com/pending1", "http://example.com/pending2"]
        assert saved["completed_urls"] == ["http://example.com/done1"]
        assert "timestamp" in saved
        assert isinstance(saved["timestamp"], float)

    def test_save_state_timestamp_is_current(self, tmp_path):
        """Saved state should have current timestamp."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        
        before = time.time()
        state.save_state()
        after = time.time()
        
        with open(state_file, 'r') as f:
            saved = json.load(f)
        
        assert before <= saved["timestamp"] <= after


class TestScraperStateLoad:
    """Test ScraperState load functionality."""

    def test_load_state_returns_dict(self, tmp_path):
        """Should return state as dictionary."""
        state_file = tmp_path / "state.json"
        state = ScraperState(
            state_file=state_file,
            circuit_state=CircuitState.OPEN,
            failure_count=5,
            pending_urls=["http://example.com"]
        )
        state.save_state()
        
        loaded = state.load_state()
        
        assert isinstance(loaded, dict)
        assert loaded["circuit_state"] == "OPEN"
        assert loaded["failure_count"] == 5
        assert loaded["pending_urls"] == ["http://example.com"]

    def test_load_and_restore_restores_attributes(self, tmp_path):
        """Should restore instance attributes from file."""
        state_file = tmp_path / "state.json"
        
        # Create and save state
        state1 = ScraperState(
            state_file=state_file,
            circuit_state=CircuitState.HALF_OPEN,
            failure_count=7,
            last_failure_time=9876543210.0,
            pending_urls=["url1", "url2"],
            completed_urls=["url3"]
        )
        state1.save_state()
        
        # Create new instance and restore
        state2 = ScraperState(state_file=state_file)
        state2.load_and_restore()
        
        assert state2.circuit_state == CircuitState.HALF_OPEN
        assert state2.failure_count == 7
        assert state2.last_failure_time == 9876543210.0
        assert state2.pending_urls == ["url1", "url2"]
        assert state2.completed_urls == ["url3"]

    def test_load_state_file_not_found(self, tmp_path):
        """Should raise FileNotFoundError if file doesn't exist."""
        state_file = tmp_path / "nonexistent.json"
        state = ScraperState(state_file=state_file)
        
        with pytest.raises(FileNotFoundError):
            state.load_state()

    def test_load_state_corrupted_json(self, tmp_path):
        """Should raise JSONDecodeError for corrupted file."""
        state_file = tmp_path / "corrupted.json"
        state_file.write_text("not valid json{")
        
        state = ScraperState(state_file=state_file)
        
        with pytest.raises(json.JSONDecodeError):
            state.load_state()

    def test_state_exists_false_when_no_file(self, tmp_path):
        """state_exists() should return False when file doesn't exist."""
        state_file = tmp_path / "nonexistent.json"
        state = ScraperState(state_file=state_file)
        
        assert state.state_exists() is False

    def test_state_exists_true_when_file_exists(self, tmp_path):
        """state_exists() should return True when file exists."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        state.save_state()
        
        assert state.state_exists() is True


class TestScraperStateAtomicWrite:
    """Test atomic write functionality."""

    def test_atomic_write_uses_temp_file(self, tmp_path):
        """Should write to temp file before renaming."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_file = MagicMock()
            mock_file.name = str(tmp_path / "temp.tmp")
            mock_temp.return_value = mock_file
            
            try:
                state.save_state()
            except:
                pass  # We mocked the temp file
            
            mock_temp.assert_called_once()
            assert mock_temp.call_args[1]['dir'] == state_file.parent

    def test_atomic_write_renames_on_success(self, tmp_path):
        """Should rename temp file to final name on success."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        
        state.save_state()
        
        assert state_file.exists()
        # Should be valid JSON
        with open(state_file, 'r') as f:
            json.load(f)

    def test_atomic_write_cleans_up_temp_on_failure(self, tmp_path):
        """Should clean up temp file if write fails."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        
        # Make json.dump raise an exception
        with patch('json.dump', side_effect=IOError("write failed")):
            with pytest.raises(IOError):
                state.save_state()
        
        # Check no temp files left behind in parent dir
        temp_files = list(state_file.parent.glob("scraper_state_*.tmp"))
        assert len(temp_files) == 0

    def test_atomic_write_not_corrupted_by_crash(self, tmp_path):
        """Original file should remain intact if crash during write."""
        state_file = tmp_path / "state.json"
        
        # First save some valid state
        state1 = ScraperState(
            state_file=state_file,
            circuit_state=CircuitState.OPEN,
            failure_count=5
        )
        state1.save_state()
        
        # Verify we can load it
        loaded1 = state1.load_state()
        assert loaded1["circuit_state"] == "OPEN"
        assert loaded1["failure_count"] == 5
        
        # Simulate a crash during second save by mocking os.rename to fail
        state2 = ScraperState(
            state_file=state_file,
            circuit_state=CircuitState.CLOSED,
            failure_count=0
        )
        
        with patch('os.rename', side_effect=IOError("crash during rename")):
            with pytest.raises(IOError):
                state2.save_state()
        
        # Original file should still be intact and loadable
        loaded2 = state1.load_state()
        assert loaded2["circuit_state"] == "OPEN"  # Not the new value
        assert loaded2["failure_count"] == 5  # Not the new value


class TestScraperStateAtexit:
    """Test atexit handler functionality."""

    def test_atexit_handler_registers(self, tmp_path):
        """Should register with atexit when register_atexit_handler called."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        
        with patch('atexit.register') as mock_register:
            state.register_atexit_handler()
            mock_register.assert_called_once_with(state._atexit_save)

    def test_atexit_handler_only_registers_once(self, tmp_path):
        """Should only register atexit handler once."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        
        with patch('atexit.register') as mock_register:
            state.register_atexit_handler()
            state.register_atexit_handler()
            state.register_atexit_handler()
            mock_register.assert_called_once()

    def test_atexit_save_saves_state(self, tmp_path):
        """_atexit_save should call save_state."""
        state_file = tmp_path / "state.json"
        state = ScraperState(
            state_file=state_file,
            failure_count=5  # Has data worth saving
        )
        
        with patch.object(state, 'save_state') as mock_save:
            state._atexit_save()
            mock_save.assert_called_once()

    def test_atexit_save_skips_empty_state(self, tmp_path):
        """_atexit_save should skip if state is empty/default."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)  # All defaults
        
        with patch.object(state, 'save_state') as mock_save:
            state._atexit_save()
            mock_save.assert_not_called()

    def test_atexit_save_handles_exceptions(self, tmp_path):
        """_atexit_save should not raise exceptions."""
        state_file = tmp_path / "state.json"
        state = ScraperState(
            state_file=state_file,
            failure_count=5
        )
        
        with patch.object(state, 'save_state', side_effect=IOError("disk full")):
            # Should not raise
            state._atexit_save()


class TestScraperStateClear:
    """Test clear_state functionality."""

    def test_clear_state_removes_file(self, tmp_path):
        """Should remove state file if it exists."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        state.save_state()
        
        assert state_file.exists()
        
        state.clear_state()
        
        assert not state_file.exists()

    def test_clear_state_no_error_when_no_file(self, tmp_path):
        """Should not raise error when file doesn't exist."""
        state_file = tmp_path / "state.json"
        state = ScraperState(state_file=state_file)
        
        # Should not raise
        state.clear_state()


class TestScraperStateEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_url_lists(self, tmp_path):
        """Should handle empty URL lists."""
        state_file = tmp_path / "state.json"
        state = ScraperState(
            state_file=state_file,
            pending_urls=[],
            completed_urls=[]
        )
        
        state.save_state()
        loaded = state.load_state()
        
        assert loaded["pending_urls"] == []
        assert loaded["completed_urls"] == []

    def test_many_urls(self, tmp_path):
        """Should handle many URLs."""
        state_file = tmp_path / "state.json"
        urls = [f"http://example.com/{i}" for i in range(1000)]
        state = ScraperState(
            state_file=state_file,
            pending_urls=urls[:500],
            completed_urls=urls[500:]
        )
        
        state.save_state()
        loaded = state.load_state()
        
        assert len(loaded["pending_urls"]) == 500
        assert len(loaded["completed_urls"]) == 500

    def test_unicode_urls(self, tmp_path):
        """Should handle URLs with unicode characters."""
        state_file = tmp_path / "state.json"
        state = ScraperState(
            state_file=state_file,
            pending_urls=["http://example.com/测试", "http://example.com/🎉"],
            completed_urls=["http://example.com/äöü"]
        )
        
        state.save_state()
        loaded = state.load_state()
        
        assert "http://example.com/测试" in loaded["pending_urls"]
        assert "http://example.com/🎉" in loaded["pending_urls"]
        assert "http://example.com/äöü" in loaded["completed_urls"]

    def test_special_float_values(self, tmp_path):
        """Should handle special float values for last_failure_time."""
        state_file = tmp_path / "state.json"
        state = ScraperState(
            state_file=state_file,
            last_failure_time=None
        )
        
        state.save_state()
        loaded = state.load_state()
        
        assert loaded["last_failure_time"] is None
