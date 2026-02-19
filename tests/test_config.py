"""Tests for trader.config module."""

import os
import importlib
import pytest

import trader.config as config


class TestConfigDefaults:
    """Test that config loads correct default values."""

    def test_log_level_defaults_to_info(self):
        """LOG_LEVEL should default to 'INFO' when not set."""
        assert config.LOG_LEVEL == "INFO"

    def test_log_retention_days_defaults_to_7(self):
        """LOG_RETENTION_DAYS should default to 7 when not set."""
        assert config.LOG_RETENTION_DAYS == 7
        assert isinstance(config.LOG_RETENTION_DAYS, int)

    def test_log_file_path_is_set(self):
        """LOG_FILE_PATH should be set to 'logs/trader.log'."""
        assert config.LOG_FILE_PATH == "logs/trader.log"

    def test_webhook_url_graceful_handling(self):
        """WEBHOOK_URL should be None when not set in environment."""
        assert config.WEBHOOK_URL is None

    def test_log_format_is_set(self):
        """LOG_FORMAT should be a valid JSON format string."""
        assert config.LOG_FORMAT is not None
        assert isinstance(config.LOG_FORMAT, str)
        assert "timestamp" in config.LOG_FORMAT
        assert "level" in config.LOG_FORMAT
        assert "message" in config.LOG_FORMAT


class TestConfigEnvironmentVariables:
    """Test that config correctly reads from environment variables."""

    def test_log_level_from_env(self, monkeypatch):
        """LOG_LEVEL should read from LOG_LEVEL environment variable."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        # Reload module to pick up new env var
        importlib.reload(config)
        assert config.LOG_LEVEL == "DEBUG"

    def test_log_retention_days_from_env(self, monkeypatch):
        """LOG_RETENTION_DAYS should read from LOG_RETENTION_DAYS environment variable."""
        monkeypatch.setenv("LOG_RETENTION_DAYS", "14")
        importlib.reload(config)
        assert config.LOG_RETENTION_DAYS == 14

    def test_webhook_url_from_env(self, monkeypatch):
        """WEBHOOK_URL should read from WEBHOOK_URL environment variable."""
        test_url = "https://hooks.example.com/alerts"
        monkeypatch.setenv("WEBHOOK_URL", test_url)
        importlib.reload(config)
        assert config.WEBHOOK_URL == test_url

    def test_log_format_from_env(self, monkeypatch):
        """LOG_FORMAT should read from LOG_FORMAT environment variable."""
        custom_format = '{"ts": "%(asctime)s", "lvl": "%(levelname)s"}'
        monkeypatch.setenv("LOG_FORMAT", custom_format)
        importlib.reload(config)
        assert config.LOG_FORMAT == custom_format


class TestConfigEdgeCases:
    """Test edge cases and error handling."""

    def test_log_retention_days_invalid_value(self, monkeypatch):
        """Invalid LOG_RETENTION_DAYS should raise ValueError."""
        monkeypatch.setenv("LOG_RETENTION_DAYS", "not_a_number")
        with pytest.raises(ValueError):
            importlib.reload(config)

    def test_log_retention_days_zero(self, monkeypatch):
        """LOG_RETENTION_DAYS can be set to 0."""
        monkeypatch.setenv("LOG_RETENTION_DAYS", "0")
        importlib.reload(config)
        assert config.LOG_RETENTION_DAYS == 0
