"""Tests for scraper alert integration."""
import logging
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from trader.scraper import Scraper
from trader.database import DatabaseConnection


class TestImportAlertModule:
    """Test cases for Scraper.import_alert_module() method."""

    def test_import_alert_module_exists(self) -> None:
        """Verify import_alert_module method exists."""
        scraper = Scraper()
        assert hasattr(scraper, 'import_alert_module')
        assert callable(scraper.import_alert_module)

    def test_import_alert_module_returns_module(self) -> None:
        """Verify import_alert_module returns alert module."""
        scraper = Scraper()
        result = scraper.import_alert_module()
        # Should return the alert module
        assert result is not None
        assert hasattr(result, 'send_alert')

    def test_import_alert_module_caches_result(self) -> None:
        """Verify import_alert_module caches the module."""
        scraper = Scraper()
        first = scraper.import_alert_module()
        second = scraper.import_alert_module()
        assert first is second  # Same object (cached)

    def test_import_alert_module_handles_import_error(self) -> None:
        """Verify import_alert_module handles ImportError gracefully."""
        scraper = Scraper()
        with patch.dict('sys.modules', {'trader.alert': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'trader.alert'")):
                result = scraper.import_alert_module()
                assert result is None


class TestSendCriticalAlert:
    """Test cases for Scraper.send_critical_alert() method."""

    def test_send_critical_alert_exists(self) -> None:
        """Verify send_critical_alert method exists."""
        scraper = Scraper()
        assert hasattr(scraper, 'send_critical_alert')
        assert callable(scraper.send_critical_alert)

    def test_send_critical_alert_avoids_duplicates(self) -> None:
        """Verify duplicate alerts are prevented."""
        scraper = Scraper()
        
        # First send should work
        with patch.object(scraper, 'import_alert_module') as mock_import:
            mock_alert = MagicMock()
            mock_alert.send_alert.return_value = True
            mock_import.return_value = mock_alert
            
            # Mark as already sent
            scraper._alert_sent = True
            
            result = scraper.send_critical_alert("Test message")
            assert result is False  # Should not send duplicate
            mock_alert.send_alert.assert_not_called()

    def test_send_critical_alert_returns_false_when_no_module(self) -> None:
        """Verify send_critical_alert returns False when module unavailable."""
        scraper = Scraper()
        
        with patch.object(scraper, 'import_alert_module', return_value=None):
            result = scraper.send_critical_alert("Test message")
            assert result is False

    def test_send_critical_alert_calls_send_alert(self) -> None:
        """Verify send_critical_alert calls send_alert with correct params."""
        scraper = Scraper()
        
        with patch.object(scraper, 'import_alert_module') as mock_import:
            mock_alert = MagicMock()
            mock_alert.send_alert.return_value = True
            mock_alert.send_alert.__name__ = 'send_alert'
            mock_import.return_value = mock_alert
            
            result = scraper.send_critical_alert("Test critical message")
            
            assert result is True
            mock_alert.send_alert.assert_called_once_with("Test critical message", "critical")
            assert scraper._alert_sent is True

    def test_send_critical_alert_handles_send_failure(self) -> None:
        """Verify send_critical_alert handles failure gracefully."""
        scraper = Scraper()
        
        with patch.object(scraper, 'import_alert_module') as mock_import:
            mock_alert = MagicMock()
            mock_alert.send_alert.return_value = False
            mock_import.return_value = mock_alert
            
            result = scraper.send_critical_alert("Test message")
            assert result is False
            assert scraper._alert_sent is False

    def test_send_critical_alert_handles_exception(self) -> None:
        """Verify send_critical_alert handles exceptions gracefully."""
        scraper = Scraper()
        
        with patch.object(scraper, 'import_alert_module') as mock_import:
            mock_alert = MagicMock()
            mock_alert.send_alert.side_effect = Exception("Send failed")
            mock_import.return_value = mock_alert
            
            result = scraper.send_critical_alert("Test message")
            assert result is False
            assert scraper._alert_sent is False


class TestScrapeWithAlertIntegration:
    """Test cases for Scraper.scrape() alert integration."""

    def test_scrape_method_exists(self) -> None:
        """Verify scrape method exists."""
        scraper = Scraper()
        assert hasattr(scraper, 'scrape')
        assert callable(scraper.scrape)

    def test_scrape_sends_alert_on_failure(self) -> None:
        """Verify scrape sends critical alert when exception occurs."""
        scraper = Scraper()
        
        # Make _do_scrape raise an exception
        def fail_scrape() -> int:
            raise ValueError("Scraping failed!")
        
        scraper._do_scrape = fail_scrape  # type: ignore
        
        with patch.object(scraper, 'send_critical_alert') as mock_alert:
            mock_alert.return_value = True
            
            with pytest.raises(ValueError, match="Scraping failed"):
                scraper.scrape()
            
            # Verify alert was sent with error message and stack trace
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args[0][0]
            assert "Scraping failed" in call_args
            assert "Stack trace" in call_args

    def test_scrape_records_failure_before_alert(self) -> None:
        """Verify scrape records failure before sending alert."""
        scraper = Scraper()
        
        def fail_scrape() -> int:
            raise RuntimeError("Critical error!")
        
        scraper._do_scrape = fail_scrape  # type: ignore
        scraper._alert_sent = False
        
        with patch.object(scraper, 'send_critical_alert', return_value=True):
            with pytest.raises(RuntimeError):
                scraper.scrape()
        
        # Verify failure was recorded
        failures = scraper.get_recent_failures(limit=1)
        assert len(failures) == 1
        assert "Critical error" in failures[0]["error_message"]
        assert failures[0]["level"] == "critical"

    def test_scrape_ends_run_as_failed(self) -> None:
        """Verify scrape marks run as failed after exception."""
        scraper = Scraper()
        
        def fail_scrape() -> int:
            raise Exception("Failure!")
        
        scraper._do_scrape = fail_scrape  # type: ignore
        
        with patch.object(scraper, 'send_critical_alert', return_value=True):
            with pytest.raises(Exception):
                scraper.scrape()
        
        # Verify current_run_id is cleared
        assert scraper.current_run_id is None
        
        # Check run history
        history = scraper.get_run_history(limit=1)
        assert len(history) == 1
        assert history[0]["status"] == "failed"

    def test_scrape_propagates_exception_after_alert(self) -> None:
        """Verify scrape re-raises exception after sending alert."""
        scraper = Scraper()
        
        def fail_scrape() -> int:
            raise ValueError("Original error!")
        
        scraper._do_scrape = fail_scrape  # type: ignore
        
        with patch.object(scraper, 'send_critical_alert', return_value=True):
            with pytest.raises(ValueError, match="Original error"):
                scraper.scrape()

    def test_scrape_alerts_before_raising(self) -> None:
        """Verify alert is sent before exception is raised."""
        scraper = Scraper()
        call_order: list[str] = []
        
        def fail_scrape() -> int:
            raise ValueError("Test error!")
        
        def mock_alert(msg: str) -> bool:
            call_order.append("alert")
            return True
        
        scraper._do_scrape = fail_scrape  # type: ignore
        
        with patch.object(scraper, 'send_critical_alert', side_effect=mock_alert):
            try:
                scraper.scrape()
            except ValueError:
                call_order.append("exception_raised")
        
        assert call_order == ["alert", "exception_raised"]

    def test_scrape_logs_warning_when_alert_fails(self) -> None:
        """Verify warning is logged if alert sending fails."""
        scraper = Scraper()
        
        def fail_scrape() -> int:
            raise ValueError("Error!")
        
        scraper._do_scrape = fail_scrape  # type: ignore
        
        with patch.object(scraper, 'send_critical_alert', return_value=False) as mock_send:
            with patch('trader.scraper.logging.getLogger') as mock_logger_get:
                mock_logger = MagicMock()
                mock_logger_get.return_value = mock_logger
                
                with pytest.raises(ValueError):
                    scraper.scrape()
                
                # Verify warning was logged
                mock_logger.warning.assert_called_once()
                args = mock_logger.warning.call_args[0]
                assert "Failed to send" in args[0]

    def test_scrape_propagates_original_when_alert_exception(self) -> None:
        """Verify original exception propagates even if alert raises exception."""
        scraper = Scraper()
        
        def fail_scrape() -> int:
            raise ValueError("Original error!")
        
        scraper._do_scrape = fail_scrape  # type: ignore
        
        with patch.object(scraper, 'send_critical_alert', side_effect=Exception("Alert failed")):
            with patch('trader.scraper.logging.getLogger') as mock_logger_get:
                mock_logger = MagicMock()
                mock_logger_get.return_value = mock_logger
                
                with pytest.raises(ValueError, match="Original error"):
                    scraper.scrape()
                
                # Verify alert error was logged
                mock_logger.error.assert_called_once()


class TestAlertDuplicationPrevention:
    """Test cases for alert duplication prevention."""

    def test_alert_flag_tracks_sent_status(self) -> None:
        """Verify _alert_sent flag tracks if alert was sent."""
        scraper = Scraper()
        assert scraper._alert_sent is False
        
        # Send an alert
        with patch.object(scraper, 'import_alert_module') as mock_import:
            mock_alert = MagicMock()
            mock_alert.send_alert.return_value = True
            mock_import.return_value = mock_alert
            
            scraper.send_critical_alert("Test")
            assert scraper._alert_sent is True

    def test_reset_alert_flag_exists(self) -> None:
        """Verify reset_alert_flag method exists."""
        scraper = Scraper()
        assert hasattr(scraper, 'reset_alert_flag')
        assert callable(scraper.reset_alert_flag)

    def test_reset_alert_flag_clears_sent_status(self) -> None:
        """Verify reset_alert_flag clears the _alert_sent flag."""
        scraper = Scraper()
        scraper._alert_sent = True
        
        scraper.reset_alert_flag()
        assert scraper._alert_sent is False

    def test_subsequent_alerts_after_reset(self) -> None:
        """Verify alerts can be sent again after reset."""
        scraper = Scraper()
        
        with patch.object(scraper, 'import_alert_module') as mock_import:
            mock_alert = MagicMock()
            mock_alert.send_alert.return_value = True
            mock_import.return_value = mock_alert
            
            # First alert
            scraper.send_critical_alert("First")
            assert scraper._alert_sent is True
            
            # Reset
            scraper.reset_alert_flag()
            assert scraper._alert_sent is False
            
            # Second alert should work
            result = scraper.send_critical_alert("Second")
            assert result is True
            assert scraper._alert_sent is True


class TestScrapeSuccessfulRun:
    """Test cases for successful scraper runs."""

    def test_scrape_completes_successfully(self) -> None:
        """Verify scrape completes successfully without alerts."""
        scraper = Scraper()
        
        # Override _do_scrape to return items
        def success_scrape() -> int:
            return 42
        
        scraper._do_scrape = success_scrape  # type: ignore
        
        with patch.object(scraper, 'send_critical_alert') as mock_alert:
            result = scraper.scrape()
            
            assert result == 42
            mock_alert.assert_not_called()

    def test_scrape_ends_run_as_completed(self) -> None:
        """Verify scrape marks run as completed on success."""
        scraper = Scraper()
        
        def success_scrape() -> int:
            return 100
        
        scraper._do_scrape = success_scrape  # type: ignore
        result = scraper.scrape()
        
        assert result == 100
        
        # Verify run was marked as completed
        history = scraper.get_run_history(limit=1)
        assert len(history) == 1
        assert history[0]["status"] == "completed"
        assert history[0]["items_count"] == 100


class TestAlertWithWebhook:
    """Test cases for alert integration with webhook."""

    def test_alert_includes_error_and_stack_trace(self) -> None:
        """Verify alert message includes error and stack trace."""
        scraper = Scraper()
        
        def fail_scrape() -> int:
            raise ValueError("Test error message")
        
        scraper._do_scrape = fail_scrape  # type: ignore
        
        received_message: str = ""
        
        def capture_alert(msg: str) -> bool:
            nonlocal received_message
            received_message = msg
            return True
        
        with patch.object(scraper, 'send_critical_alert', side_effect=capture_alert):
            with pytest.raises(ValueError):
                scraper.scrape()
        
        # Verify message structure
        assert "Scraper failed with error" in received_message
        assert "Test error message" in received_message
        assert "Stack trace" in received_message
        assert "Traceback" in received_message or "File " in received_message
