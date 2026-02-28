# Metadata Updater - Build Instructions

This document explains how to build distributable packages of the Metadata Updater application using PyInstaller.

## Prerequisites

- **Python 3.12** or higher
- **pip** package manager
- **PyInstaller** for bundling
- Platform-specific tools:
  - **macOS**: Xcode Command Line Tools
  - **Windows**: Microsoft Visual C++ Build Tools
  - **Linux**: GCC and development headers

## Installation

### 1. Install Dependencies

First, install all required Python packages:

```bash
pip install -r requirements_webview.txt
pip install pyinstaller
```

### 2. Optional: Install Additional Build Tools

For optimal builds, install these optional tools:

```bash
# For creating signed macOS app bundles
pip install altgraph

# For code optimization
pip install pyarmor  # Optional, for code obfuscation
```

## Building

### Quick Build (Recommended)

The easiest way to build is using the provided build script:

```bash
chmod +x build.sh
./build.sh
```

This will:
1. Clean previous builds
2. Check dependencies
3. Run PyInstaller with the pywebview configuration
4. Output the application to the `dist/` directory

### Manual Build with PyInstaller

If you prefer more control, run PyInstaller directly:

```bash
# Using the pywebview specification
pyinstaller build_pywebview.spec

# Or with additional options
pyinstaller build_pywebview.spec --noconfirm --clean
```

#### PyInstaller Options
- `--noconfirm`: Don't ask for confirmation if output directory exists
- `--clean`: Remove temporary build files before building
- `--distpath`: Specify output directory for distribution files
- `--workpath`: Specify temporary work directory
- `-w` or `--windowed`: No console window (already configured in spec)

## Platform-Specific Build Instructions

### macOS

The application will be built as a native .app bundle:

```bash
./build.sh
# Output: dist/Metadata Updater.app
```

**To run:**
```bash
open "dist/Metadata Updater.app"
```

**To create a DMG installer:**
```bash
# Install dmg creation tools
pip install dmg

# Create DMG
python -m dmg create "dist/Metadata Updater.app" "dist/Metadata Updater.dmg"
```

**Signing and Notarization (optional):**
```bash
# Sign the app
codesign --deep --force --verify --verbose --sign "Developer ID Application" \
  "dist/Metadata Updater.app"

# Notarize with Apple (required for distribution)
xcrun altool --notarize-app \
  -f "dist/Metadata Updater.app" \
  -t osx \
  -u "your-apple-id@example.com" \
  -p "your-app-specific-password"
```

### Windows

The application will be built as an executable:

```bash
# In PowerShell or Command Prompt
pyinstaller build_pywebview.spec

# Output: dist/Metadata Updater.exe
```

**To run:**
```
dist\Metadata Updater.exe
```

**Creating an installer (optional):**
```bash
# Install NSIS (Nullsoft Scriptable Install System)
pip install pyinstaller-nsis

# Then create the installer
pyinstaller build_pywebview.spec --onefile
```

### Linux

The application will be built as an executable:

```bash
chmod +x build.sh
./build.sh
# Output: dist/Metadata Updater
```

**To run:**
```bash
./dist/Metadata\ Updater
```

**Creating a .deb package (Debian/Ubuntu):**
```bash
# Create necessary directories
mkdir -p deb_package/DEBIAN
mkdir -p deb_package/usr/bin
mkdir -p deb_package/usr/share/applications

# Copy executable
cp dist/Metadata\ Updater deb_package/usr/bin/

# Create control file
cat > deb_package/DEBIAN/control << EOF
Package: metadata-updater
Version: 1.7.0
Section: audio
Priority: optional
Architecture: amd64
Maintainer: Your Name <your-email@example.com>
Description: Update audio file metadata automatically
EOF

# Create .deb package
dpkg -b deb_package/ metadata-updater_1.7.0_amd64.deb
```

## Configuration and Customization

### Modifying the Build

Edit `build_pywebview.spec` to customize the build:

- **Change application name**: Modify the `name='Metadata Updater'` line
- **Add files**: Add to the `datas` list
- **Exclude modules**: Add to the `excludes` list
- **Change icon**: Update the `icon` parameter
- **Optimize further**: Change `optimize=2` to `optimize=0` for debugging

### Icon Files

The build uses `icon.icns` for the application icon. To use a different icon:

1. Prepare icon files:
   - **macOS**: `icon.icns` (1024x1024 recommended)
   - **Windows**: `icon.ico` (256x256 recommended)
   - **Linux**: `icon.png` (512x512 recommended)

2. Update the spec file:
```python
icon=['icon.icns'],  # For macOS
# or
icon=['icon.ico'],  # For Windows
```

## Troubleshooting

### Build Fails with "Module not found"

If PyInstaller can't find a module, add it to `hiddenimports` in the spec file:

```python
hiddenimports=[
    'missing_module_name',
    # ... other imports
]
```

### Application Won't Start

Check the debug output:

```bash
# On macOS
open "dist/Metadata Updater.app" --stderr
```

Enable debug mode in the spec file:
```python
exe = EXE(
    ...
    debug=True,  # Enable debugging
    ...
)
```

### Large File Size

The application is large (200-400 MB) because it includes:
- Python runtime
- PyWebView
- PyTorch/Transformers for ML
- All dependencies

To reduce size:
1. Set `optimize=2` in spec (already configured)
2. Remove unused dependencies
3. Use UPX compression (configure in spec)

### Performance Issues

- Ensure you're using the optimized build (`optimize=2`)
- Run native builds for your platform (don't use cross-compilation)
- Check system resources during first run (LLM model loading is CPU intensive)

## Distribution

### Preparing for Release

1. **Test the build thoroughly**:
   ```bash
   # Run the executable
   ./dist/Metadata\ Updater
   # Test all features
   ```

2. **Create release artifacts**:
   - macOS: Create DMG installer
   - Windows: Create MSI installer (using WiX or NSIS)
   - Linux: Create .deb and/or .tar.gz packages

3. **Sign and notarize** (required for public distribution):
   - macOS: Apple Developer certification required
   - Windows: Sectigo/DigiCert code signing certificate

4. **Create release notes** and changelog

### Uploading to Repositories

- **macOS**: Upload to App Store or GitHub Releases
- **Windows**: Upload to Windows Store or GitHub Releases
- **Linux**: Upload to Flathub, Snap Store, or GitHub Releases

## Development Builds

For development, run directly without building:

```bash
python3 main.py
```

This allows for hot reloading and easier debugging.

## Additional Resources

- [PyInstaller Documentation](https://pyinstaller.org/)
- [pywebview Documentation](https://pywebview.kivy.org/)
- [Python Packaging Guide](https://packaging.python.org/)

## Support

For issues or questions:
1. Check the [project documentation](./MIGRATION_GUIDE.md)
2. Review [troubleshooting guide](#troubleshooting)
3. Report issues on GitHub

---

**Last Updated**: October 30, 2025
**Version**: 1.7.0 (pywebview)
