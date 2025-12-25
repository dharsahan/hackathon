#!/bin/bash
# Smart File Organizer - Installation Script for Linux
# This script sets up the systemd user service for auto-start

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
SERVICE_NAME="smart-file-organizer"
USER_SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$USER_SERVICE_DIR/$SERVICE_NAME.service"

echo "🗂️  Smart File Organizer - Service Installation"
echo "================================================"
echo ""

# Check if venv exists
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "❌ Virtual environment not found at $VENV_DIR"
    echo "Please run the full install.sh first, or create venv manually:"
    echo "  python3 -m venv $VENV_DIR"
    echo "  $VENV_DIR/bin/pip install -r requirements.txt"
    exit 1
fi

# Create user systemd directory if it doesn't exist
mkdir -p "$USER_SERVICE_DIR"

# Generate service file dynamically with correct paths
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Smart File Organizer - Intelligent autonomous file management
Documentation=https://github.com/user/smart-file-organizer
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=$VENV_DIR/bin/python -m src.main
Restart=on-failure
RestartSec=10

# Environment
Environment=PYTHONUNBUFFERED=1

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=smart-file-organizer

[Install]
WantedBy=default.target
EOF

echo "✓ Service file generated at $SERVICE_FILE"
echo "  WorkingDirectory: $SCRIPT_DIR"
echo "  ExecStart: $VENV_DIR/bin/python -m src.main"

# Reload systemd
systemctl --user daemon-reload
echo "✓ Systemd daemon reloaded"

# Enable the service (auto-start on login)
systemctl --user enable "$SERVICE_NAME"
echo "✓ Service enabled for auto-start"

# Enable lingering (keeps service running even after logout)
loginctl enable-linger "$USER" 2>/dev/null || true
echo "✓ Linger enabled (service will run without login)"

# Start the service
systemctl --user start "$SERVICE_NAME"
echo "✓ Service started"

echo ""
echo "================================================"
echo "✅ Installation complete!"
echo ""
echo "Dashboard: http://127.0.0.1:3000"
echo ""
echo "Commands:"
echo "  Status:  systemctl --user status $SERVICE_NAME"
echo "  Logs:    journalctl --user -u $SERVICE_NAME -f"
echo "  Stop:    systemctl --user stop $SERVICE_NAME"
echo "  Start:   systemctl --user start $SERVICE_NAME"
echo "  Disable: systemctl --user disable $SERVICE_NAME"
echo ""
