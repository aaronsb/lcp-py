#!/bin/bash

# Quick development installation script
# For development and testing without building binary

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔧 LCP Development Setup"
echo "========================"
echo ""

# Create virtual environment if it doesn't exist
if [[ ! -d "$SCRIPT_DIR/venv" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install in development mode
echo "Installing dependencies..."
pip install --upgrade pip
pip install -e .

echo ""
echo "✅ Development setup complete!"
echo ""
echo "Usage:"
echo "  source venv/bin/activate    # Activate environment"
echo "  lcp --help                  # Run LCP"
echo "  python -m lcp.cli --help    # Alternative way to run"
echo ""
echo "For production installation, run: ./install.sh"