# -*- mode: python ; coding: utf-8 -*-
# PyInstaller specification for Metadata Updater (pywebview version)
# This spec file configures PyInstaller to bundle the pywebview application

from PyInstaller.utils.hooks import get_module_file_attribute
import os

block_cipher = None

# Analysis: define what gets bundled into the application
a = Analysis(
    ['src/main.py'],  # Entry point
    pathex=['src'],
    binaries=[],
    datas=[
        # Configuration and data files
        ('config/categorized_genres.json', 'config'),
        ('config/genre_characteristics.json', 'config'),
        # License public key (required for JWT license verification)
        ('config/license_public.pem', 'config'),
        # Web UI files for pywebview
        ('web/index.html', 'web'),
        ('web/styles.css', 'web'),
        ('web/app.js', 'web'),
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
        'openai',
        # Web scraping (Riddim scraper)
        'httpx',
        'bs4',
        # Caching
        'requests_cache',
        # Core modules
        'metadata_updater_webview',
        'api',
        'integration_helper',
        'simplified_metadata_searcher',
        'simplified_mb_integration',
        'simplified_spotify_integration',
        'artist_normalizer',
        'title_normalizer',
        'license_key',
        'settings_manager',
        'rate_limiter',
        'unified_cache_manager',
        'resource_path',
        'genre_finder',
        'enhanced_genre_detector',
        'genre_patterns',
        'audio_utilities',
        'riddim_scraper',
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
        # Exclude NLTK (unused, causes numpy compatibility issue in PyInstaller)
        'nltk',
        # Exclude RAG dependencies (causes numpy compatibility issues in PyInstaller)
        # App gracefully falls back to standard genre detection if RAG unavailable
        'langchain_community',
        'chromadb',
        'langchain_huggingface',
        'sentence_transformers',
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
    icon=['assets/icon.icns'],
)

# BUNDLE: create macOS app bundle
app = BUNDLE(
    exe,
    name='Metadata Updater.app',
    icon='assets/icon.icns',
    bundle_identifier='com.djzrex.metadata-updater',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
    },
)
