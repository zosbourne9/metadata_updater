# PyQt6 to pywebview Migration - Complete Analysis

This document provides a detailed analysis of all PyQt6 imports and usages that need to be replaced with pywebview equivalents.

---

## Overview of Changes Required

The migration involves removing PyQt6 dependencies from 9 files and replacing signal/slot patterns with callback-based communication. Files like `simplified_metadata_searcher.py` and `simplified_spotify_integration.py` don't directly import PyQt6 but receive callbacks from files that do.

---

## File-by-File Analysis

### 1. **simplified_spotify_integration.py**

**Current PyQt6 Usage:**
- Lines 5, 8, 11: `from PyQt6.QtCore import QObject, pyqtSignal`
- `SimplifiedSpotifyStatusEmitter` class (lines 7-11): Emits `status_updated` signal

**How Signals are Used:**
- `status_emitter.status_updated.connect(status_update_callback)` in `__init__` (line 33)
- `status_emitter.emit_status(message)` called in `emit_status()` (line 43)

**Dependencies:**
- `LLMStatusEmitter` pattern used in other files depends on this pattern

**Migration Strategy:**
1. Remove lines 5, 8: Remove PyQt6 imports
2. Remove lines 7-11: Remove `SimplifiedSpotifyStatusEmitter` class
3. Replace signal in `__init__`:
   ```python
   # OLD:
   self.status_emitter = SimplifiedSpotifyStatusEmitter()
   if status_update_callback:
       self.status_emitter.status_updated.connect(status_update_callback)
   
   # NEW:
   self.status_update_callback = status_update_callback
   ```
4. Replace `emit_status()` method (lines 40-45):
   ```python
   def emit_status(self, message):
       """Emit status update through callback."""
       if self.status_update_callback:
           self.status_update_callback(message)
       else:
           print(message)
   ```

**Files That Depend on This:**
- `simplified_metadata_searcher.py` passes `status_update_callback` to this class

---

### 2. **simplified_metadata_searcher.py**

**Current PyQt6 Usage:**
- No direct imports - receives callback parameter

**Migration Impact:**
- No changes needed to this file
- It's already callback-ready (parameter `status_update_callback=None` at line 16)

---

### 3. **license_key.py**

**Current PyQt6 Usage:**
- Line 4: `from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget, QLineEdit, QVBoxLayout, QDialog`
- Lines 158-372: Full UI implementation using PyQt6 widgets

**How Signals are Used:**
- `activate_btn.clicked.connect(self.activate_license)` (line 219)
- `cancel_btn.clicked.connect(self.close)` (line 235)
- `self.license_btn.clicked.connect(self.show_license_dialog)` - connected from `ui_elements.py`

**Dependencies:**
- Imports in `ui_elements.py` line 11: `from license_key import LicenseBanner, LicenseDialog`
- Both `LicenseDialog` and `LicenseBanner` are QDialog/QFrame subclasses

**Migration Strategy:**

This file contains **two UI classes that must be migrated**:

#### A. `LicenseDialog` (lines 158-261)
- Currently a QDialog with license key entry form
- Replace with HTML/JavaScript dialog
- Strategy: Convert to webview-based modal dialog or use backend endpoints

**Migration Steps:**
1. Create HTML template for license dialog (can be embedded or served)
2. Replace `QDialog` inheritance with simple class
3. Replace all `QPushButton`, `QLineEdit`, `QLabel`, `QVBoxLayout` with HTML
4. Replace button click handlers with JavaScript event listeners
5. Use JavaScript to call backend Python functions via pywebview API

**New Structure:**
```python
class LicenseDialog:
    def __init__(self, parent, license_manager):
        self.license_manager = license_manager
        self.result_callback = None
    
    def show(self, callback=None):
        """Show license dialog and call callback when done."""
        self.result_callback = callback
        # Use API to show dialog or navigate to license page
```

#### B. `LicenseBanner` (lines 263-372)
- Currently a QFrame showing license status
- Replace with HTML element in the UI
- Status can be updated via JavaScript/HTML

