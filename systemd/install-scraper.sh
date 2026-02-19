#!/bin/bash
# Installation script for D2IA Bot Scraper systemd service and timer
# This script copies service/unit files to /etc/systemd/system/ and enables the timer

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source and destination paths
SERVICE_FILE="$SCRIPT_DIR/d2iabot-scraper.service"
TIMER_FILE="$SCRIPT_DIR/d2iabot-scraper.timer"
SYSTEMD_DIR="/etc/systemd/system"

# Check for root/sudo privileges
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}Error: This script must be run as root or with sudo privileges${NC}" >&2
        echo "Usage: sudo $0" >&2
        exit 1
    fi
}

# Check if source files exist
check_source_files() {
    if [[ ! -f "$SERVICE_FILE" ]]; then
        echo -e "${RED}Error: Service file not found: $SERVICE_FILE${NC}" >&2
        exit 1
    fi

    if [[ ! -f "$TIMER_FILE" ]]; then
        echo -e "${RED}Error: Timer file not found: $TIMER_FILE${NC}" >&2
        exit 1
    fi
}

# Check if systemd is available
check_systemd() {
    if ! command -v systemctl > /dev/null 2>&1; then
        echo -e "${RED}Error: systemctl is not available. Is systemd installed?${NC}" >&2
        exit 1
    fi
}

# Copy files to systemd directory
copy_files() {
    echo -e "${YELLOW}Copying systemd files to $SYSTEMD_DIR...${NC}"
    
    cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
    echo -e "${GREEN}✓ Copied d2iabot-scraper.service${NC}"
    
    cp "$TIMER_FILE" "$SYSTEMD_DIR/"
    echo -e "${GREEN}✓ Copied d2iabot-scraper.timer${NC}"
}

# Reload systemd daemon
reload_daemon() {
    echo -e "${YELLOW}Reloading systemd daemon...${NC}"
    systemctl daemon-reload
    echo -e "${GREEN}✓ Daemon reloaded${NC}"
}

# Enable the timer
enable_timer() {
    echo -e "${YELLOW}Enabling d2iabot-scraper.timer...${NC}"
    systemctl enable d2iabot-scraper.timer
    echo -e "${GREEN}✓ Timer enabled${NC}"
}

# Start the timer
start_timer() {
    echo -e "${YELLOW}Starting d2iabot-scraper.timer...${NC}"
    systemctl start d2iabot-scraper.timer
    echo -e "${GREEN}✓ Timer started${NC}"
}

# Print success message and status instructions
print_success() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Installation completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "The D2IA Bot Scraper systemd service and timer have been installed."
    echo ""
    echo "To check the timer status:"
    echo "  sudo systemctl status d2iabot-scraper.timer"
    echo ""
    echo "To check the service status:"
    echo "  sudo systemctl status d2iabot-scraper.service"
    echo ""
    echo "To view the timer schedule:"
    echo "  systemctl list-timers d2iabot-scraper.timer"
    echo ""
    echo "To view logs:"
    echo "  sudo journalctl -u d2iabot-scraper.service -f"
    echo ""
}

# Main installation flow
main() {
    check_root
    check_source_files
    check_systemd
    copy_files
    reload_daemon
    enable_timer
    start_timer
    print_success
}

# Run main function
main "$@"
