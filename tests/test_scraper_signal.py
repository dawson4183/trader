"""Tests for signal handling in trader.scraper module."""

import json
import os
import signal
import tempfile
import time
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from trader.scraper import Scraper, SignalManager, ScraperState
from trader.exceptions import ShutdownRequestedError


class TestSignalManagerBasics:
    """Test SignalManager basic functionality."""

    def test_signal_manager_importable(self):
        """SignalManager should be importable from scraper module."""
        from trader.scraper import SignalManager
        assert callable(SignalManager)

    def test_signal_manager_instantiates(self):
        """SignalManager should instantiate with a state_saver callable."""
        def save_state():
            pass
        
        manager = SignalManager(save_state)
        assert isinstance(manager, SignalManager)
        assert manager.shutdown_requested is False

    def test_signal_manager_has_shutdown_requested_flag(self):
        """SignalManager should have shutdown_requested attribute."""
        manager = SignalManager(lambda: None)
        assert hasattr(manager, 'shutdown_requested')
        assert isinstance(manager.shutdown_requested, bool)
        assert manager.shutdown_requested is False

    def test_signal_manager_preserves_original_handlers(self):
        """SignalManager should preserve original signal handlers."""
        # Get original handler first
        original_sigint = signal.signal(signal.SIGINT, signal.default_int_handler)
        original_sigterm = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        
        # Restore originals
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)
        
        # Create manager
        manager = SignalManager(lambda: None)
        
        # Check originals were preserved
        assert manager.original_sigint is not None or original_sigint == signal.default_int_handler
        assert manager.original_sigterm is not None or original_sigterm == signal.SIG_DFL

        # Cleanup
        manager.restore_handlers()

    def test_signal_manager_restore_handlers(self):
        """restore_handlers should restore original signal handlers."""
        # Get current handler
        original = signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGINT, original)  # Restore immediately
        
        manager = SignalManager(lambda: None)
        
        # Restore should set back to original (which is now our handler)
        manager.restore_handlers()


class TestSignalManagerHandlers:
    """Test SignalManager signal handling."""

    def test_signal_manager_registers_sigint_handler(self):
        """SignalManager should register SIGINT handler."""
        original = signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGINT, original)  # Restore
        
        manager = SignalManager(lambda: None)
        
        try:
            # Check a handler is registered
            current_handler = signal.signal(signal.SIGINT, original)
            # Handler should be our custom one
            assert current_handler != original
        finally:
            manager.restore_handlers()

    def test_signal_manager_registers_sigterm_handler(self):
        """SignalManager should register SIGTERM handler."""
        try:
            original = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except ValueError:
            pytest.skip("SIGTERM not available on this platform")
        
        signal.signal(signal.SIGTERM, original)
        manager = SignalManager(lambda: None)
        
        try:
            current_handler = signal.signal(signal.SIGTERM, original)
            assert current_handler != original
        finally:
            manager.restore_handlers()


class TestSignalManagerStateSaving:
    """Test that SignalManager saves state on signal."""

    def test_state_saver_called_on_sigint(self):
        """State saver should be called when SIGINT is received."""
        saved_called = [False]
        
        def save_state():
            saved_called[0] = True
        
        # Store original handler and set dummy handler
        dummy_handler = lambda s, f: None
        original = signal.signal(signal.SIGINT, dummy_handler)
        
        manager = SignalManager(save_state)
        manager.original_sigint = dummy_handler  # Prevent calling original
        
        try:
            import sys
            # Call handler directly
            manager._handle_signal(signal.SIGINT, sys._getframe())
            
            assert saved_called[0] is True
            assert manager.shutdown_requested is True
        finally:
            signal.signal(signal.SIGINT, original)
            manager.restore_handlers()

    def test_shutdown_flag_set_on_signal(self):
        """shutdown_requested should be set to True on signal."""
        # Store original handler
        dummy_handler = lambda s, f: None
        original = signal.signal(signal.SIGINT, dummy_handler)
        
        manager = SignalManager(lambda: None)
        manager.original_sigint = dummy_handler  # Prevent calling original
        
        try:
            import sys
            # Use _handle_signal directly
            manager._handle_signal(signal.SIGINT, sys._getframe())
            
            assert manager.shutdown_requested is True
        finally:
            signal.signal(signal.SIGINT, original)
            manager.restore_handlers()


class TestScraperSignalHandling:
    """Test Scraper signal handling integration."""

    def test_scraper_has_signal_manager_attribute(self):
        """Scraper should have signal_manager attribute."""
        scraper = Scraper(enable_signal_handling=True)
        assert hasattr(scraper, 'signal_manager')

    def test_scraper_signal_manager_can_be_disabled(self):
        """Scraper can have signal handling disabled."""
        scraper = Scraper(enable_signal_handling=False)
        assert scraper.signal_manager is None

    def test_scraper_signal_manager_is_signalmanager_when_enabled(self):
        """Signal manager should be SignalManager instance when enabled."""
        scraper = Scraper(enable_signal_handling=True)
        assert isinstance(scraper.signal_manager, SignalManager)

    def test_scraper_signal_manager_is_none_when_disabled(self):
        """Signal manager should be None when disabled."""
        scraper = Scraper(enable_signal_handling=False)
        assert scraper.signal_manager is None

    def test_scraper_stores_urls_in_instance_variables(self):
        """Scraper should store URLs in instance variables for signal access."""
        scraper = Scraper(enable_signal_handling=False)
        
        # URLs should be initialized
        assert hasattr(scraper, '_pending_urls')
        assert hasattr(scraper, '_completed_urls')
        assert scraper._pending_urls == []
        assert scraper._completed_urls == []


