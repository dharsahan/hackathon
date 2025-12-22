#!/bin/bash
# Smart File Organizer - Installation Script for Arch Linux
# This script sets up the systemd user service for auto-start

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="smart-file-organizer"
SERVICE_FILE="$SCRIPT_DIR/smart-file-organizer.service"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

echo "🗂️  Smart File Organizer - Service Installation"
echo "================================================"
echo ""

# Create user systemd directory if it doesn't exist
mkdir -p "$USER_SERVICE_DIR"

# Copy service file
cp "$SERVICE_FILE" "$USER_SERVICE_DIR/"
echo "✓ Service file installed to $USER_SERVICE_DIR"

# Reload systemd
systemctl --user daemon-reload
echo "✓ Systemd daemon reloaded"

# Enable the service (auto-start on login)
systemctl --user enable "$SERVICE_NAME"
echo "✓ Service enabled for auto-start"

# Enable lingering (keeps service running even after logout)
loginctl enable-linger "$USER"
echo "✓ Linger enabled (service will run without login)"

# Start the service
systemctl --user start "$SERVICE_NAME"
echo "✓ Service started"

echo ""
echo "================================================"
echo "✅ Installation complete!"
echo ""
echo "Commands:"
echo "  Status:  systemctl --user status $SERVICE_NAME"
echo "  Logs:    journalctl --user -u $SERVICE_NAME -f"
echo "  Stop:    systemctl --user stop $SERVICE_NAME"
echo "  Start:   systemctl --user start $SERVICE_NAME"
echo "  Disable: systemctl --user disable $SERVICE_NAME"
echo ""
