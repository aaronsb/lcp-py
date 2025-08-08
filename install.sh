#!/bin/bash

# LCP Installation Script
# Creates a standalone binary using PyInstaller for easy distribution

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/dist"
INSTALL_DIR="$HOME/.local/bin"

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

# Check if Python 3.9+ is available
check_python() {
    print_step "Checking Python version..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    major_version=$(echo $python_version | cut -d. -f1)
    minor_version=$(echo $python_version | cut -d. -f2)
    
    if [[ $major_version -lt 3 ]] || [[ $major_version -eq 3 && $minor_version -lt 9 ]]; then
        print_error "Python 3.9 or higher is required (found Python $python_version)"
        exit 1
    fi
    
    print_success "Python $python_version detected"
}

# Create virtual environment
create_venv() {
    print_step "Setting up virtual environment..."
    
    cd "$SCRIPT_DIR"
    
    if [[ -d "venv" ]]; then
        print_warning "Virtual environment already exists, removing..."
        rm -rf venv
    fi
    
    python3 -m venv venv
    source venv/bin/activate
    
    print_success "Virtual environment created"
}

# Install dependencies
install_deps() {
    print_step "Installing dependencies..."
    
    # Upgrade pip first
    pip install --upgrade pip
    
    # Install build dependencies
    pip install PyInstaller wheel
    
    # Install project dependencies
    pip install -e .
    
    print_success "Dependencies installed"
}

# Build binary
build_binary() {
    print_step "Building standalone binary..."
    
    # Clean previous builds
    rm -rf "$BUILD_DIR" build *.spec
    
    # Create PyInstaller spec
    cat > lcp.spec << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['lcp/cli.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'lcp.backends.huggingface',
        'lcp.ui.chat',
        'lcp.ui.progress',
        'platformdirs',
        'toml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='lcp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
EOF
    
    # Build with PyInstaller
    pyinstaller lcp.spec --clean
    
    if [[ ! -f "$BUILD_DIR/lcp" ]]; then
        print_error "Build failed - binary not found"
        exit 1
    fi
    
    print_success "Binary built successfully: $BUILD_DIR/lcp"
}

# Install binary
install_binary() {
    print_step "Installing binary to $INSTALL_DIR..."
    
    # Ensure install directory exists
    mkdir -p "$INSTALL_DIR"
    
    # Copy binary
    cp "$BUILD_DIR/lcp" "$INSTALL_DIR/lcp"
    chmod +x "$INSTALL_DIR/lcp"
    
    print_success "Binary installed to $INSTALL_DIR/lcp"
    
    # Check if install directory is in PATH
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        print_warning "Install directory $INSTALL_DIR is not in PATH"
        echo ""
        echo "Add this line to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
        echo "export PATH=\"\$PATH:$INSTALL_DIR\""
        echo ""
        echo "Or run commands with full path: $INSTALL_DIR/lcp"
    fi
}

# Test installation
test_installation() {
    print_step "Testing installation..."
    
    if "$INSTALL_DIR/lcp" --version &> /dev/null; then
        print_success "Installation test passed"
        echo ""
        echo "🎉 LCP installed successfully!"
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
        echo "Try running: $INSTALL_DIR/lcp --help"
        exit 1
    fi
}

# Clean up
cleanup() {
    print_step "Cleaning up build files..."
    
    cd "$SCRIPT_DIR"
    rm -rf venv build *.spec __pycache__ .pytest_cache
    
    # Keep dist directory for reference
    print_success "Cleanup complete (kept dist/ directory)"
}

# Main installation process
main() {
    echo "🦙 LCP Installation Script"
    echo "=========================="
    echo ""
    
    check_python
    create_venv
    install_deps
    build_binary
    install_binary
    test_installation
    
    # Ask about cleanup
    echo ""
    read -p "Clean up build files? (Y/n): " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        cleanup
    fi
    
    echo ""
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