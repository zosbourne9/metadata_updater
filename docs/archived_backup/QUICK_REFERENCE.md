# PyQt6 to Pywebview Migration - Quick Reference Guide

## Files Overview

### To Keep (No UI Changes)
- `integration_helper.py` - Metadata retrieval logic ✓
- `genre_finder.py` - Genre detection ✓
- `artist_normalizer.py` - Artist name cleaning ✓
- `unified_cache_manager.py` - Caching system ✓
- `constants.py` - Configuration ✓
- `dialog_handler.py` - Dialog utilities ✓
- All other backend modules ✓

### To Modify
- **main.py**: Replace `QApplication` with `pywebview.create_window()`
- **metadata_updater.py**: Keep `ProcessingThread` & logic, remove Qt imports, add API endpoints
- **license_key.py**: Keep `LicenseManager`, remove `LicenseDialog` & `LicenseBanner` classes

### To Remove
- **ui_elements.py**: Entire file (644 lines) - replace with HTML/CSS/JS

### To Create
- **index.html**: Main UI (50-70 elements)
- **styles.css**: Dark theme styling
- **app.js**: Frontend logic & API interactions
- **api.py**: Python API endpoints (8-10 methods)

---

## UI Element Mapping Quick Reference

| PyQt6 | HTML | CSS | JavaScript |
|-------|------|-----|-----------|
| `QMainWindow` | `<div id="app">` | Layout | - |
| `QPushButton` | `<button>` | `.btn` | onclick handlers |
| `QLabel` | `<p>`, `<span>` | `.label` | textContent |
| `QLineEdit` | `<input type="text">` | `.input` | value, change handlers |
| `QProgressBar` | `<progress>` | `.progress` | value attribute |
| `QComboBox` | `<select>` | `.dropdown` | change handlers |
| `QCheckBox` | `<input type="checkbox">` | `.checkbox` | checked property |
| `QFrame` | `<div>` | `.container` | - |
| `QVBoxLayout` | `<div>` | `flex-direction: column` | - |
| `QHBoxLayout` | `<div>` | `flex-direction: row` | - |
| `QDialog` | `<div class="modal">` | `.modal, .overlay` | show/hide |
| `QMessageBox` | Modal `<div>` | `.dialog` | Event handlers |
| `QFileDialog` | - | - | Python API call |
| `pyqtSignal` | - | - | API polling or callback |

---

## Key Python API Endpoints to Implement

```python
# File Selection
@webview.expose
def select_files():
    """Open file dialog, return list of paths"""
    
@webview.expose
def select_folder():
    """Open folder dialog, return folder path"""

# Processing Control
@webview.expose
def start_processing(selected_fields):
    """Start metadata processing thread"""
    
@webview.expose
def cancel_processing():
    """Cancel running processing thread"""
    
@webview.expose
def get_progress():
    """Return {progress, status, current_file}"""

# License Management
@webview.expose
def validate_license(key):
    """Validate and save license key"""
    
@webview.expose
def get_license_status():
    """Return license status and remaining files"""

# Cache Management
@webview.expose
def clear_caches():
    """Clear all caches"""
```

---

## Key JavaScript Functions to Implement

```javascript
// File Selection
async function selectFiles() {
    const files = await api.select_files();
    updateFileList(files);
}

// Update Progress (polling approach)
let progressInterval;
function startProgressPolling() {
    progressInterval = setInterval(async () => {
        const {progress, status, current_file} = await api.get_progress();
        updateProgressBar(progress);
        updateStatusLabels(status, current_file);
    }, 100);
}

// Processing Control
async function startProcessing() {
    const selectedFields = getSelectedFields();
    await api.start_processing(selectedFields);
    startProgressPolling();
}

async function cancelProcessing() {
    await api.cancel_processing();
    clearInterval(progressInterval);
}

// UI State Management
function getSelectedFields() {
    return {
        artist: toggles.artist.checked,
        album: toggles.album.checked,
        genre: toggles.genre.checked,
        year: toggles.year.checked,
        comments: toggles.comments.checked
    };
}

function updateUI(disabled) {
    updateTagsBtn.disabled = disabled;
    updateFilenamesBtn.disabled = disabled;
    selectFilesBtn.disabled = disabled;
}
```

---

## Color Scheme (Copy from Current Theme)

```css
:root {
    --bg-primary: #374151;      /* Main background */
    --bg-secondary: rgba(0, 0, 0, 0.15);  /* Card backgrounds */
    --bg-tertiary: rgba(0, 0, 0, 0.3);    /* Hover effects */
    
    --text-primary: #f3f4f6;    /* Main text */
    --text-secondary: #d1d5db;  /* Secondary text */
    --text-tertiary: #9ca3af;   /* Tertiary text */
    
    --border-color: rgba(255, 255, 255, 0.1);
    --border-color-hover: rgba(255, 255, 255, 0.25);
    
    --btn-primary: #3b82f6;     /* Blue buttons */
    --btn-primary-hover: #2563eb;
    --btn-primary-active: #1d4ed8;
    
    --btn-success: #10b981;     /* Green (toggles) */
    --btn-success-hover: #059669;
    
    --btn-danger: #ef4444;      /* Red (cancel) */
    --btn-danger-hover: #f87171;
    
    --btn-warning: #f59e0b;     /* Orange (reset) */
    --btn-warning-hover: #d97706;
}
```

---

## Current UI Sections (What to Rebuild)

1. **License Banner** (38px)
   - License status text
   - "Change Key" button
   - Remaining files counter

2. **Header**
   - Title: "Audio Metadata Manager"
   - Version: "v1.7"

3. **Drop Zone** (90px)
   - "Drop audio files here" message
   - Dashed border
   - Hover effects

