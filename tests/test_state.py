"""Tests for the state management module."""

import unittest
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from trader.state import StateManager


class TestStateManagerInitialization(unittest.TestCase):
    """Test cases for StateManager initialization."""

    def test_default_values(self) -> None:
        """StateManager should have sensible defaults."""
        sm = StateManager()
        self.assertEqual(sm.url, "")
        self.assertEqual(sm.page, 1)
        self.assertEqual(sm.items_processed, 0)
        self.assertEqual(sm.retry_count, 0)
        self.assertEqual(sm.auto_save_interval, 10)
        self.assertIsNone(sm.filepath)

    def test_custom_values(self) -> None:
        """StateManager should accept custom configuration."""
        sm = StateManager(
            url="https://example.com",
            page=5,
            items_processed=100,
            retry_count=3,
            auto_save_interval=20,
            filepath="/tmp/state.json"
        )
        self.assertEqual(sm.url, "https://example.com")
        self.assertEqual(sm.page, 5)
        self.assertEqual(sm.items_processed, 100)
        self.assertEqual(sm.retry_count, 3)
        self.assertEqual(sm.auto_save_interval, 20)
        self.assertEqual(sm.filepath, "/tmp/state.json")


class TestStateManagerDict(unittest.TestCase):
    """Test cases for state dictionary conversion."""

    def test_to_dict(self) -> None:
        """to_dict should return state with timestamp."""
        sm = StateManager(
            url="https://example.com",
            page=3,
            items_processed=50,
            retry_count=2
        )
        
        with patch('time.time', return_value=1234567890.0):
            result = sm.to_dict()
        
        self.assertEqual(result["url"], "https://example.com")
        self.assertEqual(result["page"], 3)
        self.assertEqual(result["items_processed"], 50)
        self.assertEqual(result["retry_count"], 2)
        self.assertEqual(result["timestamp"], 1234567890.0)

    def test_from_dict(self) -> None:
        """from_dict should load state from dictionary."""
        sm = StateManager()
        data = {
            "url": "https://example.com",
            "page": 10,
            "items_processed": 200,
            "retry_count": 5
        }
        
        sm.from_dict(data)
        
        self.assertEqual(sm.url, "https://example.com")
        self.assertEqual(sm.page, 10)
        self.assertEqual(sm.items_processed, 200)
        self.assertEqual(sm.retry_count, 5)

    def test_from_dict_with_defaults(self) -> None:
        """from_dict should use defaults for missing fields."""
        sm = StateManager()
        data = {"url": "https://example.com"}
        
        sm.from_dict(data)
        
        self.assertEqual(sm.url, "https://example.com")
        self.assertEqual(sm.page, 1)  # default
        self.assertEqual(sm.items_processed, 0)  # default
        self.assertEqual(sm.retry_count, 0)  # default


class TestStateManagerSave(unittest.TestCase):
    """Test cases for save functionality."""

    def setUp(self) -> None:
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.filepath = os.path.join(self.temp_dir, "state.json")

    def tearDown(self) -> None:
        """Clean up temporary files."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_save_creates_file(self) -> None:
        """save should create JSON file."""
        sm = StateManager(url="https://example.com", page=5)
        sm.save(self.filepath)
        
        self.assertTrue(os.path.exists(self.filepath))

    def test_save_writes_correct_data(self) -> None:
        """save should write correct JSON data."""
        sm = StateManager(
            url="https://example.com/page5",
            page=5,
            items_processed=42,
            retry_count=3
        )
        
        with patch('time.time', return_value=1234567890.0):
            sm.save(self.filepath)
        
        with open(self.filepath, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(data["url"], "https://example.com/page5")
        self.assertEqual(data["page"], 5)
        self.assertEqual(data["items_processed"], 42)
        self.assertEqual(data["retry_count"], 3)
        self.assertEqual(data["timestamp"], 1234567890.0)

    def test_save_uses_default_filepath(self) -> None:
        """save should use instance filepath if none provided."""
        sm = StateManager(filepath=self.filepath, url="https://test.com")
        sm.save()
        
        with open(self.filepath, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(data["url"], "https://test.com")

    def test_save_raises_without_filepath(self) -> None:
        """save should raise ValueError if no filepath available."""
        sm = StateManager()
        
        with self.assertRaises(ValueError) as ctx:
            sm.save()
        
        self.assertIn("No filepath provided", str(ctx.exception))

    def test_save_creates_directories(self) -> None:
        """save should create parent directories if needed."""
        nested_path = os.path.join(self.temp_dir, "nested", "deep", "state.json")
        sm = StateManager(url="https://example.com")
        
        sm.save(nested_path)
        
        self.assertTrue(os.path.exists(nested_path))


class TestStateManagerLoad(unittest.TestCase):
    """Test cases for load functionality."""

    def setUp(self) -> None:
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.filepath = os.path.join(self.temp_dir, "state.json")

    def tearDown(self) -> None:
        """Clean up temporary files."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_load_returns_false_if_file_missing(self) -> None:
        """load should return False if file doesn't exist."""
        sm = StateManager()
        
        result = sm.load(self.filepath)
        
        self.assertFalse(result)

    def test_load_restores_state(self) -> None:
        """load should restore state from JSON file."""
        # First save some state
        original = StateManager(
            url="https://example.com/loaded",
            page=7,
            items_processed=150,
            retry_count=4
        )
        original.save(self.filepath)
        
        # Now load into new StateManager
        sm = StateManager()
        result = sm.load(self.filepath)
        
        self.assertTrue(result)
        self.assertEqual(sm.url, "https://example.com/loaded")
        self.assertEqual(sm.page, 7)
        self.assertEqual(sm.items_processed, 150)
        self.assertEqual(sm.retry_count, 4)

    def test_load_uses_default_filepath(self) -> None:
        """load should use instance filepath if none provided."""
        # Save with default filepath
        sm1 = StateManager(filepath=self.filepath, url="https://default.com")
        sm1.save()
        
        # Load using default
        sm2 = StateManager(filepath=self.filepath)
        result = sm2.load()
        
        self.assertTrue(result)
        self.assertEqual(sm2.url, "https://default.com")

    def test_load_raises_without_filepath(self) -> None:
        """load should raise ValueError if no filepath available."""
        sm = StateManager()
        
        with self.assertRaises(ValueError) as ctx:
            sm.load()
        
        self.assertIn("No filepath provided", str(ctx.exception))


