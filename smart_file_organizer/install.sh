#!/bin/bash
# ============================================================================
# Smart File Organizer - Complete Installation Script
# ============================================================================
# This script installs all dependencies and sets up the systemd service
# Supports: Arch Linux, Ubuntu/Debian, Fedora
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

print_banner() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║        🗂️  Smart File Organizer - Installation Script         ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Detect OS
detect_os() {
    if [ -f /etc/arch-release ]; then
        OS="arch"
    elif [ -f /etc/debian_version ]; then
        OS="debian"
    elif [ -f /etc/fedora-release ]; then
        OS="fedora"
    else
        OS="unknown"
    fi
    echo "$OS"
}

# Install system dependencies
install_system_deps() {
    local os=$(detect_os)
    echo ""
    echo -e "${BLUE}Installing system dependencies...${NC}"
    
    case $os in
        arch)
            print_step "Detected Arch Linux"
            sudo pacman -S --noconfirm --needed python python-pip tesseract tesseract-data-eng 2>/dev/null || {
                print_warning "Some packages may already be installed"
            }
            ;;
        debian)
            print_step "Detected Ubuntu/Debian"
            sudo apt update -qq
            sudo apt install -y python3 python3-pip python3-venv tesseract-ocr 2>/dev/null
            ;;
        fedora)
            print_step "Detected Fedora"
            sudo dnf install -y python3 python3-pip tesseract 2>/dev/null
            ;;
        *)
            print_warning "Unknown OS - please install Python 3.9+ and Tesseract manually"
            ;;
    esac
    
    print_step "System dependencies installed"
}

# Create virtual environment
create_venv() {
    echo ""
    echo -e "${BLUE}Setting up Python virtual environment...${NC}"
    
    if [ -d "$VENV_DIR" ]; then
        print_warning "Virtual environment already exists, skipping creation"
    else
        python3 -m venv "$VENV_DIR"
        print_step "Virtual environment created"
    fi
    
    # Activate and upgrade pip
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip -q
    print_step "Pip upgraded"
}

# Install Python dependencies
install_python_deps() {
    echo ""
    echo -e "${BLUE}Installing Python dependencies...${NC}"
    
    source "$VENV_DIR/bin/activate"
    pip install -r "$SCRIPT_DIR/requirements.txt" -q
    print_step "Python dependencies installed"
}

# Setup systemd service
setup_service() {
    echo ""
    echo -e "${BLUE}Setting up systemd service...${NC}"
    
    local SERVICE_DIR="$HOME/.config/systemd/user"
    local SERVICE_FILE="$SERVICE_DIR/smart-file-organizer.service"
    
    # Create service directory
    mkdir -p "$SERVICE_DIR"
    
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
    
    print_step "Service file generated with correct paths"
    
    # Reload systemd
    systemctl --user daemon-reload
    print_step "Systemd daemon reloaded"
    
    # Enable service
    systemctl --user enable smart-file-organizer
    print_step "Service enabled for auto-start"
    
    # Enable lingering
    loginctl enable-linger "$USER" 2>/dev/null || true
    print_step "Linger enabled (runs without login)"
}

# Start service
start_service() {
    echo ""
    echo -e "${BLUE}Starting service...${NC}"
    
    systemctl --user start smart-file-organizer
    sleep 2
    
    if systemctl --user is-active --quiet smart-file-organizer; then
        print_step "Service started successfully"
    else
        print_error "Service failed to start"
        echo "Check logs: journalctl --user -u smart-file-organizer -f"
        exit 1
    fi
}

# Create default directories
create_directories() {
    echo ""
    echo -e "${BLUE}Creating directories...${NC}"
    
    mkdir -p ~/Downloads
    mkdir -p ~/Desktop
    mkdir -p ~/Organized/.quarantine
    mkdir -p ~/Organized/Vault
    
    print_step "Directories created"
}

# Verify installation
verify_installation() {
    echo ""
    echo -e "${BLUE}Verifying installation...${NC}"
    
    # Check Python
    if command -v python3 &> /dev/null; then
        local py_version=$(python3 --version)
        print_step "Python: $py_version"
    else
        print_error "Python not found"
        exit 1
    fi
    
    # Check Tesseract
    if command -v tesseract &> /dev/null; then
        local tess_version=$(tesseract --version 2>&1 | head -1)
        print_step "Tesseract: $tess_version"
    else
        print_warning "Tesseract not found (OCR will be disabled)"
    fi
    
    # Check venv
    if [ -f "$VENV_DIR/bin/python" ]; then
        print_step "Virtual environment: OK"
    else
        print_error "Virtual environment not found"
        exit 1
    fi
    
    # Check service
    if systemctl --user is-active --quiet smart-file-organizer; then
        print_step "Service: Running"
    else
        print_warning "Service: Not running"
    fi
}

# Print usage info
print_usage() {
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}                    Installation Complete! 🎉                    ${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "The Smart File Organizer is now running as a background service."
    echo -e "It will automatically start on boot."
    echo ""
    echo -e "${BLUE}Watching:${NC}"
    echo -e "  • ~/Downloads"
    echo -e "  • ~/Desktop"
    echo ""
    echo -e "${BLUE}Commands:${NC}"
    echo -e "  Status:   ${YELLOW}systemctl --user status smart-file-organizer${NC}"
    echo -e "  Logs:     ${YELLOW}journalctl --user -u smart-file-organizer -f${NC}"
    echo -e "  Stop:     ${YELLOW}systemctl --user stop smart-file-organizer${NC}"
    echo -e "  Restart:  ${YELLOW}systemctl --user restart smart-file-organizer${NC}"
    echo ""
    echo -e "${BLUE}CLI Tools:${NC}"
    echo -e "  History:  ${YELLOW}$VENV_DIR/bin/python -m src.main --history${NC}"
    echo -e "  Undo:     ${YELLOW}$VENV_DIR/bin/python -m src.main --undo${NC}"
    echo -e "  Rules:    ${YELLOW}$VENV_DIR/bin/python -m src.main --rules${NC}"
    echo -e "  Stats:    ${YELLOW}$VENV_DIR/bin/python -m src.main --stats${NC}"
    echo ""
    echo -e "${BLUE}Configuration:${NC} $SCRIPT_DIR/config.yaml"
    echo ""
}

# Main installation
main() {
    print_banner
    
    echo "This script will:"
    echo "  1. Install system dependencies (Python, Tesseract)"
    echo "  2. Create Python virtual environment"
    echo "  3. Install Python packages"
    echo "  4. Setup systemd service (auto-start on boot)"
    echo "  5. Start the organizer daemon"
    echo ""
    
    read -p "Continue with installation? [Y/n] " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    
    install_system_deps
    create_venv
    install_python_deps
    create_directories
    setup_service
    start_service
    verify_installation
    print_usage
}

# Run main function
main "$@"
