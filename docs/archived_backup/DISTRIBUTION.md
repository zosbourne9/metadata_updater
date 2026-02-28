# Metadata Updater - Distribution Guide

This document provides step-by-step instructions for creating and distributing releases of the Metadata Updater application across macOS, Windows, and Linux platforms.

## Release Preparation

### Prerequisites

- All code changes committed to git
- Version number updated in `main.py`
- BUILD_INSTRUCTIONS.md reviewed and updated
- All tests passing
- No uncommitted changes

### Version Management

Update the version number in `main.py`:

```python
init_result = {
    'success': True,
    'message': 'Application initialized',
    'version': '1.8.0'  # Update this
}
```

Then create a git tag:

```bash
git tag -a v1.8.0 -m "Release version 1.8.0"
git push origin v1.8.0
```

## Platform-Specific Distribution

### macOS Distribution

#### Prerequisites
- Apple Developer account (optional, for code signing)
- Xcode Command Line Tools
- `codesign` utility
- macOS 10.13+

#### Build Steps

1. **Build the app bundle**:
   ```bash
   ./build.sh
   ```
   Output: `dist/Metadata Updater.app`

2. **Code signing (optional but recommended)**:
   ```bash
   # If you have a Developer ID Application certificate
   codesign --force --deep --sign "Developer ID Application: Your Name (TEAM_ID)" \
     "dist/Metadata Updater.app"
   
   # Verify the signature
   codesign -v --deep --strict "dist/Metadata Updater.app"
   ```

3. **Create DMG installer**:
   ```bash
   # Install dmgbuild if needed
   pip install dmgbuild
   
   # Create the DMG
   dmgbuild -s dmg_settings.py "Metadata Updater" "dist/Metadata Updater.dmg"
   ```

4. **Notarization (required for distribution on App Store or public websites)**:
   ```bash
   # Upload for notarization
   xcrun altool --notarize-app \
     -f "dist/Metadata Updater.dmg" \
     -t osx \
     -u "your-apple-id@example.com" \
     -p "@keychain:altool-password"
   
   # Check notarization status (takes 5-30 minutes)
   xcrun altool --notarization-info <REQUEST_UUID> \
     -u "your-apple-id@example.com" \
     -p "@keychain:altool-password"
   
   # Once approved, staple the notarization ticket
   xcrun stapler staple "dist/Metadata Updater.dmg"
   ```

#### Distribution Channels

- **Direct download**: Upload DMG to GitHub Releases
- **Mac App Store**: Submit via App Store Connect (requires ~$100 developer account)
- **Homebrew**: Create a Homebrew cask
- **MacPorts**: Contribute formula to MacPorts

### Windows Distribution

#### Prerequisites
- Windows 10 or 11
- NSIS (Nullsoft Scriptable Install System) or WiX Toolset
- Visual C++ redistributables

#### Build Steps

1. **Build the executable**:
   ```bash
   pyinstaller build_pywebview.spec --onefile
   ```
   Output: `dist/Metadata Updater.exe`

2. **Create installer using NSIS**:
   ```bash
   # Install NSIS
   pip install pyinstaller-nsis
   
   # Create installer configuration
   ```

   Create `installer.nsi`:
   ```nsis
   ; Metadata Updater Installer
   !include "MUI2.nsh"
   
   Name "Metadata Updater 1.8.0"
   OutFile "dist/Metadata Updater Installer.exe"
   InstallDir "$PROGRAMFILES\Metadata Updater"
   
   !insertmacro MUI_PAGE_WELCOME
   !insertmacro MUI_PAGE_DIRECTORY
   !insertmacro MUI_PAGE_INSTFILES
   !insertmacro MUI_PAGE_FINISH
   !insertmacro MUI_LANGUAGE "English"
   
   Section "Install"
     SetOutPath "$INSTDIR"
     File "dist\Metadata Updater.exe"
     CreateDirectory "$SMPROGRAMS\Metadata Updater"
     CreateShortCut "$SMPROGRAMS\Metadata Updater\Metadata Updater.lnk" "$INSTDIR\Metadata Updater.exe"
     CreateShortCut "$DESKTOP\Metadata Updater.lnk" "$INSTDIR\Metadata Updater.exe"
   SectionEnd
   
   Section "Uninstall"
     Delete "$INSTDIR\Metadata Updater.exe"
     Delete "$SMPROGRAMS\Metadata Updater\Metadata Updater.lnk"
     Delete "$DESKTOP\Metadata Updater.lnk"
   SectionEnd
   ```

   Then build:
   ```bash
   makensis installer.nsi
   ```

3. **Sign the executable (optional)**:
   ```bash
   signtool sign /f certificate.pfx /p password /t http://timestamp.server \
     "dist\Metadata Updater.exe"
   ```

#### Distribution Channels

- **Direct download**: Upload to GitHub Releases
- **Windows Store**: Submit via Partner Center (requires verification)
- **Chocolatey**: Create package and submit to community repository
- **WinGet**: Contribute manifest to winget-pkgs repository
- **SourceForge**: Upload for distribution

### Linux Distribution

#### Prerequisites
- Ubuntu/Debian development tools
- RPM build tools (for RedHat-based distributions)
- AppImage builder (optional)

#### Build Steps

1. **Build the executable**:
   ```bash
   ./build.sh
   ```
   Output: `dist/Metadata Updater`