4. **File Selection**
   - Dropdown: "📁 File(s)" or "📂 Folder"
   - Button: "✨ Select Files"

5. **Metadata Toggles** (2x3 grid)
   - ✅ All
   - 🎤 Artist (with warning on toggle)
   - 💿 Album
   - 🎵 Genre
   - 📅 Year
   - 🏷️ Subgenres

6. **Status Display**
   - Progress bar (0-100%)
   - Current file label
   - Overall status message

7. **Primary Buttons**
   - "✨ Update Tags" (disabled until files selected)
   - "📝 Update Filenames" (disabled until files selected)

8. **Secondary Buttons**
   - "🗑️ Clear" (clear all caches)
   - "✋ Cancel" (cancel processing)
   - "🔄 Reset" (reset application)

9. **License Dialog** (Modal)
   - Title: "Enter License Key"
   - Text input with placeholder
   - "Validate" button
   - Status message display

---

## Migration Checklist

### Phase 1: Setup
- [ ] Install pywebview
- [ ] Create project structure
- [ ] Setup HTML skeleton
- [ ] Link CSS & JS files

### Phase 2: HTML Structure
- [ ] License banner
- [ ] Header section
- [ ] Drop zone with validation
- [ ] File selection controls
- [ ] Metadata toggle grid
- [ ] Status display section
- [ ] Action buttons
- [ ] License modal

### Phase 3: CSS Styling
- [ ] Define CSS variables for colors
- [ ] Style buttons (all states)
- [ ] Style drop zone (normal/hover/active)
- [ ] Style progress bar
- [ ] Style modal dialogs
- [ ] Responsive layout (flexbox/grid)
- [ ] Dark theme application

### Phase 4: JavaScript Core
- [ ] Toggle button state management
- [ ] File selection integration
- [ ] Drag & drop handlers
- [ ] Modal open/close
- [ ] Form validation

### Phase 5: Python API
- [ ] Expose select_files() method
- [ ] Expose select_folder() method
- [ ] Expose start_processing() method
- [ ] Expose cancel_processing() method
- [ ] Expose get_progress() method
- [ ] Expose validate_license() method
- [ ] Expose clear_caches() method

### Phase 6: Integration
- [ ] Connect button clicks to API calls
- [ ] Setup progress polling
- [ ] Handle processing completion
- [ ] Update UI state during processing
- [ ] Handle errors & edge cases

### Phase 7: Testing
- [ ] File selection (files & folders)
- [ ] Drag & drop functionality
- [ ] Progress tracking
- [ ] License validation
- [ ] Cancel/reset operations
- [ ] Cross-platform testing (macOS/Windows/Linux)

### Phase 8: Packaging
- [ ] Update main.py for pywebview
- [ ] Create PyInstaller spec
- [ ] Test bundled application
- [ ] Verify all resources included

---

## Important Implementation Notes

### Progress Update Strategy
**Recommended**: Polling approach
- JavaScript polls `get_progress()` every 100ms
- Less complex than WebSocket
- Sufficient for smooth UI updates
- Easy to implement with current architecture

### Threading Safety
- Keep `ProcessingThread` unchanged
- Use thread-safe state variables
- Access state only via Python API methods
- Use locks if needed (threading.Lock)

### File Dialog Integration
- Use tkinter.filedialog as fallback (works cross-platform)
- Or use pywebview.api for native dialogs if available
- Return absolute paths from Python
- Validate paths in both Python & JavaScript

### Drag & Drop
- HTML5 Drag & Drop API (well-supported)
- Prevent default browser behavior
- Validate file extensions (.mp3, .m4a)
- Show visual feedback on dragover

### Error Handling
- Catch exceptions in Python API methods
- Return error messages to JavaScript
- Show error modals to user
- Log errors to debug file

### License Dialog
- Modal overlay that blocks main UI
- ESC key to close
- ENTER to submit
- Real-time key validation feedback

---

## Performance Considerations

1. **Model Loading**: LLM loads on first genre detection → ~30-60 seconds
   - Show loading indicator
   - Disable UI during load
   - Cache model after first load

2. **API Calls**: Spotify/MusicBrainz may be slow
   - Show current file being processed
   - Implement request timeouts
   - Cache results

3. **File I/O**: Writing to many files → progress updates important
   - Update progress after each file
   - Show current file name
   - Allow cancellation mid-process

4. **Memory**: Processing large libraries
   - Don't load all files into memory
   - Process one file at a time
   - Clear temporary data after each file

---

## Known Issues & Solutions

**Issue**: Artist toggle warning appears twice
**Solution**: Track warning state in JavaScript, show only once

**Issue**: File paths with spaces cause issues
**Solution**: Properly quote paths in Python, validate in JavaScript

**Issue**: Progress bar doesn't update smoothly
**Solution**: Poll every 100ms, or use WebSocket for real-time

**Issue**: License dialog not modal enough
**Solution**: Use overlay div with pointer-events: auto

**Issue**: Drag & drop not working on nested elements
**Solution**: Set pointer-events: none on children, handle on parent

---

## Useful Resources

- **Pywebview Docs**: https://pywebview.kivy.org/
- **HTML5 Drag & Drop**: https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API
- **File Dialog Alternatives**:
  - tkinter.filedialog (built-in Python)
  - pywebview native file dialogs (if available)
  - Web-based file picker (if needed)

---

## Questions to Answer Before Starting

1. What progress update strategy? (Polling vs WebSocket)
2. Should license validation be immediate or on button click?
3. What happens on network errors?
4. Should app auto-refresh file dialogs or use cache?
5. How handle multi-file drag drop (accumulate or replace)?
6. Should processing be pausable or just cancellable?
7. Target Python version? (3.8+, 3.9+, 3.10+?)
8. Deploy as executable or script + interpreter?
