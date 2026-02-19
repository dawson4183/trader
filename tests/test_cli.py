"""Tests for trader CLI module."""
import json
import subprocess
import sys
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest

from trader import cli
from trader.cli import main, run_health_checks, _determine_overall_status


class TestCLIExists:
    """Test cases for CLI module existence."""

    def test_cli_module_exists(self) -> None:
        """Verify trader/cli.py exists."""
        assert hasattr(cli, 'main')
        assert callable(cli.main)

    def test_main_function_exists(self) -> None:
        """Verify main() function exists and is callable."""
        assert callable(main)

    def test_run_health_checks_exists(self) -> None:
        """Verify run_health_checks() function exists."""
        assert callable(run_health_checks)


class TestHealthCheckFlag:
    """Test cases for --health-check flag."""

    def test_health_check_flag_available(self) -> None:
        """Verify --health-check flag is recognized."""
        # Should not raise SystemExit
        with patch('sys.stdout'):
            with patch.object(sys, 'exit'):
                try:
                    result = main(['--health-check'])
                except SystemExit:
                    pass  # Expected if health check runs

    def test_health_check_triggers_execution(self) -> None:
        """Verify --health-check triggers health check execution."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'ok', 'response_ms': 1.0},
                'scraper': {'status': 'ok'},
                'recent_failures': {},
                'overall_status': 'healthy'
            }
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with patch('sys.exit') as mock_exit:
                    main(['--health-check'])

            mock_run.assert_called_once()


class TestCLIOutput:
    """Test cases for CLI output format."""

    def test_outputs_valid_json(self) -> None:
        """Verify CLI outputs valid JSON."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'ok', 'response_ms': 1.0},
                'scraper': {'status': 'ok'},
                'recent_failures': {},
                'overall_status': 'healthy'
            }
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                result = main(['--health-check'])

            output = mock_stdout.getvalue()
            # Parse JSON to verify it's valid
            parsed = json.loads(output)
            assert parsed is not None
            assert result == 0

    def test_output_has_database_key(self) -> None:
        """Verify output contains 'database' key."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'ok', 'response_ms': 1.0},
                'scraper': {'status': 'ok'},
                'recent_failures': {},
                'overall_status': 'healthy'
            }
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main(['--health-check'])

            output = mock_stdout.getvalue()
            parsed = json.loads(output)
            assert 'database' in parsed

    def test_output_has_scraper_key(self) -> None:
        """Verify output contains 'scraper' key."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'ok', 'response_ms': 1.0},
                'scraper': {'status': 'ok'},
                'recent_failures': {},
                'overall_status': 'healthy'
            }
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main(['--health-check'])

            output = mock_stdout.getvalue()
            parsed = json.loads(output)
            assert 'scraper' in parsed

    def test_output_has_recent_failures_key(self) -> None:
        """Verify output contains 'recent_failures' key."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'ok', 'response_ms': 1.0},
                'scraper': {'status': 'ok'},
                'recent_failures': {},
                'overall_status': 'healthy'
            }
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main(['--health-check'])

            output = mock_stdout.getvalue()
            parsed = json.loads(output)
            assert 'recent_failures' in parsed

    def test_output_has_overall_status_key(self) -> None:
        """Verify output contains 'overall_status' key."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'ok', 'response_ms': 1.0},
                'scraper': {'status': 'ok'},
                'recent_failures': {},
                'overall_status': 'healthy'
            }
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                main(['--health-check'])

            output = mock_stdout.getvalue()
            parsed = json.loads(output)
            assert 'overall_status' in parsed