2. **Create Debian package**:
   ```bash
   # Create directory structure
   mkdir -p deb_package/DEBIAN
   mkdir -p deb_package/usr/bin
   mkdir -p deb_package/usr/share/applications
   mkdir -p deb_package/usr/share/icons/hicolor/256x256/apps
   
   # Copy files
   cp dist/Metadata\ Updater deb_package/usr/bin/metadata-updater
   chmod +x deb_package/usr/bin/metadata-updater
   
   # Create desktop entry
   cat > deb_package/usr/share/applications/metadata-updater.desktop << EOF
   [Desktop Entry]
   Type=Application
   Name=Metadata Updater
   Exec=metadata-updater
   Icon=metadata-updater
   Categories=Audio;Utility;
   Version=1.8.0
   EOF
   
   # Create control file
   cat > deb_package/DEBIAN/control << EOF
   Package: metadata-updater
   Version: 1.8.0
   Section: audio
   Priority: optional
   Architecture: amd64
   Maintainer: Your Name <your-email@example.com>
   Description: Update audio file metadata automatically
    Metadata Updater automatically updates metadata for audio files
    including artist, album, genre, and year information.
   EOF
   
   # Build package
   dpkg-deb --build deb_package dist/metadata-updater_1.8.0_amd64.deb
   ```

3. **Create AppImage**:
   ```bash
   # Install AppImage builder
   pip install appimage-builder
   
   # Create appimage.yml configuration
   # Then build
   appimage-builder --recipe appimage.yml
   ```

   Example `appimage.yml`:
   ```yaml
   version: 1
   
   AppDir:
     path: ./AppDir
     app_info:
       id: com.djzrex.metadata-updater
       name: Metadata Updater
       icon: icon
       version: 1.8.0
       exec: usr/bin/Metadata Updater
     
     files:
       dist/Metadata\ Updater: usr/bin/
       icon.png: icon.png
   
   AppImage:
     file_name: Metadata Updater-1.8.0-x86_64.AppImage
     update-info: gh-releases-zsync|user|repo|latest|*x86_64.AppImage.zsync
   ```

#### Distribution Channels

- **Direct download**: Upload to GitHub Releases
- **Flathub**: Create and submit Flatpak manifest
- **Snap Store**: Create and publish snap package
- **AUR**: Contribute PKGBUILD for Arch Linux
- **Ubuntu PPA**: Host on Launchpad PPA
- **AppImage**: Distribute via GitHub Releases

## Release Checklist

### Pre-Release

- [ ] All code changes committed
- [ ] Version number updated
- [ ] README.md updated with latest features
- [ ] CHANGELOG.md updated
- [ ] All tests passing
- [ ] Documentation reviewed and updated
- [ ] Build instructions tested on target platforms
- [ ] Performance tested and optimized

### Build and Package

- [ ] macOS app bundle created
- [ ] macOS DMG created
- [ ] macOS app signed and notarized
- [ ] Windows executable created
- [ ] Windows installer created
- [ ] Windows executable signed
- [ ] Linux executables created
- [ ] Linux .deb package created
- [ ] Linux AppImage created

### Testing

- [ ] Application starts without errors
- [ ] File upload works correctly
- [ ] Metadata searching functions
- [ ] File processing completes successfully
- [ ] License validation works
- [ ] All settings save and load correctly
- [ ] On macOS: App launches from Finder
- [ ] On Windows: Installer works and app launches
- [ ] On Linux: Runs from terminal and desktop shortcuts work

### Release

- [ ] Create git tag
- [ ] Push tag to repository
- [ ] Create GitHub Release with all artifacts
- [ ] Upload to platform-specific distribution channels
- [ ] Update project website with download links
- [ ] Create release announcement
- [ ] Post to social media / forums

### Post-Release

- [ ] Monitor bug reports
- [ ] Track download statistics
- [ ] Plan next release

## Automated CI/CD

### GitHub Actions Workflow

Create `.github/workflows/release.yml`:

```yaml
name: Release Build

on:
  push:
    tags:
      - 'v*'

jobs:
  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements_webview.txt PyInstaller
      - run: ./build.sh
      - uses: actions/upload-artifact@v3
        with:
          name: macos-app
          path: dist/

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements_webview.txt PyInstaller
      - run: python -m PyInstaller build_pywebview.spec
      - uses: actions/upload-artifact@v3
        with:
          name: windows-exe
          path: dist/

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements_webview.txt PyInstaller
      - run: ./build.sh
      - uses: actions/upload-artifact@v3
        with:
          name: linux-app
          path: dist/
```

## Security Considerations

### Code Signing

- Always sign executables before distribution
- Use reputable certificate authorities
- Maintain private key security

### Dependencies

- Regularly update dependencies
- Monitor security advisories
- Include security patches in releases

### Distribution

- Use HTTPS for downloads
- Provide checksums (SHA256) for verification
- Consider code obfuscation for proprietary logic

## Version Numbering

Use Semantic Versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Incompatible API changes
- **MINOR**: New features in backward-compatible manner
- **PATCH**: Backward-compatible bug fixes

Example: `1.8.0` → `1.8.1` (patch) → `1.9.0` (minor) → `2.0.0` (major)

## Rollback Procedure

If a release has critical issues:

1. Document the issue
2. Create a hotfix branch from previous stable tag
3. Apply minimal fixes
4. Build and release as patch version
5. Communicate issue and fix to users
6. Update documentation

---

**Last Updated**: October 30, 2025
**Current Version**: 1.7.0 (pywebview)
