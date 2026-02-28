"""
Settings manager for Metadata Updater
Handles persistence of user settings like Serato library path
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class SettingsManager:
    """Manages persistent application settings"""
    
    def __init__(self):
        """Initialize settings manager"""
        self._home_dir = Path.home()
        self._settings_file = self._home_dir / '.metadata_updater_settings'
        self._settings: Dict[str, Any] = {}
        self.load_settings()
    
    def load_settings(self) -> None:
        """Load settings from file"""
        try:
            if self._settings_file.exists():
                with open(self._settings_file, 'r') as f:
                    self._settings = json.load(f)
                print(f"✓ Settings loaded from {self._settings_file}")
            else:
                self._settings = {}
                print("No existing settings file found, starting with defaults")
        except Exception as e:
            print(f"Error loading settings: {e}")
            self._settings = {}
    
    def save_settings(self) -> None:
        """Save settings to file"""
        try:
            with open(self._settings_file, 'w') as f:
                json.dump(self._settings, f, indent=2)
            print(f"✓ Settings saved to {self._settings_file}")
        except Exception as e:
            print(f"Error saving settings: {e}")
            raise
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save to disk"""
        self._settings[key] = value
        self.save_settings()
    
    def get_serato_library_path(self) -> Optional[str]:
        """Get the cached Serato library path (primary/first library)"""
        library_paths = self.get_serato_library_paths()
        return library_paths[0] if library_paths else None

    def get_serato_library_paths(self) -> list:
        """Get all cached Serato library paths"""
        return self.get('serato_library_paths', [])

    def set_serato_library_path(self, path: Optional[str]) -> None:
        """Set and cache the Serato library path (maintains backward compatibility)"""
        if path:
            # If setting a single path, store it as the first in the list
            self.set('serato_library_paths', [path])
        else:
            # Clear the settings if None or empty string
            if 'serato_library_paths' in self._settings:
                del self._settings['serato_library_paths']
            if 'serato_library_path' in self._settings:
                del self._settings['serato_library_path']
            self.save_settings()

    def set_serato_library_paths(self, paths: list) -> None:
        """Set and cache multiple Serato library paths"""
        if paths:
            self.set('serato_library_paths', paths)
        else:
            if 'serato_library_paths' in self._settings:
                del self._settings['serato_library_paths']
            self.save_settings()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary"""
        return self._settings.copy()