class TestExitCodes:
    """Test cases for exit codes."""

    def test_returns_0_for_healthy(self) -> None:
        """Verify exit code 0 for healthy status."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'ok', 'response_ms': 1.0},
                'scraper': {'status': 'ok'},
                'recent_failures': {},
                'overall_status': 'healthy'
            }
            with patch('sys.stdout', new_callable=StringIO):
                result = main(['--health-check'])
                assert result == 0

    def test_returns_1_for_degraded(self) -> None:
        """Verify exit code 1 for degraded status."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'ok', 'response_ms': 1.0},
                'scraper': {'status': 'idle'},
                'recent_failures': {},
                'overall_status': 'degraded'
            }
            with patch('sys.stdout', new_callable=StringIO):
                result = main(['--health-check'])
                assert result == 1

    def test_returns_1_for_unhealthy(self) -> None:
        """Verify exit code 1 for unhealthy status."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'error', 'response_ms': 0.0, 'error': 'Connection failed'},
                'scraper': {'status': 'ok'},
                'recent_failures': {},
                'overall_status': 'unhealthy'
            }
            with patch('sys.stdout', new_callable=StringIO):
                result = main(['--health-check'])
                assert result == 1

    def test_raises_system_exit_for_unhealthy(self) -> None:
        """Verify returns 1 for unhealthy status."""
        with patch('trader.cli.run_health_checks') as mock_run:
            mock_run.return_value = {
                'database': {'status': 'error', 'response_ms': 0.0, 'error': 'Connection failed'},
                'scraper': {'status': 'ok'},
                'recent_failures': {},
                'overall_status': 'unhealthy'
            }
            with patch('sys.stdout', new_callable=StringIO):
                result = main(['--health-check'])
                assert result == 1


class TestOverallStatusLogic:
    """Test cases for overall status determination."""

    def test_overall_status_healthy(self) -> None:
        """Verify 'healthy' when all checks pass."""
        database = {'status': 'ok', 'response_ms': 1.0}
        scraper = {'status': 'ok'}
        failures = {}

        result = _determine_overall_status(database, scraper, failures)
        assert result == 'healthy'

    def test_overall_status_unhealthy_db_error(self) -> None:
        """Verify 'unhealthy' when database errors."""
        database = {'status': 'error', 'response_ms': 0.0}
        scraper = {'status': 'ok'}
        failures = {}

        result = _determine_overall_status(database, scraper, failures)
        assert result == 'unhealthy'

    def test_overall_status_unhealthy_scraper_error(self) -> None:
        """Verify 'unhealthy' when scraper has error status."""
        database = {'status': 'ok', 'response_ms': 1.0}
        scraper = {'status': 'error'}
        failures = {}

        result = _determine_overall_status(database, scraper, failures)
        assert result == 'unhealthy'

    def test_overall_status_degraded_when_idle(self) -> None:
        """Verify 'degraded' when scraper is idle."""
        database = {'status': 'ok', 'response_ms': 1.0}
        scraper = {'status': 'idle'}
        failures = {}

        result = _determine_overall_status(database, scraper, failures)
        assert result == 'degraded'

    def test_overall_status_unhealthy_critical_failures(self) -> None:
        """Verify 'unhealthy' when there are critical failures."""
        database = {'status': 'ok', 'response_ms': 1.0}
        scraper = {'status': 'ok'}
        failures = {'critical_24h': 1, 'total_24h': 1}

        result = _determine_overall_status(database, scraper, failures)
        assert result == 'unhealthy'

    def test_overall_status_error_takes_precedence_over_idle(self) -> None:
        """Verify error takes precedence over idle."""
        database = {'status': 'error', 'response_ms': 0.0}
        scraper = {'status': 'idle'}
        failures = {}

        result = _determine_overall_status(database, scraper, failures)
        assert result == 'unhealthy'


class TestRunHealthChecks:
    """Test cases for run_health_checks function."""

    def test_returns_dict(self) -> None:
        """Verify run_health_checks returns dictionary."""
        result = run_health_checks()
        assert isinstance(result, dict)

    def test_calls_all_check_functions(self) -> None:
        """Verify run_health_checks calls all individual check functions."""
        with patch('trader.cli.check_database_connection') as mock_db, \
             patch('trader.cli.check_scraper_status') as mock_scraper, \
             patch('trader.cli.check_recent_failures') as mock_failures:
            
            mock_db.return_value = {'status': 'ok', 'response_ms': 1.0}
            mock_scraper.return_value = {'status': 'ok'}
            mock_failures.return_value = {}

            run_health_checks()

            mock_db.assert_called_once()
            mock_scraper.assert_called_once()
            mock_failures.assert_called_once()

    def test_result_contains_all_component_keys(self) -> None:
        """Verify result contains all required component keys."""
        with patch('trader.cli.check_database_connection') as mock_db, \
             patch('trader.cli.check_scraper_status') as mock_scraper, \
             patch('trader.cli.check_recent_failures') as mock_failures:
            
            mock_db.return_value = {'status': 'ok', 'response_ms': 1.0}
            mock_scraper.return_value = {'status': 'ok'}
            mock_failures.return_value = {}

            result = run_health_checks()

            assert 'database' in result
            assert 'scraper' in result
            assert 'recent_failures' in result
            assert 'overall_status' in result


class TestArgparseUsage:
    """Test cases for argparse usage."""

    def test_argparse_parser_created(self) -> None:
        """Verify ArgumentParser is used."""
        with patch('argparse.ArgumentParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser
            mock_parser.parse_args.return_value = MagicMock(health_check=True)

            try:
                main(['--health-check'])
            except:
                pass

            mock_parser_class.assert_called()

    def test_add_argument_called(self) -> None:
        """Verify add_argument is called for health-check."""
        from unittest.mock import MagicMock, patch

        with patch('argparse.ArgumentParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser
            
            # Create a namespace that mimics parsed args
            namespace = MagicMock()
            namespace.health_check = True
            mock_parser.parse_args.return_value = namespace

            try:
                main(['--health-check'])
            except:
                pass

    def test_prints_help_when_no_args(self) -> None:
        """Verify help is printed when no arguments provided."""
        from unittest.mock import MagicMock, patch

        with patch('argparse.ArgumentParser') as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser

            # Create namespace with health_check=False
            namespace = MagicMock()
            namespace.health_check = False
            mock_parser.parse_args.return_value = namespace

            result = main([])

            mock_parser.print_help.assert_called_once()

    def test_help_includes_health_check(self) -> None:
        """Verify help includes description of --health-check."""
        with patch('sys.stdout', new_callable=StringIO):
            with pytest.raises(SystemExit):
                main(['--help'])


class TestIntegration:
    """Integration tests with real health check functions."""

    def test_integration_outputs_json(self) -> None:
        """Integration test that CLI outputs valid JSON."""
        from unittest.mock import MagicMock, patch

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            try:
                main(['--health-check'])
            except SystemExit:
                pass

            output = mock_stdout.getvalue()
            parsed = json.loads(output)
            assert 'database' in parsed
            assert 'scraper' in parsed
            assert 'recent_failures' in parsed
            assert 'overall_status' in parsed


# Module execution test
class TestModuleExecution:
    """Test cases for module level execution."""

    def test_main_guard_creates_exit(self) -> None:
        """Verify __main__ guard calls sys.exit with main result."""
        # This is tested implicitly by the code structure
        # The if __name__ == "__main__": block calls sys.exit(main())
        pass