**New Structure:**
```python
class LicenseBanner:
    def __init__(self, license_manager):
        self.license_manager = license_manager
        # No UI widget here - HTML element in main page instead
    
    def get_html(self):
        """Return HTML for license banner."""
        is_licensed = self.license_manager.is_licensed()
        return f"<div class='license-banner'>{'Licensed' if is_licensed else 'Free'}</div>"
```

**Remove:**
- Line 4: Remove entire PyQt6 import
- Lines 158-372: Remove both classes (they'll be reimplemented as HTML/JavaScript)

---

### 4. **dialog_handler.py**

**Current PyQt6 Usage:**
- Line 1: `from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, Qt, QThread, QEventLoop`
- Line 2: `from PyQt6.QtWidgets import QMessageBox, QApplication`
- Lines 9-10: Signal definitions
- Lines 27-30: Signal connections in `__init__`
- Lines 44-50: `@pyqtSlot` decorator and signal emission

**How Signals/Slots are Used:**
- Thread-safe dialog handling using signals
- `features_dialog_requested.emit()` to request dialog on main thread (line 40)
- `@pyqtSlot` methods to handle signals on main thread
- `QEventLoop.exec()` to wait for dialog result (line 41)

**Dependencies:**
- Used by `spotify_integration.py` line 30: `DialogHandler.instance(parent)`
- Used by `mb_integration.py` line 46: `DialogHandler.instance(parent)`
- Called with `dialog_handler.show_features_dialog()` in multiple places

**Migration Strategy:**

This is **critical** - it handles thread-safe dialogs. Replace with callback-based approach:

1. Remove all PyQt6 imports (lines 1-2)
2. Remove signal definitions (lines 8-10)
3. Remove signal connections (lines 27-30)
4. Replace singleton pattern with function-based approach:

**New Implementation:**
```python
class DialogHandler:
    """Handles dialogs in a thread-safe manner using callbacks."""
    
    _instance = None
    _dialog_callback = None  # Callback to show dialog from main context
    
    @classmethod
    def instance(cls, parent=None, dialog_callback=None):
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls(parent)
        if dialog_callback:
            cls._dialog_callback = dialog_callback
        return cls._instance
    
    def __init__(self, parent=None):
        self._parent = parent
        self._dialog_result = False
    
    def show_features_dialog(self, featuring_artists, main_artist):
        """Show features dialog using callback mechanism."""
        if self._dialog_callback:
            # Call the callback with dialog info
            return self._dialog_callback('features', {
                'featuring_artists': featuring_artists,
                'main_artist': main_artist
            })
        else:
            # Fallback: print to console
            print(f"Features dialog needed: {featuring_artists} for {main_artist}")
            return False
    
    def show_error(self, message, title="Error"):
        """Show error dialog via callback."""
        if self._dialog_callback:
            return self._dialog_callback('error', {
                'message': message,
                'title': title
            })
        else:
            print(f"{title}: {message}")
    
    def show_warning(self, message, title="Warning"):
        """Show warning dialog via callback."""
        if self._dialog_callback:
            return self._dialog_callback('warning', {
                'message': message,
                'title': title
            })
        else:
            print(f"{title}: {message}")
```

**Changes Needed:**
- Remove lines 1-2: PyQt6 imports
- Remove lines 8-10: Signal definitions
- Remove lines 27-30: Signal connections
- Remove lines 44-50: @pyqtSlot decorators
- Replace all `QMessageBox` calls with callback mechanism
- Remove `QThread` and `QEventLoop` logic

---

### 5. **llm_utils.py**

**Current PyQt6 Usage:**
- Line 7: `from PyQt6.QtCore import QObject, pyqtSignal`
- Line 8: `from PyQt6.QtWidgets import QMessageBox`
- Lines 11-15: `LLMStatusEmitter` class
- Line 32: Creating status emitter
- Line 51: `QMessageBox.critical()` call (line 51)

**How Signals are Used:**
- `status_emitter.status_updated.connect(update_status_callback)` (line 32)
- `self.status_emitter.emit_status(message)` calls (lines 44, 63-72)

**Dependencies:**
- Status updates shown in UI
- Error dialogs for model loading failures

**Migration Strategy:**

1. Remove lines 7-8: PyQt6 imports
2. Remove lines 11-15: Remove `LLMStatusEmitter` class
3. Replace in `__init__`:
   ```python
   self.status_update_callback = update_status_callback
   ```
4. Replace `emit_status()` method (lines 41-46):
   ```python
   def emit_status(self, message):
       """Emit status update through callback."""
       if self.status_update_callback:
           self.status_update_callback(message)
       else:
           print(message)
   ```
5. Replace `show_error_dialog()` (lines 48-53):
   ```python
   def show_error_dialog(self, message, title="Error"):
       """Show error dialog via callback."""
       if self.status_update_callback:
           self.status_update_callback(f"{title}: {message}")
       else:
           print(f"Error: {message}")
   ```

---

### 6. **hf_llm_utils.py**

**Current PyQt6 Usage:**
- Line 6: `from PyQt6.QtCore import QObject, pyqtSignal`
- Line 7: `from PyQt6.QtWidgets import QMessageBox`
- Lines 10-14: `HFLLMStatusEmitter` class
- Line 42-44: Creating status emitter
- Line 69: `QMessageBox.critical()` call

**How Signals are Used:**
- Similar to `llm_utils.py`
- Status signals for model loading
- Error dialogs

**Migration Strategy:**

Identical to `llm_utils.py`:

1. Remove lines 6-7: PyQt6 imports
2. Remove lines 10-14: Remove `HFLLMStatusEmitter` class
3. Update `__init__` to store callback (line 44)
4. Update `emit_status()` method (lines 59-64)
5. Update `show_error_dialog()` method (lines 66-71)

**New Implementation:**
```python
def __init__(self, parent=None, update_status_callback=None):
    # ... existing code ...
    self.status_update_callback = update_status_callback

def emit_status(self, message):
    """Emit status update through callback."""
    if self.status_update_callback:
        self.status_update_callback(message)
    else:
        print(message)

def show_error_dialog(self, message, title="Error"):
    """Show error dialog via callback."""
    if self.status_update_callback:
        self.status_update_callback(f"{title}: {message}")
    else:
        print(f"Error: {message}")
```

---

### 7. **spotify_integration.py**

**Current PyQt6 Usage:**
- Line 10: `from PyQt6.QtWidgets import QMessageBox`
- Line 11: `from PyQt6.QtCore import QObject, pyqtSignal`
- Lines 16-20: `SpotifyStatusEmitter` class
- Lines 32-35: Creating status emitter
- Line 142: `QMessageBox.critical()` call

**How Signals are Used:**
- Status updates for Spotify operations
- Error dialogs for API issues

**Dependencies:**
- Used by `spotify_integration.py` (itself)
- Called from main metadata updater

**Migration Strategy:**

1. Remove lines 10-11: PyQt6 imports
2. Remove lines 16-20: Remove `SpotifyStatusEmitter` class
3. Replace in `__init__` (lines 32-35):
   ```python
   self.status_update_callback = status_update_callback
   ```
4. Replace `emit_status()` (lines 132-137):
   ```python
   def emit_status(self, message):
       """Emit status update through callback."""
       if self.status_update_callback:
           self.status_update_callback(message)
       else:
           print(message)
   ```
5. Replace `show_error_dialog()` (lines 139-144):
   ```python
   def show_error_dialog(self, message, title="Error"):
       """Show error dialog via callback."""
       if self.status_update_callback:
           self.status_update_callback(f"{title}: {message}")
       else:
           print(f"Error: {message}")
   ```

---

### 8. **mb_integration.py**

**Current PyQt6 Usage:**
- Line 7: `from PyQt6.QtWidgets import QMessageBox`
- Line 8: `from PyQt6.QtCore import QObject, pyqtSignal`
- Lines 33-37: `MusicBrainzStatusEmitter` class
- Lines 49-51: Creating status emitter
- Line 99: `QMessageBox.critical()` call

**How Signals are Used:**
- Status updates for MusicBrainz queries
- Error dialogs

**Dependencies:**
- Used by metadata updater
- Calls `DialogHandler` for feature dialogs

**Migration Strategy:**

Identical to spotify and llm files:

1. Remove lines 7-8: PyQt6 imports
2. Remove lines 33-37: Remove `MusicBrainzStatusEmitter` class
3. Update `__init__` to use callback (line 51)
4. Replace `emit_status()` method (lines 89-94)
5. Replace `show_error_dialog()` method (lines 96-101)

---

### 9. **ui_elements.py**

**Current PyQt6 Usage:**
- Lines 3-10: Major PyQt6 imports for all widget classes
- Line 11: Import from `license_key` (needs replacement)
- Line 9: `from PyQt6.QtCore import Qt, pyqtSignal`
- Lines 13-51, 52-644: Full UI implementation using PyQt6 widgets

**How Signals are Used:**
- Button click signals (lines 219, 235, 365, 527-537)
- Qt widget hierarchy and layout system
- Drag-and-drop events (lines 78-102)
- Custom signals (would be needed for pywebview)

**Dependencies:**
- Main UI file - everything depends on this
- Imports `LicenseBanner` and `LicenseDialog` from `license_key.py`

**Migration Strategy:**

This is the **most complex file** - it's the entire UI. Complete rewrite needed:

1. **Remove all PyQt6 imports (lines 3-10)**
2. **Remove PyQt6 from license_key import (line 11)** - will use callback-based version
3. **Replace entire UI implementation with pywebview API**

**New Structure:**

```python
# ui_elements.py - Minimal class, HTML-driven
import os

class UIElements:
    """Coordinator for UI elements - no Qt dependencies."""
    
    def __init__(self, metadata_updater, version=None, license_manager=None):
        self.metadata_updater = metadata_updater
        self.version = version
        self.license_manager = license_manager
        self.selected_files = []
        self.artist_warning_shown = False
    
    def get_html(self):
        """Return the complete HTML UI."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Audio Metadata Manager</title>
            <link rel="stylesheet" href="styles.css">
        </head>
        <body>
            <div class="container">
                <!-- License Banner -->
                <div class="license-banner" id="licenseBanner">
                    <!-- Updated by Python code -->
                </div>
                
                <!-- Header -->
                <div class="header">
                    <h1>Audio Metadata Manager</h1>
                    <p class="version">v{{ version }}</p>
                </div>
                
                <!-- Drop Zone -->
                <div class="drop-zone" id="dropZone">
                    <p>🎵 Drop your audio files here</p>
                    <p>or use the selection below</p>
                </div>
                
                <!-- File Selection -->
                <div class="file-selection">
                    <select id="modeSelect">
                        <option>📁 File(s)</option>
                        <option>📂 Folder</option>
                    </select>
                    <button id="selectFilesBtn">✨ Select Files</button>
                </div>
                
                <!-- Metadata Fields -->
                <div class="metadata-section">
                    <h3>🎛️ Select Metadata Fields</h3>
                    <div class="toggles-grid">
                        <button class="toggle" data-field="all">✅ All</button>
                        <button class="toggle" data-field="artist">🎤 Artist</button>
                        <button class="toggle" data-field="album">💿 Album</button>
                        <button class="toggle" data-field="genre">🎵 Genre</button>
                        <button class="toggle" data-field="year">📅 Year</button>
                        <button class="toggle" data-field="comments">🏷️ Subgenres</button>
                    </div>
                </div>
                
                <!-- Status Section -->
                <div class="status-section">
                    <div class="progress-bar-container">
                        <div class="progress-bar" id="progressBar"></div>
                    </div>
                    <p id="currentFileLabel">🎵 Ready To Process Files</p>
                    <p id="statusLabel">Select files to begin processing</p>
                </div>
                
                <!-- Action Buttons -->
                <div class="buttons-section">
                    <button id="updateTagsBtn" class="primary-btn">✨ Update Tags</button>
                    <button id="updateFilenamesBtn" class="primary-btn">📝 Update Filenames</button>
                    <button id="clearCacheBtn" class="secondary-btn">🗑️ Clear</button>
                    <button id="cancelBtn" class="secondary-btn">✋ Cancel</button>
                    <button id="resetBtn" class="warning-btn">🔄 Reset</button>
                </div>
            </div>
            
            <script src="ui_elements.js"></script>
        </body>
        </html>
        """
    
    def on_drop(self, files):
        """Handle dropped files."""
        self.selected_files = files
        self.update_status(f"Ready to process {len(files)} file(s)")
    
    def update_status(self, message):
        """Update status via JavaScript callback."""
        # JavaScript will call this via pywebview API
        pass
```

**HTML File (index.html):**
- Move existing styles from PyQt6 stylesheets to CSS file
- Create responsive, drag-and-drop enabled HTML interface

**JavaScript File (ui_elements.js):**
- Handle all button click events
- Manage drag-and-drop
- Call Python backend functions via `pywebview.api`
- Update UI dynamically

---

## Summary of Migration Changes

| File | Type | Key Changes | Status |
|------|------|------------|--------|
| `simplified_spotify_integration.py` | Data | Remove QObject/signal, use callback | High Priority |
| `simplified_metadata_searcher.py` | Data | No changes needed | ✓ Done |
| `license_key.py` | UI | Rewrite as HTML/JS | High Priority |
| `dialog_handler.py` | Utility | Replace signals with callbacks | Critical |
| `llm_utils.py` | Utility | Remove QObject/signal, use callback | High Priority |
| `hf_llm_utils.py` | Utility | Remove QObject/signal, use callback | High Priority |
| `spotify_integration.py` | Integration | Remove QObject/signal, use callback | High Priority |
| `mb_integration.py` | Integration | Remove QObject/signal, use callback | High Priority |
| `ui_elements.py` | UI | Complete rewrite as HTML/JS | Critical |

---

## Implementation Priority

1. **Phase 1 (Critical):** 
   - `dialog_handler.py` - Unblock other changes
   - `ui_elements.py` - Main UI framework

2. **Phase 2 (High Priority):**
   - `llm_utils.py` and `hf_llm_utils.py` - Status callbacks
   - `spotify_integration.py` and `mb_integration.py` - Status callbacks
   - `license_key.py` - License management UI

3. **Phase 3 (Cleanup):**
   - `simplified_spotify_integration.py` - Status callback
   - Remove all remaining PyQt6 references

---

## Key Architectural Changes

### Signals → Callbacks
Replace PyQt6's signal/slot mechanism with simple Python callbacks:
```python
# OLD (PyQt6):
signal.emit(value)
signal.connect(handler)

# NEW (Callbacks):
if callback:
    callback(value)
```

### UI → HTML/JavaScript
Replace PyQt6 widgets with HTML/JavaScript:
```python
# OLD (PyQt6):
button = QPushButton("Click me")
button.clicked.connect(on_click)

# NEW (HTML/JavaScript):
<button id="myBtn">Click me</button>
<script>
    document.getElementById('myBtn').addEventListener('click', () => {
        pywebview.api.on_click();
    });
</script>
```

### Thread Safety
Replace PyQt6's thread-safe signals with pywebview's API mechanism:
```python
# OLD (PyQt6):
self.signal.emit(value)  # Thread-safe via event loop

# NEW (pywebview):
# Python backend exposes methods as API
# JavaScript calls them asynchronously
pywebview.api.update_status(message).then(...)
```

---

## Testing Checklist

After migration, verify:
- [ ] All status updates appear in UI correctly
- [ ] Error dialogs display properly
- [ ] Feature artist dialogs work
- [ ] License management works
- [ ] Drag-and-drop functionality works
- [ ] Progress bar updates correctly
- [ ] No console errors
- [ ] All callbacks execute properly

---

## Notes

- **Callbacks Optional:** All callbacks have fallback print statements for logging
- **No Breaking Changes:** External API of these classes remains the same
- **Gradual Migration:** Can be done file-by-file since signals → callbacks is just local change
- **HTML/CSS:** Existing styles in PyQt6 stylesheets should be converted to CSS file
- **Testing:** Each file should be unit tested after migration