class TestStateManagerAutoSave(unittest.TestCase):
    """Test cases for auto-save functionality."""

    def setUp(self) -> None:
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.filepath = os.path.join(self.temp_dir, "state.json")

    def tearDown(self) -> None:
        """Clean up temporary files."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_auto_save_triggers_at_interval(self) -> None:
        """record_item should trigger auto-save at interval."""
        sm = StateManager(
            auto_save_interval=5,
            filepath=self.filepath,
            url="https://example.com"
        )
        
        # Record 4 items - no save yet
        for _ in range(4):
            result = sm.record_item()
            self.assertFalse(result)
        
        self.assertFalse(os.path.exists(self.filepath))
        
        # 5th item triggers save
        result = sm.record_item()
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.filepath))

    def test_auto_save_disabled_when_zero(self) -> None:
        """Auto-save should be disabled when interval is 0."""
        sm = StateManager(
            auto_save_interval=0,
            filepath=self.filepath,
            url="https://example.com"
        )
        
        # Record many items - no auto-save
        for _ in range(100):
            result = sm.record_item()
            self.assertFalse(result)
        
        self.assertFalse(os.path.exists(self.filepath))

    def test_auto_save_resets_counter(self) -> None:
        """Auto-save should reset counter after save."""
        sm = StateManager(
            auto_save_interval=3,
            filepath=self.filepath,
            url="https://example.com"
        )
        
        # First batch
        for _ in range(3):
            sm.record_item()
        
        # Next 2 should not trigger
        for _ in range(2):
            result = sm.record_item()
            self.assertFalse(result)
        
        # 3rd triggers again
        result = sm.record_item()
        self.assertTrue(result)

    def test_record_item_increments_counter(self) -> None:
        """record_item should increment items_processed."""
        sm = StateManager()
        
        self.assertEqual(sm.items_processed, 0)
        sm.record_item()
        self.assertEqual(sm.items_processed, 1)
        sm.record_item()
        self.assertEqual(sm.items_processed, 2)


class TestStateManagerUpdate(unittest.TestCase):
    """Test cases for update functionality."""

    def test_update_url(self) -> None:
        """update should update URL."""
        sm = StateManager()
        sm.update(url="https://new.com")
        self.assertEqual(sm.url, "https://new.com")

    def test_update_page(self) -> None:
        """update should update page."""
        sm = StateManager(page=1)
        sm.update(page=5)
        self.assertEqual(sm.page, 5)

    def test_update_retry_count(self) -> None:
        """update should update retry_count."""
        sm = StateManager()
        sm.update(retry_count=3)
        self.assertEqual(sm.retry_count, 3)

    def test_update_partial(self) -> None:
        """update should only update provided fields."""
        sm = StateManager(url="https://old.com", page=1, retry_count=0)
        sm.update(page=10)
        
        self.assertEqual(sm.url, "https://old.com")  # unchanged
        self.assertEqual(sm.page, 10)  # updated
        self.assertEqual(sm.retry_count, 0)  # unchanged

    def test_update_none_values_ignored(self) -> None:
        """update should ignore None values."""
        sm = StateManager(url="https://example.com", page=5)
        sm.update(url=None, page=None, retry_count=None)
        
        self.assertEqual(sm.url, "https://example.com")
        self.assertEqual(sm.page, 5)


class TestStateManagerCrashSave(unittest.TestCase):
    """Test cases for crash save functionality."""

    def setUp(self) -> None:
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.filepath = os.path.join(self.temp_dir, "state.json")

    def tearDown(self) -> None:
        """Clean up temporary files."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_save_on_crash_saves_state(self) -> None:
        """save_on_crash should save state for crash recovery."""
        sm = StateManager(
            filepath=self.filepath,
            url="https://crash.com",
            page=99,
            items_processed=1000
        )
        
        sm.save_on_crash()
        
        with open(self.filepath, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(data["url"], "https://crash.com")
        self.assertEqual(data["page"], 99)
        self.assertEqual(data["items_processed"], 1000)

    def test_save_on_crash_no_exception(self) -> None:
        """save_on_crash should not raise exceptions."""
        sm = StateManager()
        
        # No filepath, but should not raise
        try:
            sm.save_on_crash()
        except Exception as e:
            self.fail(f"save_on_crash raised an exception: {e}")

    def test_save_on_crash_ignores_errors(self) -> None:
        """save_on_crash should ignore save errors gracefully."""
        sm = StateManager(
            filepath="/nonexistent/path/that/cannot/be/created/state.json",
            url="https://example.com"
        )
        
        # Should not raise even though path is invalid
        try:
            sm.save_on_crash()
        except Exception as e:
            self.fail(f"save_on_crash raised an exception: {e}")


class TestStateManagerTimestamp(unittest.TestCase):
    """Test cases for timestamp functionality."""

    def test_get_timestamp_from_dict(self) -> None:
        """get_timestamp should return timestamp from current state."""
        sm = StateManager()
        
        with patch('time.time', return_value=1234567890.0):
            timestamp = sm.get_timestamp()
        
        self.assertEqual(timestamp, 1234567890.0)


class TestStateManagerRepr(unittest.TestCase):
    """Test cases for string representation."""

    def test_repr(self) -> None:
        """__repr__ should show state information."""
        sm = StateManager(
            url="https://example.com",
            page=5,
            items_processed=100,
            retry_count=2
        )
        
        result = repr(sm)
        
        self.assertIn("StateManager", result)
        self.assertIn("https://example.com", result)
        self.assertIn("page=5", result)
        self.assertIn("items_processed=100", result)
        self.assertIn("retry_count=2", result)


class TestStateManagerIntegration(unittest.TestCase):
    """Integration tests for complete state lifecycle."""

    def setUp(self) -> None:
        """Create temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.filepath = os.path.join(self.temp_dir, "scraper_state.json")

    def tearDown(self) -> None:
        """Clean up temporary files."""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_full_scraper_workflow(self) -> None:
        """Test complete scraper workflow with state management."""
        # Step 1: Create fresh state
        sm = StateManager(
            filepath=self.filepath,
            auto_save_interval=10,
            url="https://example.com/page1",
            page=1
        )
        
        # Step 2: Simulate processing items
        # Item 0-9: no auto-save, still on page 1
        for i in range(10):
            sm.record_item()
        
        # After item 10 (count=10), auto-save triggers with page1
        # Update to page 2 after first batch
        sm.update(url="https://example.com/page2", page=2)
        
        # Item 11-20: next batch
        for i in range(10):
            sm.record_item()
        
        # After item 20 (count=20), auto-save triggers with page2
        # Update to page 3
        sm.update(url="https://example.com/page3", page=3)
        
        # Item 21-25: final batch (no auto-save until 30)
        for i in range(5):
            sm.record_item()
        
        # Step 3: Verify auto-saves happened
        self.assertTrue(os.path.exists(self.filepath))
        
        # Step 4: Simulate crash and restart
        sm2 = StateManager(filepath=self.filepath, auto_save_interval=10)
        loaded = sm2.load()
        
        self.assertTrue(loaded)
        # Should have saved at item 20 with page2
        self.assertEqual(sm2.items_processed, 20)
        self.assertEqual(sm2.url, "https://example.com/page2")
        self.assertEqual(sm2.page, 2)
        
        # Step 5: Continue from where we left off
        for i in range(15):
            sm2.record_item()
        
        self.assertEqual(sm2.items_processed, 35)  # 20 + 15

    def test_resume_from_crash(self) -> None:
        """Test resuming from a crash state."""
        # Simulate crash during processing
        crashed = StateManager(
            filepath=self.filepath,
            url="https://example.com/items/150",
            page=15,
            items_processed=150,
            retry_count=2
        )
        crashed.save_on_crash()
        
        # New instance loads crash state
        resumed = StateManager(filepath=self.filepath)
        resumed.load()
        
        self.assertEqual(resumed.url, "https://example.com/items/150")
        self.assertEqual(resumed.page, 15)
        self.assertEqual(resumed.items_processed, 150)
        self.assertEqual(resumed.retry_count, 2)

    def test_startup_load_if_exists(self) -> None:
        """Load state on startup if file exists, otherwise start fresh."""
        # First scenario: no existing state
        sm1 = StateManager(filepath=self.filepath, auto_save_interval=5)
        result = sm1.load()
        self.assertFalse(result)  # No file exists
        self.assertEqual(sm1.items_processed, 0)
        self.assertEqual(sm1.page, 1)  # default
        
        # Process some items
        for _ in range(12):
            sm1.record_item()
        
        # Second scenario: state exists, load it
        sm2 = StateManager(filepath=self.filepath, auto_save_interval=5)
        result = sm2.load()
        self.assertTrue(result)  # File exists
        self.assertEqual(sm2.items_processed, 10)  # auto-saved at 10


if __name__ == "__main__":
    unittest.main()
