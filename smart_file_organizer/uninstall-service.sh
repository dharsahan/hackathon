#!/bin/bash
# Smart File Organizer - Uninstallation Script
# Removes the systemd user service

set -e

SERVICE_NAME="smart-file-organizer"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

echo "🗂️  Smart File Organizer - Service Removal"
echo "==========================================="
echo ""

# Stop the service if running
systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
echo "✓ Service stopped"

# Disable the service
systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
echo "✓ Service disabled"

# Remove service file
rm -f "$USER_SERVICE_DIR/$SERVICE_NAME.service"
echo "✓ Service file removed"

# Reload systemd
systemctl --user daemon-reload
echo "✓ Systemd daemon reloaded"

echo ""
echo "✅ Service removed successfully!"
echo ""