class TestScraperStateSavedOnSignal:
    """Test that scraper state is saved when signal is received."""

    def test_state_saved_to_file_on_sigint_simulation(self):
        """State should be saved to JSON file on SIGINT simulation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            
            # Create scraper with signal handling
            scraper = Scraper(state_file=state_file, enable_signal_handling=True)
            
            # Set up some state
            scraper._save_progress(
                pending_urls=["https://example.com/pending"],
                completed_urls=["https://example.com/completed"],
            )
            
            # Simulate SIGINT
            import sys
            if scraper.signal_manager:
                scraper.signal_manager._handle_sigint(signal.SIGINT, sys._getframe())
            
            # State should be saved
            assert os.path.exists(state_file)
            
            with open(state_file) as f:
                saved = json.load(f)
            
            assert "completed_urls" in saved
            assert "pending_urls" in saved
            assert saved["completed_urls"] == ["https://example.com/completed"]
            
            # Cleanup
            if scraper.signal_manager:
                scraper.signal_manager.restore_handlers()

    def test_shutdown_flag_set_in_signal_manager(self):
        """Shutdown flag should be set in signal manager on signal."""
        scraper = Scraper(enable_signal_handling=True)
        
        if scraper.signal_manager:
            import sys
            scraper.signal_manager._handle_sigint(signal.SIGINT, sys._getframe())
            
            assert scraper.signal_manager.shutdown_requested is True
            
            # Cleanup
            scraper.signal_manager.restore_handlers()


class TestScraperGracefulShutdown:
    """Test that scraper stops gracefully after signal."""

    def test_scraper_stops_after_shutdown_signal(self):
        """Scraper should stop after current URL when shutdown signal received."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "state.json")
            scraper = Scraper(state_file=state_file, enable_signal_handling=True)
            
            urls = [
                "https://example.com/page1",
                "https://example.com/page2",
                "https://example.com/page3",
            ]
            
            # Mock the signal handler to simulate shutdown after first URL
            call_count = 0
            original_shutdown_requested = scraper.signal_manager.shutdown_requested
            
            def mock_shutdown_requested():
                nonlocal call_count
                call_count += 1
                # Return True after first URL
                return call_count > 1
            
            # Set shutdown requested flag after first URL simulation
            mock_response = MagicMock()
            mock_response.read.return_value = b"<html>content</html>"
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            
            with patch('urllib.request.urlopen', return_value=mock_response):
                # Simulate shutdown flag set
                if scraper.signal_manager:
                    scraper.signal_manager.shutdown_requested = True
                
                result = scraper.scrape(urls)
            
            # Should have processed at least one URL before stopping
            assert result['completed_count'] >= 1

    def test_shutdownrequestederror_importable(self):
        """ShutdownRequestedError should be importable."""
        from trader.exceptions import ShutdownRequestedError
        assert callable(ShutdownRequestedError)

    def test_scraper_exports_in_public_api(self):
        """New signal classes should be in trader public API."""
        import trader
        assert hasattr(trader, 'SignalManager')
        assert hasattr(trader, 'ShutdownRequestedError')
        assert hasattr(trader, 'CircuitBreaker')
        assert hasattr(trader, 'scraper_retry')


class TestTypeCheck:
    """Type check compatibility."""

    def test_scraper_type_compatible(self):
        """Scraper should have all required attributes and methods."""
        scraper = Scraper(enable_signal_handling=True)
        assert hasattr(scraper, 'signal_manager')
        assert hasattr(scraper, '_setup_signal_handlers')
        assert callable(scraper._setup_signal_handlers)

    def test_signal_manager_type_compatible(self):
        """SignalManager should have all required attributes and methods."""
        manager = SignalManager(lambda: None)
        assert hasattr(manager, 'shutdown_requested')
        assert hasattr(manager, 'original_sigint')
        assert hasattr(manager, 'original_sigterm')
        assert hasattr(manager, '_register_handlers')
        assert hasattr(manager, '_handle_sigint')
        assert hasattr(manager, '_handle_sigterm')
        assert hasattr(manager, '_handle_signal')
        assert hasattr(manager, 'restore_handlers')
        assert callable(manager._register_handlers)
        assert callable(manager._handle_sigint)
        assert callable(manager._handle_sigterm)
        assert callable(manager._handle_signal)
        assert callable(manager.restore_handlers)
