"""Tests for the systemd install-scraper.sh script."""
import os
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestInstallScriptStructure:
    """Tests for the install script file structure and permissions."""
    
    @pytest.fixture
    def repo_root(self):
        """Return the repository root path."""
        return Path(__file__).parent.parent
    
    @pytest.fixture
    def install_script_path(self, repo_root):
        """Return the path to the install script."""
        return repo_root / "systemd" / "install-scraper.sh"
    
    @pytest.fixture
    def install_script_content(self, install_script_path):
        """Return the content of the install script."""
        with open(install_script_path, 'r') as f:
            return f.read()
    
    def test_install_script_exists(self, install_script_path):
        """Test that install-scraper.sh exists."""
        assert install_script_path.exists(), f"Install script not found at {install_script_path}"
    
    def test_install_script_is_executable(self, install_script_path):
        """Test that install-scraper.sh has executable permissions."""
        assert os.access(install_script_path, os.X_OK), \
            f"Install script is not executable: {install_script_path}"
    
    def test_install_script_has_shebang(self, install_script_content):
        """Test that script has proper shebang (#!/bin/bash)."""
        assert install_script_content.startswith("#!/bin/bash"), \
            "Script should start with #!/bin/bash shebang"
    
    def test_install_script_has_set_e(self, install_script_content):
        """Test that script has 'set -e' for error handling."""
        assert "set -e" in install_script_content, \
            "Script should have 'set -e' for error handling"
    
    def test_install_script_checks_root_privileges(self, install_script_content):
        """Test that script checks for root/sudo privileges."""
        # Should check for root (EUID or id -u)
        assert "EUID" in install_script_content or "id -u" in install_script_content or "whoami" in install_script_content, \
            "Script should check for root privileges (EUID, id -u, or whoami)"
        
        # Should check if running as root
        assert "-ne 0" in install_script_content or "!= 0" in install_script_content or "== 0" in install_script_content, \
            "Script should compare UID to 0"
    
    def test_install_script_exits_on_missing_privileges(self, install_script_content):
        """Test that script exits with error when privileges are missing."""
        assert "exit 1" in install_script_content, \
            "Script should exit with code 1 on error"
        assert "Error:" in install_script_content or "Error" in install_script_content, \
            "Script should output error message"
    
    def test_install_script_copies_service_file(self, install_script_content):
        """Test that script copies d2iabot-scraper.service to /etc/systemd/system/."""
        # Check for cp command with service file
        assert "d2iabot-scraper.service" in install_script_content, \
            "Script should reference d2iabot-scraper.service"
        assert "/etc/systemd/system" in install_script_content, \
            "Script should reference /etc/systemd/system"
        assert "cp " in install_script_content, \
            "Script should have cp command"
    
    def test_install_script_copies_timer_file(self, install_script_content):
        """Test that script copies d2iabot-scraper.timer to /etc/systemd/system/."""
        assert "d2iabot-scraper.timer" in install_script_content, \
            "Script should reference d2iabot-scraper.timer"
        assert "cp " in install_script_content, \
            "Script should have cp command"
    
    def test_install_script_runs_daemon_reload(self, install_script_content):
        """Test that script runs systemctl daemon-reload."""
        assert "daemon-reload" in install_script_content, \
            "Script should run systemctl daemon-reload"
        assert "systemctl" in install_script_content, \
            "Script should use systemctl"
    
    def test_install_script_enables_timer(self, install_script_content):
        """Test that script enables d2iabot-scraper.timer."""
        assert "systemctl enable d2iabot-scraper.timer" in install_script_content, \
            "Script should run 'systemctl enable d2iabot-scraper.timer'"
    
    def test_install_script_starts_timer(self, install_script_content):
        """Test that script starts d2iabot-scraper.timer."""
        assert "systemctl start d2iabot-scraper.timer" in install_script_content, \
            "Script should run 'systemctl start d2iabot-scraper.timer'"
    
    def test_install_script_outputs_success_message(self, install_script_content):
        """Test that script outputs success message."""
        assert "success" in install_script_content.lower() or "Success" in install_script_content or "completed" in install_script_content.lower(), \
            "Script should output success message"
    
    def test_install_script_has_status_instructions(self, install_script_content):
        """Test that script includes instructions to check status."""
        assert "systemctl status" in install_script_content, \
            "Script should include instructions to check status with systemctl status"
    
    def test_install_script_checks_source_files_exist(self, install_script_content):
        """Test that script checks if source files exist before copying."""
        assert "-f" in install_script_content or "test -f" in install_script_content, \
            "Script should check if source files exist (-f test)"
    
    def test_install_script_checks_systemd_available(self, install_script_content):
        """Test that script checks if systemctl is available."""
        assert "systemctl" in install_script_content, \
            "Script should reference systemctl"
        assert "command -v" in install_script_content or "which" in install_script_content or "type" in install_script_content, \
            "Script should check if systemctl command is available"


class TestInstallScriptShellcheck:
    """Tests for shellcheck validation of the install script."""
    
    @pytest.fixture
    def install_script_path(self):
        """Return the path to the install script."""
        repo_root = Path(__file__).parent.parent
        return repo_root / "systemd" / "install-scraper.sh"
    
    def test_install_script_passes_shellcheck(self, install_script_path):
        """Test that install script passes shellcheck validation."""
        # Skip if shellcheck is not available
        try:
            result = subprocess.run(
                ['shellcheck', str(install_script_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            # shellcheck returns 0 on success
            assert result.returncode == 0, \
                f"shellcheck found issues:\n{result.stdout}\n{result.stderr}"
        except FileNotFoundError:
            pytest.skip("shellcheck not available on this system")
        except subprocess.TimeoutExpired:
            pytest.skip("shellcheck timed out")


class TestInstallScriptInSystemdDir:
    """Tests for install script location."""
    
    @pytest.fixture
    def repo_root(self):
        """Return the repository root path."""
        return Path(__file__).parent.parent
    
    def test_install_script_in_systemd_dir(self, repo_root):
        """Test that install script is in systemd/ directory."""
        install_script = repo_root / "systemd" / "install-scraper.sh"
        assert install_script.exists(), "install-scraper.sh not found in systemd/"
