#!/bin/bash

# Build script for Metadata Updater (pywebview version)
# Supports building for macOS, Windows, and Linux
# 
# Directory structure:
#   src/        - Python source files
#   web/        - Web UI files (HTML, CSS, JS)
#   config/     - Configuration JSON files
#   assets/     - Application icons

set -e

# Configuration
BUILD_NAME="build_pywebview.spec"
PLATFORM=$(uname -s)

echo "=========================================="
echo "Metadata Updater Build Script (pywebview)"
echo "=========================================="
echo "Platform: $PLATFORM"
echo ""

# Verify required directories exist
echo "[1/4] Verifying project structure..."
required_dirs=("src" "web" "config" "assets")
for dir in "${required_dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "Error: Required directory '$dir' not found"
        exit 1
    fi
done
echo "✓ All required directories found"
echo ""

# Clean up previous builds
echo "[2/4] Cleaning up previous builds..."
rm -rf build/
rm -rf dist/

# Check dependencies
echo "[3/4] Checking dependencies..."
if ! command -v pyinstaller &> /dev/null; then
    echo "Error: PyInstaller is not installed"
    echo "Install it with: pip install pyinstaller"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Run PyInstaller
echo "[4/4] Building application with PyInstaller..."
pyinstaller "$BUILD_NAME"

echo ""
echo "=========================================="
echo "✓ Build complete!"
echo "=========================================="
echo ""
echo "Application location:"
echo "  macOS: dist/Metadata Updater.app"
echo "  Windows: dist/Metadata Updater.exe"
echo "  Linux: dist/Metadata Updater"
echo ""
echo "To run the application:"
if [ "$PLATFORM" == "Darwin" ]; then
    echo "  open dist/Metadata\\ Updater.app"
else
    echo "  ./dist/Metadata\\ Updater"
fi
