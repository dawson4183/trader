"""Tests for systemd service and timer files."""
import os
import re
import subprocess
import pytest
from pathlib import Path


class TestServiceFileStructure:
    """Tests for the systemd service file structure and syntax."""
    
    @pytest.fixture
    def service_file_path(self):
        """Return the path to the service file."""
        repo_root = Path(__file__).parent.parent
        return repo_root / "systemd" / "d2iabot-scraper.service"
    
    @pytest.fixture
    def service_content(self, service_file_path):
        """Return the content of the service file."""
        with open(service_file_path, 'r') as f:
            return f.read()
    
    def test_service_file_exists(self, service_file_path):
        """Test that the service file exists."""
        assert service_file_path.exists(), f"Service file not found at {service_file_path}"
    
    def test_unit_section_exists(self, service_content):
        """Test that [Unit] section exists with Description and After."""
        assert "[Unit]" in service_content, "Missing [Unit] section"
        
        # Check for Description
        description_pattern = r'^Description=.+$'
        assert re.search(description_pattern, service_content, re.MULTILINE), \
            "Missing or invalid Description in [Unit]"
        
        # Check for After=network.target
        assert "After=network.target" in service_content, \
            "Missing 'After=network.target' in [Unit]"
    
    def test_service_section_exists(self, service_content):
        """Test that [Service] section exists with required directives."""
        assert "[Service]" in service_content, "Missing [Service] section"
    
    def test_service_type_simple(self, service_content):
        """Test that Type=simple is set."""
        type_pattern = r'^Type=simple$'
        assert re.search(type_pattern, service_content, re.MULTILINE), \
            "Missing or invalid 'Type=simple' in [Service]"
    
    def test_service_user_specified(self, service_content):
        """Test that User is specified."""
        user_pattern = r'^User=\S+$'
        assert re.search(user_pattern, service_content, re.MULTILINE), \
            "Missing or invalid 'User' in [Service]"
    
    def test_working_directory_set(self, service_content):
        """Test that WorkingDirectory is set to repo root."""
        working_dir_pattern = r'^WorkingDirectory=.+$'
        assert re.search(working_dir_pattern, service_content, re.MULTILINE), \
            "Missing 'WorkingDirectory' in [Service]"
    
    def test_exec_start_points_to_venv_python(self, service_content):
        """Test that ExecStart points to venv/bin/python -m trader.cli scrape."""
        # Should point to venv Python and run the scrape command
        execstart_pattern = r'^ExecStart=.*/venv/bin/python.*-m trader\.cli scrape$'
        assert re.search(execstart_pattern, service_content, re.MULTILINE), \
            "ExecStart should point to venv/bin/python -m trader.cli scrape"
    
    def test_restart_on_failure(self, service_content):
        """Test that Restart=on-failure is set."""
        assert "Restart=on-failure" in service_content, \
            "Missing 'Restart=on-failure' in [Service]"
    
    def test_restart_sec_set(self, service_content):
        """Test that RestartSec=30 is set."""
        restart_sec_pattern = r'^RestartSec=30$'
        assert re.search(restart_sec_pattern, service_content, re.MULTILINE), \
            "Missing or invalid 'RestartSec=30' in [Service]"
    
    def test_standard_output_journal(self, service_content):
        """Test that StandardOutput=journal is set."""
        assert "StandardOutput=journal" in service_content, \
            "Missing 'StandardOutput=journal' in [Service]"
    
    def test_standard_error_journal(self, service_content):
        """Test that StandardError=journal is set."""
        assert "StandardError=journal" in service_content, \
            "Missing 'StandardError=journal' in [Service]"
    
    def test_install_section_exists(self, service_content):
        """Test that [Install] section exists with WantedBy."""
        assert "[Install]" in service_content, "Missing [Install] section"
        assert "WantedBy=multi-user.target" in service_content, \
            "Missing 'WantedBy=multi-user.target' in [Install]"
    
    def test_service_file_syntax_valid(self, service_file_path):
        """Test that service file syntax is valid using systemd-analyze."""
        # Skip if systemd-analyze is not available
        try:
            result = subprocess.run(
                ['systemd-analyze', 'verify', str(service_file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            # systemd-analyze verify returns 0 on success
            # Some warnings are acceptable, but no errors
            assert result.returncode == 0, \
                f"Service file has syntax errors: {result.stderr}"
        except FileNotFoundError:
            pytest.skip("systemd-analyze not available on this system")
        except subprocess.TimeoutExpired:
            pytest.skip("systemd-analyze timed out")


class TestTimerFileStructure:
    """Tests for the systemd timer file structure and syntax."""
    
    @pytest.fixture
    def timer_file_path(self):
        """Return the path to the timer file."""
        repo_root = Path(__file__).parent.parent
        return repo_root / "systemd" / "d2iabot-scraper.timer"
    
    @pytest.fixture
    def timer_content(self, timer_file_path):
        """Return the content of the timer file."""
        with open(timer_file_path, 'r') as f:
            return f.read()
    
    def test_timer_file_exists(self, timer_file_path):
        """Test that the timer file exists."""
        assert timer_file_path.exists(), f"Timer file not found at {timer_file_path}"
    
    def test_timer_unit_section_exists(self, timer_content):
        """Test that [Unit] section exists with Description."""
        assert "[Unit]" in timer_content, "Missing [Unit] section"
        
        # Check for Description
        description_pattern = r'^Description=.+$'
        assert re.search(description_pattern, timer_content, re.MULTILINE), \
            "Missing or invalid Description in [Unit]"
    
    def test_timer_section_exists(self, timer_content):
        """Test that [Timer] section exists."""
        assert "[Timer]" in timer_content, "Missing [Timer] section"
    
    def test_timer_on_boot_sec(self, timer_content):
        """Test that OnBootSec=1min is set."""
        onboot_pattern = r'^OnBootSec=1min$'
        assert re.search(onboot_pattern, timer_content, re.MULTILINE), \
            "Missing or invalid 'OnBootSec=1min' in [Timer]"
    
    def test_timer_on_unit_active_sec(self, timer_content):
        """Test that OnUnitActiveSec=15min is set."""
        active_pattern = r'^OnUnitActiveSec=15min$'
        assert re.search(active_pattern, timer_content, re.MULTILINE), \
            "Missing or invalid 'OnUnitActiveSec=15min' in [Timer]"
    
    def test_timer_persistent(self, timer_content):
        """Test that Persistent=true is set."""
        persistent_pattern = r'^Persistent=true$'
        assert re.search(persistent_pattern, timer_content, re.MULTILINE), \
            "Missing or invalid 'Persistent=true' in [Timer]"
    
    def test_timer_unit_reference(self, timer_content):
        """Test that Unit=d2iabot-scraper.service is specified."""
        unit_pattern = r'^Unit=d2iabot-scraper\.service$'
        assert re.search(unit_pattern, timer_content, re.MULTILINE), \
            "Missing or invalid 'Unit=d2iabot-scraper.service' in [Timer]"
    
    def test_timer_install_section_exists(self, timer_content):
        """Test that [Install] section exists with WantedBy."""
        assert "[Install]" in timer_content, "Missing [Install] section"
        assert "WantedBy=timers.target" in timer_content, \
            "Missing 'WantedBy=timers.target' in [Install]"
    
    def test_timer_file_syntax_valid(self, timer_file_path):
        """Test that timer file syntax is valid using systemd-analyze."""
        # Skip if systemd-analyze is not available
        try:
            result = subprocess.run(
                ['systemd-analyze', 'verify', str(timer_file_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            # systemd-analyze verify returns 0 on success
            # Some warnings are acceptable, but no errors
            assert result.returncode == 0, \
                f"Timer file has syntax errors: {result.stderr}"
        except FileNotFoundError:
            pytest.skip("systemd-analyze not available on this system")
        except subprocess.TimeoutExpired:
            pytest.skip("systemd-analyze timed out")


class TestSystemdDirectoryStructure:
    """Tests for the systemd directory structure."""
    
    @pytest.fixture
    def repo_root(self):
        """Return the repository root path."""
        return Path(__file__).parent.parent
    
    def test_systemd_directory_exists(self, repo_root):
        """Test that systemd/ directory exists."""
        systemd_dir = repo_root / "systemd"
        assert systemd_dir.exists(), "systemd/ directory does not exist"
        assert systemd_dir.is_dir(), "systemd/ is not a directory"
    
    def test_service_file_in_systemd_dir(self, repo_root):
        """Test that service file is in systemd/ directory."""
        service_file = repo_root / "systemd" / "d2iabot-scraper.service"
        assert service_file.exists(), "d2iabot-scraper.service not found in systemd/"
    
    def test_timer_file_in_systemd_dir(self, repo_root):
        """Test that timer file is in systemd/ directory."""
        timer_file = repo_root / "systemd" / "d2iabot-scraper.timer"
        assert timer_file.exists(), "d2iabot-scraper.timer not found in systemd/"
