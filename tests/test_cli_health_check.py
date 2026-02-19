"""Tests for the CLI --health-check flag."""
import sys
from unittest.mock import patch
import pytest
from trader.cli import main, create_parser, run_health_check


class TestHealthCheckFlag:
    """Tests for the --health-check flag."""

    def test_health_check_flag_registered(self):
        """Test that --health-check flag is registered in argparse."""
        parser = create_parser()
        args = parser.parse_args(['--health-check'])
        assert args.health_check is True

    def test_health_check_flag_false_by_default(self):
        """Test that --health-check flag defaults to False."""
        parser = create_parser()
        args = parser.parse_args([])
        assert args.health_check is False

    def test_health_check_prints_healthy_when_success(self):
        """Test health check prints 'healthy' on success."""
        with patch('builtins.print') as mock_print:
            result = run_health_check()

        assert result == 0
        mock_print.assert_called_once_with('healthy')

    def test_health_check_exits_zero_when_healthy(self):
        """Test health check returns exit code 0 when healthy."""
        result = run_health_check()
        assert result == 0

    def test_health_check_validates_python_version(self):
        """Test health check validates Python version >= 3.8."""
        # Save original version_info
        original_version_info = sys.version_info

        try:
            # Mock Python version to 3.7
            with patch.object(sys, 'version_info', (3, 7, 0, 'final', 0)):
                with patch('builtins.print') as mock_print:
                    result = run_health_check()

            assert result == 1
            mock_print.assert_called_once()
            printed = mock_print.call_args[0][0]
            assert printed.startswith('unhealthy:')
            assert '3.7' in printed
        finally:
            # Restore original version_info
            sys.version_info = original_version_info  # type: ignore

    def test_health_check_validates_beautifulsoup4(self):
        """Test health check fails when beautifulsoup4 is not importable."""
        with patch.dict('sys.modules', {'bs4': None}):
            with patch('builtins.print') as mock_print:
                result = run_health_check()

        assert result == 1
        mock_print.assert_called_once()
        printed = mock_print.call_args[0][0]
        assert printed.startswith('unhealthy:')
        assert 'beautifulsoup4' in printed

    def test_health_check_validates_lxml(self):
        """Test health check fails when lxml is not importable."""
        with patch.dict('sys.modules', {'lxml': None}):
            with patch('builtins.print') as mock_print:
                result = run_health_check()

        assert result == 1
        mock_print.assert_called_once()
        printed = mock_print.call_args[0][0]
        assert printed.startswith('unhealthy:')
        assert 'lxml' in printed

    def test_health_check_multiple_errors(self):
        """Test health check reports multiple errors."""
        original_version_info = sys.version_info

        try:
            with patch.object(sys, 'version_info', (3, 6, 0, 'final', 0)):
                with patch.dict('sys.modules', {'bs4': None, 'lxml': None}):
                    with patch('builtins.print') as mock_print:
                        result = run_health_check()

            assert result == 1
            mock_print.assert_called_once()
            printed = mock_print.call_args[0][0]
            assert printed.startswith('unhealthy:')
            assert '3.6' in printed
            assert 'beautifulsoup4' in printed
            assert 'lxml' in printed
        finally:
            sys.version_info = original_version_info  # type: ignore


class TestMainWithHealthCheck:
    """Tests for main function with --health-check flag."""

    def test_main_with_health_check_flag(self):
        """Test main with --health-check flag runs health check."""
        with patch('builtins.print') as mock_print:
            result = main(['--health-check'])

        assert result == 0
        mock_print.assert_called_once_with('healthy')

    def test_main_health_check_takes_priority(self):
        """Test --health-check flag takes priority over other args."""
        with patch('builtins.print') as mock_print:
            # Even with other args, health check should run
            result = main(['--health-check', 'scrape', '--html-file', 'test.html'])

        assert result == 0
        mock_print.assert_called_once_with('healthy')

    def test_main_health_check_with_help(self):
        """Test --health-check appears in help output."""
        parser = create_parser()
        help_text = parser.format_help()
        assert '--health-check' in help_text
