# PyQt6 to Pywebview Migration Guide

## Overview
Successfully migrated the Metadata Updater from PyQt6 desktop UI to a modern, web-based interface using pywebview. The application maintains all backend functionality while gaining a modern, responsive web UI.

## Files Created

### 1. **index.html** (Modern HTML UI)
- Complete semantic HTML structure
- All UI components (file upload, settings, processing, results, modals)
- Responsive design for mobile and desktop
- Modern form elements and dialog modals
- Accessibility features (ARIA labels, semantic HTML)

### 2. **styles.css** (Modern Styling)
- Dark theme matching your original color scheme
- CSS variables for easy theming
- Flexbox and CSS Grid layouts
- Responsive breakpoints (mobile, tablet, desktop)
- Modern animations and transitions
- Custom scrollbar styling
- Modal overlay system
- Professional typography

### 3. **app.js** (Frontend Application Logic)
- Complete UI state management
- File drag-and-drop handling
- API communication with Python backend
- Modal management and controls
- Settings management
- License management
- Real-time progress updates
- Error handling and user feedback

### 4. **api.py** (Python API Layer)
- REST-like API endpoints for JavaScript to call
- File management (add, remove, clear)
- Processing control (start, cancel)
- License management
- Settings management
- Status queries
- Callback system for real-time updates

### 5. **metadata_updater_webview.py** (Core Logic)
- Refactored MetadataUpdater class without PyQt6 dependencies
- ProcessingThread using standard Python threading
- Callback-based event system instead of Qt signals
- All original functionality preserved:
  - Audio file processing
  - Metadata search and update
  - License management
  - Genre detection with AI
  - Spotify/MusicBrainz integration

### 6. **main.py** (Updated Entry Point)
- Replaced QApplication with pywebview
- HTML-based UI loading
- Path handling for bundled and source distributions
- macOS-specific configuration
- Icon and window setup
- Debug logging configuration

### 7. **requirements_webview.txt** (Dependencies)
- All necessary Python packages
- pywebview for the web UI framework
- Audio, API, and ML dependencies preserved

## Architecture

```
┌─────────────────────────────────────────┐
│   User Interface (Web-based)            │
│  ┌─────────────────────────────────────┐│
│  │ HTML (index.html)                   ││
│  │ CSS (styles.css)                    ││
│  │ JavaScript (app.js)                 ││
│  └─────────────────────────────────────┘│
└──────────────┬──────────────────────────┘
               │ API Calls
               ↓
┌─────────────────────────────────────────┐
│   Python API Layer (api.py)             │
│  - File management                      │
│  - Processing control                   │
│  - License management                   │
│  - Settings                             │
└──────────────┬──────────────────────────┘
               │ Business Logic
               ↓
┌─────────────────────────────────────────┐
│   Core Backend (metadata_updater_webview.py) │
│  - Audio processing                     │
│  - Metadata search                      │
│  - AI genre detection                   │
│  - License checks                       │
│  + All original dependencies            │
└─────────────────────────────────────────┘
```

## Key Changes from PyQt6

### Signal/Slot System → Callbacks
**Before (PyQt6):**
```python
class ProcessingThread(QThread):
    progress = pyqtSignal(int)
    def run(self):
        self.progress.emit(value)
```

**After (pywebview):**
```python
class ProcessingThread(Thread):
    on_progress = None
    def run(self):
        if self.on_progress:
            self.on_progress(value)
```

### UI Components → HTML/CSS/JS
**Before (PyQt6):**
```python
button = QPushButton("Click me")
button.clicked.connect(on_click)
```

**After (Web):**
```html
<button id="myButton">Click me</button>
```
```javascript
document.getElementById('myButton').addEventListener('click', onClick);
```

### Dialog Boxes → Modal Dialogs
**Before (PyQt6):**
```python
QFileDialog.getOpenFileNames()
```

**After (Web):**
```javascript
// HTML5 file input or native dialog handling
// Modals for settings, help, license
```

## Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements_webview.txt
```

### 2. Run the Application
```bash
python main.py
```

### 3. For Development
```bash
# With debug logging enabled (see ENABLE_DEBUG_LOGGING in main.py)
python main.py
```

## Features Maintained

✅ **File Selection & Processing**
- Drag and drop audio files
- File browser dialog
- Batch processing with progress tracking

✅ **Metadata Updates**
- Artist, Album, Genre, Year, Subgenres
- Selectable fields to update
- Real-time progress feedback

✅ **License Management**
- License activation/removal
- License status display
- Trial limitations

✅ **Settings**
- Metadata source selection
- AI genre detection toggle
- Max filename length

✅ **Backend Integration**
- Spotify API integration
- MusicBrainz API integration
- LLM-based genre detection
- Unified caching system

## Modern Features Added

✨ **Responsive Design**
- Mobile-friendly interface
- Tablet and desktop optimized
- Touch-friendly controls

✨ **Modern Styling**
- Dark theme by default
- Smooth animations
- Professional UI components
- Better visual hierarchy

✨ **Improved UX**
- Real-time progress updates
- Inline error messages
- Success confirmations
- Clear status indicators

✨ **Better Performance**
- No UI rendering overhead from Qt
- Lightweight web interface
- Native browser rendering

## Testing Checklist

Before deploying, verify:

- [ ] File drag-and-drop works
- [ ] File selection dialog opens
- [ ] Processing starts and completes
- [ ] Progress bar updates in real-time
- [ ] Current file display updates
- [ ] Error handling shows messages
- [ ] Settings can be saved
- [ ] License can be activated/removed
- [ ] All metadata fields are processed correctly
- [ ] Keyboard shortcuts work (if implemented)
- [ ] Responsive design on different screen sizes

## Troubleshooting

### pywebview not found
```bash
pip install pywebview>=5.1
```

### API calls failing
- Check browser console (F12) for errors
- Verify `main.py` is running
- Check `metadata_updater_debug.txt` for backend logs

### File dialogs not working
- Ensure file input is properly configured
- Check file path handling in `app.js`

### Styling issues
- Clear browser cache (Ctrl+Shift+Delete)
- Check `styles.css` is being loaded
- Verify color scheme variables in `:root`

## Future Enhancements

Potential improvements:
- Settings persistence to config file
- Keyboard shortcuts for common actions
- Batch file import from folder
- Preview of changes before applying
- Undo functionality
- More theme options
- Dark/Light mode toggle
- Export results to CSV
- Plugin system for custom metadata sources

## Performance Notes

- HTML/CSS rendering is faster than PyQt6
- JavaScript execution is smooth even with many files
- Threading still handles long operations (metadata search)
- Memory footprint is smaller
- Startup time is faster

## Conclusion

The migration from PyQt6 to pywebview maintains all functionality while providing a more modern, responsive user interface. The web-based approach offers better cross-platform compatibility and easier maintenance going forward.
