# -*- mode: python ; coding: utf-8 -*-
# PyInstaller specification for Metadata Updater (pywebview version)
# This spec file configures PyInstaller to bundle the pywebview application

from PyInstaller.utils.hooks import get_module_file_attribute
import os

block_cipher = None

# Analysis: define what gets bundled into the application
a = Analysis(
    ['main.py'],  # Entry point
    pathex=[],
    binaries=[],
    datas=[
        # Configuration and data files
        ('categorized_genres.json', '.'),
        ('genre_characteristics.json', '.'),
        ('hf_llm_config.json', '.'),
        ('hf_requirements.txt', '.'),
        # Model cache for LLM
        ('model_cache/', 'model_cache/'),
        # Web UI files for pywebview
        ('index.html', '.'),
        ('styles.css', '.'),
        ('app.js', '.'),
    ],
    hiddenimports=[
        # PyWebView dependencies
        'pywebview',
        'pywebview.api',
        # Audio processing
        'mutagen',
        'mutagen.mp3',
        'mutagen.mp4',
        'mutagen.id3',
        # API clients
        'requests',
        'requests.auth',
        'requests.exceptions',
        'spotipy',
        'musicbrainzngs',
        # Transformers/LLM support
        'transformers',
        'torch',
        'torch.nn',
        'torch.utils',
        # Data processing
        'numpy',
        'scipy',
        # Caching
        'requests_cache',
        # String matching
        'fuzzywuzzy',
        # Core modules
        'metadata_updater_webview',
        'api',
        'integration_helper',
        'simplified_metadata_searcher',
        'simplified_mb_integration',
        'simplified_spotify_integration',
        'artist_normalizer',
        'license_key',
        'rate_limiter',
        'unified_cache_manager',
        'resource_path',
        'dialog_handler',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude PyQt6 completely
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        # Exclude other GUI frameworks not needed
        'tkinter',
        'wxPython',
        'PySide2',
        'PySide6',
        'PyQt5',
    ],
    noarchive=False,
    optimize=2,  # Full optimization
)

# PYZ: create a Python archive
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE: create the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Metadata Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI application (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.icns'],
)

# BUNDLE: create macOS app bundle
app = BUNDLE(
    exe,
    name='Metadata Updater.app',
    icon='icon.icns',
    bundle_identifier='com.djzrex.metadata-updater',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
    },
)
