#!/bin/bash

# LCP Installation Script using pipx
# Creates an isolated environment and installs to ~/.local/bin

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# Check if pipx is installed
check_pipx() {
    print_step "Checking for pipx..."
    
    if ! command -v pipx &> /dev/null; then
        print_warning "pipx is not installed"
        echo ""
        echo "Install pipx using one of these methods:"
        echo "  - Ubuntu/Debian: apt install pipx"
        echo "  - Fedora: dnf install pipx"
        echo "  - Arch: pacman -S python-pipx"
        echo "  - MacOS: brew install pipx"
        echo "  - Any system: python3 -m pip install --user pipx"
        echo ""
        echo "After installing, run: pipx ensurepath"
        exit 1
    fi
    
    print_success "pipx found: $(pipx --version)"
}

# Install with pipx
install_lcp() {
    print_step "Installing LCP with pipx..."
    
    cd "$SCRIPT_DIR"
    
    # Uninstall if already installed
    if pipx list | grep -q "lcp"; then
        print_warning "LCP already installed, reinstalling..."
        pipx uninstall lcp
    fi
    
    # Install from local directory in editable mode for development
    # For production, you could use: pipx install .
    pipx install --editable .
    
    print_success "LCP installed successfully"
}

# Test installation
test_installation() {
    print_step "Testing installation..."
    
    if lcp --version &> /dev/null; then
        print_success "Installation test passed"
        echo ""
        version=$(lcp --version 2>&1 | grep -oP 'version \K[\d.]+' || echo "unknown")
        echo "🎉 LCP v${version} installed successfully!"
        echo ""
        echo "Usage:"
        echo "  lcp --help                 # Show help"
        echo "  lcp status                 # Check system status"
        echo "  lcp chat phi-3.5-mini     # Download and chat with model"
        echo "  lcp list                   # List local models"
        echo ""
    else
        print_error "Installation test failed"
        echo ""
        echo "Try running: lcp --help"
        echo "If it doesn't work, ensure ~/.local/bin is in your PATH"
        exit 1
    fi
}

# Ensure pipx path is configured
ensure_path() {
    print_step "Ensuring ~/.local/bin is in PATH..."
    
    pipx ensurepath
    
    # Check if we need to reload the shell
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        print_warning "You may need to restart your shell or run:"
        echo "  export PATH=\"\$PATH:\$HOME/.local/bin\""
    else
        print_success "PATH is correctly configured"
    fi
}

# Main installation process
main() {
    echo "🦙 LCP Installation with pipx"
    echo "=============================="
    echo ""
    
    check_pipx
    install_lcp
    ensure_path
    test_installation
    
    echo "🎯 Installation complete!"
    echo ""
    echo "Next steps:"
    echo "1. Ensure your llamacpp Docker container is running"
    echo "2. Run: lcp status"
    echo "3. Try: lcp chat phi-3.5-mini"
}

# Handle Ctrl+C
trap 'echo -e "\n${RED}Installation cancelled${NC}"; exit 1' INT

# Run main function
main "$@"