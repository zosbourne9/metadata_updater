# Metadata Updater - Codebase Analysis & PyQt6 to Pywebview Migration Guide

## Executive Summary

The Metadata Updater is a sophisticated audio metadata management application built with **PyQt6**. It processes MP3/M4A files, retrieves metadata from multiple sources (Spotify, MusicBrainz), uses AI (Gemma-3 LLM) for genre detection, and updates file tags. To migrate to **pywebview**, the desktop UI framework needs to be replaced with a web-based interface while preserving all backend functionality.

---

## 1. Current PyQt6 UI Architecture

### 1.1 Entry Point: main.py (176 lines)
**Purpose**: Application initialization and PyQt6 setup

**Key Responsibilities**:
- Initialize QApplication instance
- Configure application style (Fusion theme)
- Set dark theme palette (dark gray/white color scheme)
- Handle macOS-specific configuration (dock icon, window focus)
- Setup debug logging to file
- Handle cache directory management

**PyQt6 Components Used**:
- `QApplication` - Main application instance
- `QMainWindow` - Window management
- `Qt.GlobalColor` - Color constants
- `QIcon` - Icon rendering
- `QMessageBox` - Error dialogs

**Special Handling**:
- macOS app bundling with proper path handling
- Cache directory in: `~/Library/Application Support/Metadata Updater` (macOS) or `~/.metadata_updater` (Linux/Windows)
- Debug logging configuration with file output

---

### 1.2 Main Window: metadata_updater.py (1066 lines)
**Purpose**: Core application logic and main window management

**Key Responsibilities**:
- Initialize and manage UI components
- Handle file selection (files or folders)
- Manage metadata processing workflow
- Control background processing thread (ProcessingThread)
- Update metadata from multiple sources (Spotify, MusicBrainz, AI)
- License management integration
- State management

**PyQt6 Components Used**:
- `QMainWindow` - Main application window
- `QFileDialog` - File/folder selection dialogs
- `QThread` - Background processing
- `pyqtSignal` - Inter-thread communication signals
- `pyqtSlot` - Signal handler decorators

**Key Signals Defined**:
```python
class ProcessingThread(QThread):
    progress = pyqtSignal(int)           # 0-100 progress
    status = pyqtSignal(str)             # Status messages
    current_file = pyqtSignal(str)       # Currently processing file
    finished = pyqtSignal()              # Thread completion
    error = pyqtSignal(str)              # Error messages
    file_completed = pyqtSignal(int, int, int)  # (index, success, errors)
```

**Critical Methods**:
- `__init__()` - 238+ lines of initialization
- `update_metadata()` - 435+ lines of complex metadata retrieval and comparison logic
- `start_update_thread()` - Initiates background processing
- `on_processing_finished()` - Handles thread completion
- `select_files()` / `select_folder()` - File selection
- `reset_application()` - Clean application state
- `save_metadata_to_file()` - Writes metadata to audio files

**Data Flow**:
1. User selects files → `selected_files` list populated
2. User clicks "Update Tags" → `start_update_thread()` called
3. ProcessingThread starts → iterates through `selected_files`
4. For each file: `update_metadata()` is called
5. Signals emitted: progress, status, current_file
6. UI updated via signal connections
7. Thread cleanup and UI re-enabled on completion

**State Variables**:
```python
self.selected_files = []              # Files to process
self.unfound_files = []               # Failed processing
self.processing_thread = None         # Current background thread
self.cancel_requested = False         # Cancellation flag
self.cache_manager = None             # Unified cache
self.utility_tools = None             # HFLLMUtilities instance
self.license_manager = None           # License validation
```

---

### 1.3 UI Elements: ui_elements.py (644 lines)
**Purpose**: Complete UI layout, styling, and widget management

**Key Responsibilities**:
- Build entire application layout (12 major sections)
- Implement drag & drop file handling
- Manage all UI component states
- Handle user interactions
- Apply dark theme styling
- License dialog management

**PyQt6 Components Used**:
- `QWidget` - Base container
- `QVBoxLayout` / `QHBoxLayout` - Layout management
- `QPushButton` - Action buttons
- `QComboBox` - File/Folder selection dropdown
- `QCheckBox` - Metadata field toggles (converted to QPushButton toggles)
- `QLabel` - Text display and status
- `QProgressBar` - Progress indication
- `QFrame` - Container frames with styling
- `QDragEnterEvent` / `QDropEvent` - Drag & drop handling
- `QMessageBox` - Confirmation dialogs

**UI Sections** (in order):
1. **License Banner** (38px) - Shows license status and remaining free files
2. **Header** (Typography) - Title "Audio Metadata Manager" + version
3. **Drop Zone** (90px) - Drag & drop area with hover effect
4. **File Selection** - Combobox (File(s)/Folder) + "Select Files" button
5. **Metadata Fields** - 6 toggle buttons in 2x3 grid:
   - ✅ All
   - 🎤 Artist
   - 💿 Album
   - 🎵 Genre
   - 📅 Year
   - 🏷️ Subgenres
6. **Status Section** - Progress bar + 2 status labels
7. **Action Buttons** (Primary):
   - ✨ Update Tags
   - 📝 Update Filenames
8. **Action Buttons** (Secondary):
   - 🗑️ Clear Cache
   - ✋ Cancel
   - 🔄 Reset
9. **Drop Overlay** - Visual feedback during drag operations

**Styling Approach**:
- Unified dark theme (#374151 background)
- Consistent color scheme: dark gray base, light text
- Emoji icons for visual clarity
- Rounded corners and subtle borders
- Hover effects on interactive elements
- Disabled state styling for inactive buttons

**Key Event Handlers**:
```python
dragEnterEvent(event)          # Drag enter with overlay
dragLeaveEvent(event)          # Drag leave, hide overlay
dropEvent(event)               # Process dropped files
on_update_tags()               # Gather selected fields, start processing
toggle_select_all()            # Toggle all metadata fields
on_artist_toggle()             # Warning dialog for artist changes
clear_all_caches()             # Clear all cache layers
on_drop(files)                 # Validate and process dropped files
```

**Window Properties**:
- Minimum: 300x525 px
- Maximum: 450x750 px
- Default: 360x562 px
- Fixed aspect ratio maintained

---

## 2. Supporting Components & Integrations

### 2.1 Threading & Processing
**Location**: metadata_updater.py lines 26-139

**ProcessingThread Class**:
- Extends `QThread`
- Processes files sequentially in background
- Emits progress signals for UI updates
- Supports cancellation via `cancel_requested` flag
- Tracks success/error counts
- Updates license file count after each successful file

**Flow**:
```
start_update_thread()
  ↓
ProcessingThread.run()
  ↓ (for each file)
update_metadata()
  ↓
emit signals (progress, status, current_file)
  ↓
on_processing_finished() called when done
```

### 2.2 License Management
**Location**: license_key.py

**LicenseManager Class**:
- Validates license keys (20 hardcoded valid keys)
- Tracks processed files count
- Enforces free tier limit (10 files)
- Stores license in `~/.metadata_updater_license` (JSON)

**LicenseDialog (QDialog)**:
- Modal dialog for entering license key
- Qt-based UI with text input and validation button
- Shows success/error messages

**LicenseBanner (Custom Widget)**:
- Status display showing license state
- Shows remaining files for free version
- "Change Key" button opens license dialog

### 2.3 Metadata Retrieval Pipeline
**Location**: metadata_updater.py lines 379-819

**Complex Logic**:
1. Load audio file
2. Extract artist + title
3. Check unified cache
4. Try MusicBrainz first (more reliable for older/classic music)
5. If MusicBrainz incomplete, query Spotify
6. Compare quality scores between sources
7. Use AI (Gemma-3) for multi-artist collaboration genre analysis
8. Fallback to MusicBrainz or AI genre detection
9. Save to cache and write to file

**Quality Scoring Algorithm**:
- Classic era bonus (≤1990): +3 for MB, +2 for Spotify
- Pre-2000 bonus: +2 for MB, +1 for Spotify
- Album=Song title bonus: +2 for MB
- Compilation penalty: -2 for both
- "Mr. " prefix penalty: -1 for Spotify
- Completeness bonus: +1 for Spotify

### 2.4 AI/LLM Integration
**Location**: hf_llm_utils.py (~300+ lines)

**HFLLMUtilities (Singleton)**:
- Uses Hugging Face Transformers library
- Model: google/gemma-3-270m-it (instruction-tuned)
- Lazy-loads model on first use
- Caches LLM responses (hf_llm_cache.json)
- Supports CUDA GPU acceleration
- Uses Qt signals for status updates

**Features**:
- Genre detection from artist/song metadata
- Featured artist extraction from collaboration strings
- Genre analysis for multi-artist collaborations
- Caching to avoid redundant API calls

**PyQt6 Integration**:
- Uses `pyqtSignal` for status emission
- Emits to callback in main thread
- `QMessageBox` for error dialogs

---

## 3. Application Flow Diagram

```
┌─────────────────────────────────────────────┐
│         main.py - initialize_app()          │
│  - Setup logging                            │
│  - Create QApplication                      │
│  - Set dark theme palette                   │
│  - Create MetadataUpdater window            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│   MetadataUpdater.__init__() (238+ lines)   │
│  - Initialize cache_manager                 │
│  - Initialize utility_tools (LLM)           │
│  - Initialize API clients                   │
│  - Initialize license_manager               │
│  - Create UIElements                        │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│      UIElements.setup_ui() (500+ lines)     │
│  - Build all UI widgets                     │
│  - Apply dark theme styling                 │
│  - Connect signals to handlers              │
│  - Enable drag & drop                       │
└─────────────────────────────────────────────┘
                    ↓
            ┌───────┴─────────┐
            ↓                 ↓
    ┌──────────────┐   ┌──────────────────┐
    │ Drag & Drop  │   │ Select Files via │
    │   Files      │   │  Dialog or Click │
    └──────────────┘   └──────────────────┘
            │                 │
            └────────┬────────┘
                     ↓
         ┌───────────────────────────┐
         │  selected_files populated │
         │  Enable action buttons    │
         └───────────────────────────┘
                     ↓
         ┌───────────────────────────┐
         │ User clicks "Update Tags" │
         │ on_update_tags() called   │
         │ Gather selected fields    │
         └───────────────────────────┘
                     ↓
         ┌─────────────────────────────────┐
         │ start_update_thread()           │
         │ Create ProcessingThread         │
         │ Connect all signals             │
         │ Disable UI components          │
         │ Thread.start()                  │
         └─────────────────────────────────┘
                     ↓
         ┌─────────────────────────────────┐
         │ ProcessingThread.run()          │
         │ (background thread)             │
         └─────────────────────────────────┘
            │
            ├─ For each file:
            │  ├─ Emit current_file signal
            │  ├─ update_metadata() - COMPLEX
            │  │  ├─ Load audio file
            │  │  ├─ Check cache
            │  │  ├─ Try MusicBrainz
            │  │  ├─ Try Spotify
            │  │  ├─ Compare quality scores
            │  │  ├─ Detect genres (MB or AI)
            │  │  └─ Save metadata
            │  ├─ Emit progress signal (0-100)
            │  ├─ Emit status signal
            │  └─ Emit file_completed signal
            │
            └─ Emit finished signal
                     ↓
         ┌─────────────────────────────────┐
         │ on_processing_finished()        │
         │ Enable UI components            │
         │ Reset cancel_requested flag     │
         │ Update license banner           │
         └─────────────────────────────────┘
```

---

## 4. PyQt6 Features Used & Their Pywebview Equivalents

### 4.1 Window & Application Management

| PyQt6 | Purpose | Pywebview Equivalent |
|-------|---------|---------------------|
| `QApplication` | Main app instance, event loop | `webview.create_window()`, Python event loop |
| `QMainWindow` | Main window container | Window created by webview |
| `setStyle('Fusion')` | Modern theme | CSS in HTML/JS |
| `setPalette()` | Dark theme colors | CSS variables, Tailwind |
| `QIcon` | Icon rendering | Favicon, image files |

### 4.2 Layout & Widgets

| PyQt6 | Purpose | Pywebview Equivalent |
|-------|---------|---------------------|
| `QVBoxLayout/QHBoxLayout` | Widget layout | CSS flexbox, grid |
| `QPushButton` | Clickable buttons | HTML `<button>`, JavaScript click handlers |
| `QLabel` | Text display | HTML `<p>`, `<div>`, `<span>` |
| `QProgressBar` | Progress indication | HTML progress bar or custom element |
| `QComboBox` | Dropdown selection | HTML `<select>` |
| `QCheckBox` | Toggle checkbox | HTML `<input type="checkbox">` |
| `QFrame` | Container with border | HTML `<div>` with CSS |
| `QLineEdit` | Text input | HTML `<input type="text">` |
| `QMessageBox` | Dialog popups | Modal HTML div or alert() |

### 4.3 File Operations

| PyQt6 | Purpose | Pywebview Equivalent |
|-------|---------|---------------------|
| `QFileDialog.getOpenFileNames()` | Multi-file selection | `webview.api.select_files()` (custom backend call) |
| `QFileDialog.getExistingDirectory()` | Folder selection | `webview.api.select_folder()` (custom backend call) |
| Drag & Drop Events | File drag/drop | HTML5 Drag & Drop API |

### 4.4 Threading & Signals

| PyQt6 | Purpose | Pywebview Equivalent |
|-------|---------|---------------------|
| `QThread` | Background processing | Python `threading.Thread` |
| `pyqtSignal` | Inter-thread signals | Websocket or REST API calls |
| `pyqtSlot` | Signal handlers | Python function that gets called via API |
| Signal connections | Bind signals to slots | JavaScript event listeners |

### 4.5 Dialogs & User Interaction

| PyQt6 | Purpose | Pywebview Equivalent |
|-------|---------|---------------------|
| `QMessageBox` (warning, critical, info) | User notifications | Modal HTML dialog, or toast notifications |
| `QDialog` | Modal dialogs (LicenseDialog) | HTML modal overlays |
| Event handlers | User interactions | JavaScript event listeners |

---

## 5. Data Flow Between Frontend & Backend

### Current (PyQt6)
```
UI Components (Qt Widgets) ←→ Signal/Slot System ←→ Backend Python Code
                                ↓
                        Qt Event Loop Processes
                                ↓
                        Direct Memory Access
```

### Proposed (Pywebview)
```
HTML/CSS/JavaScript ←→ Python API Methods ←→ Backend Python Code
                                ↓
                        Websocket or REST API
                                ↓
                        JSON Serialization/Deserialization
```

### Critical Communication Points to Implement

1. **File Selection**
   - Current: Qt file dialogs return paths directly
   - New: JS calls Python API → opens OS file dialog → returns paths to JS

2. **Progress Updates**
   - Current: Qt signals emitted to update UI in real-time
   - New: Python calls JS function or WebSocket message to update progress

3. **Status Messages**
   - Current: `update_status_label()` slot receives signal
   - New: Python calls JS function to update status display

4. **Action Triggers**
   - Current: Qt button clicked → signal → slot method
   - New: JS onclick → Python API call → executes method

5. **Drag & Drop**
   - Current: Qt drag/drop events with custom handlers
   - New: HTML5 drag/drop API with JS handlers

---

## 6. Features Requiring Migration

### 6.1 High Priority (Core Functionality)

- [x] **File Selection UI**
  - Implement file picker buttons in HTML
  - Create Python API endpoint: `select_files()` → opens dialog → returns paths
  - Create Python API endpoint: `select_folder()` → opens dialog → returns paths

- [x] **Metadata Field Toggles**
  - 6 toggle buttons with state management in JavaScript
  - Track selected fields in `window.selectedFields` object
  - Send selected fields to Python when processing starts

- [x] **Processing Thread Management**
  - Keep `ProcessingThread` class (no changes needed)
  - Create Python API endpoint: `start_processing(selected_fields)`
  - Implement progress callback: `update_ui_progress(progress, status, current_file)`

- [x] **Progress Bar & Status Display**
  - HTML progress element with CSS
  - Update via JavaScript function from Python callbacks
  - Show current file name and overall progress

- [x] **License Banner & Dialog**
  - License banner in HTML with CSS styling
  - Modal license dialog with text input
  - Python API: `validate_license(key)`, `get_license_status()`

- [x] **Drop Zone Styling**
  - HTML drag & drop area with hover effects
  - JavaScript handlers for drag enter/leave/drop
  - Validate file types (mp3, m4a) in JavaScript

### 6.2 Medium Priority (Polish & UX)

- [x] **Dark Theme Styling**
  - Migrate palette colors to CSS variables
  - Use Tailwind CSS or custom CSS
  - Maintain exact color scheme: #374151, #f3f4f6, etc.

- [x] **Window Resize & State**
  - CSS for responsive layout
  - Fixed window size: 360x562 px
  - Min/Max size constraints

- [x] **Button States & Feedback**
  - CSS for hover, active, disabled states
  - Visual feedback on interaction
  - Loading states during processing

- [x] **Modal Dialogs**
  - License key dialog
  - Confirmation dialogs (artist warning, reset confirmation)
  - Error notifications

### 6.3 Lower Priority (Maintenance)

- [x] **Cache Directory Management**
  - Keep Python-side cache management
  - No UI changes needed

- [x] **Logging Setup**
  - Keep Python logging unchanged
  - Continue writing to debug file

- [x] **macOS-Specific Handling**
  - Bundle configuration
  - Dock icon
  - Window focus/raising

---

## 7. Technical Challenges & Solutions

### Challenge 1: Real-time Progress Updates
**Problem**: Qt signals provided real-time UI updates. Pywebview needs websocket or polling.

**Solution Options**:
1. **WebSocket** (Recommended)
   - Bi-directional communication
   - Real-time updates with low latency
   - Use `python-socketio` or `websocket-client`

2. **Polling** (Simpler)
   - JavaScript polls Python API every 100ms
   - Updates UI when progress changes
   - Less resource-intensive but slightly delayed

3. **Event Callbacks**
   - Python passes JS callback function reference
   - Call JS function directly from Python

**Recommended**: Use polling for simplicity or WebSocket for better UX.

### Challenge 2: File Dialog Integration
**Problem**: Qt file dialogs are native. JavaScript can't open OS file dialogs.

**Solution**:
- Create Python API endpoints that use `QFileDialog` or `tkinter.filedialog`
- JavaScript calls Python API
- Python opens native dialog and returns result
- Python sends result back to JavaScript

```python
@webview.expose
def select_files():
    """Open file dialog and return selected file paths."""
    files, _ = QFileDialog.getOpenFileNames(
        None,  # No parent window
        "Select Audio Files",
        "",
        "Audio Files (*.mp3 *.m4a)"
    )
    return files
```

### Challenge 3: Thread Safety with WebSocket
**Problem**: ProcessingThread must safely communicate with JS frontend.

**Solution**:
- Keep ProcessingThread unchanged
- Add Python method that JS calls to get current progress
- Use polling or queue-based approach
- Ensure thread-safe access to state variables

### Challenge 4: Modal Dialogs
**Problem**: QMessageBox is native. JavaScript alternatives are less polished.

**Solution**:
1. **HTML/CSS Modal**: Build custom modal in HTML
2. **Async Handling**: Use Promise-based approach
3. **Keyboard Handling**: Escape key, Enter to confirm

### Challenge 5: Drag & Drop Preservation
**Problem**: Qt drag/drop with visual overlay needs recreation.

**Solution**:
- HTML5 Drag & Drop API (well-supported)
- CSS for hover effects
- JavaScript event handlers for dragover, dragleave, drop
- Validate file types in JavaScript

---

## 8. Migration Implementation Strategy

### Phase 1: Infrastructure (1-2 days)
1. Setup pywebview project structure
2. Create HTML/CSS/JS base files
3. Setup Python API endpoints framework
4. Initialize webview with window configuration

### Phase 2: UI Replication (2-3 days)
1. Recreate all UI elements in HTML
2. Apply CSS styling matching current dark theme
3. Create license banner and dialog in HTML
4. Implement drag & drop zone

### Phase 3: Backend Integration (2-3 days)
1. Create Python API endpoints for file selection
2. Implement progress callback system
3. Add license dialog validation API
4. Setup signal/callback mechanism for status updates

### Phase 4: Feature Implementation (3-4 days)
1. Implement metadata field toggle system
2. Create processing start/cancel endpoints
3. Add progress bar updates
4. Implement license banner updates

### Phase 5: Testing & Polish (2-3 days)
1. Test all file operations
2. Verify progress tracking accuracy
3. Test license validation
4. Polish UI/UX and styling
5. Test on macOS/Windows/Linux

### Phase 6: Packaging (1 day)
1. Update PyInstaller spec for pywebview
2. Test bundled application
3. Verify icon and resources are included

---

## 9. Key Files to Maintain

These Python files contain core logic that needs NO CHANGES:
- `metadata_updater.py` - Keep entire ProcessingThread and metadata logic
- `hf_llm_utils.py` - Keep LLM functionality, remove only Qt dependencies
- `integration_helper.py` - Keep metadata integration logic
- `genre_finder.py` - Keep genre detection
- `unified_cache_manager.py` - Keep caching
- `artist_normalizer.py` - Keep artist normalization
- `license_key.py` - Keep LicenseManager, remove LicenseDialog/LicenseBanner

**Files to Modify**:
- `main.py` - Replace QApplication with pywebview
- `ui_elements.py` - Remove entirely (replace with HTML/CSS/JS)
- Create `app.py` or `api.py` - Expose Python methods to frontend

**Files to Create**:
- `index.html` - Main UI
- `styles.css` - All styling
- `app.js` - Frontend logic and API interactions
- `api.py` or `endpoints.py` - Python API endpoints

---

## 10. Component Dependencies Map

```
main.py
  ↓
MetadataUpdater (metadata_updater.py)
  ├─ HFLLMUtilities (hf_llm_utils.py)
  │  ├─ transformers (Hugging Face)
  │  └─ torch (PyTorch)
  ├─ SimplifiedMetadataIntegration (integration_helper.py)
  │  ├─ Spotify API client
  │  └─ MusicBrainz API client
  ├─ GenreFinder (genre_finder.py)
  ├─ ArtistNormalizer (artist_normalizer.py)
  ├─ UnifiedCacheManager (unified_cache_manager.py)
  ├─ LicenseManager (license_key.py)
  └─ UIElements (ui_elements.py) ← REMOVE
      ├─ LicenseBanner ← MOVE TO HTML
      └─ LicenseDialog ← MOVE TO HTML

ProcessingThread (metadata_updater.py)
  ├─ Emits Qt signals ← CHANGE TO CALLBACKS
  └─ Calls update_metadata()
```

---

## 11. Estimated Metrics

| Aspect | Count | Notes |
|--------|-------|-------|
| Total Python Files | 26 | Excluding .venv |
| PyQt6 imports | 75+ | Across all files |
| Lines of UI code (Qt) | 1900+ | main.py + metadata_updater.py + ui_elements.py |
| Lines to migrate | ~1900 | To HTML/CSS/JS |
| Lines to keep unchanged | ~3000+ | Core metadata logic |
| API endpoints needed | 8-10 | File selection, processing, license |
| HTML elements | ~50-70 | Form controls, status display |

---

## 12. Critical PyQt6 Features & Replacements

### Signals & Slots System
**What it does**: Enables communication between UI components and backend

**Current Usage**:
```python
class ProcessingThread(QThread):
    progress = pyqtSignal(int)          # Emitted from thread
    
# In main thread:
self.processing_thread.progress.connect(self.ui_elements.progress_bar.setValue)
```

**New Approach - Option A (Polling)**:
```python
# JavaScript polls for progress
function updateProgress() {
    api.get_progress().then(data => {
        progressBar.value = data.progress;
        statusLabel.textContent = data.status;
    });
    setTimeout(updateProgress, 100);
}
```

**New Approach - Option B (Callbacks)**:
```python
# Python calls JavaScript function directly
webview.evaluate_js("updateProgress({progress: 50, status: 'Processing...'})")
```

---

## 13. Summary for Migration Planning

### What's Easy to Migrate
✅ Button clicks → JavaScript event listeners  
✅ Text updates → JavaScript DOM manipulation  
✅ File operations → Python file system calls + API  
✅ Styling → CSS from palette colors  
✅ Progress tracking → Polling or callbacks  

### What Needs Careful Implementation
⚠️ Real-time progress updates → WebSocket or polling strategy needed  
⚠️ Threading coordination → Python threads + JS updates via API  
⚠️ File dialogs → Use OS-native dialogs via Python API  
⚠️ Modal dialogs → HTML/CSS modals instead of QMessageBox  
⚠️ Drag & drop overlay → HTML5 Drag & Drop API  

### What Stays Unchanged
✓ All metadata processing logic  
✓ LLM integration and caching  
✓ License management logic  
✓ File I/O and audio tag writing  
✓ API integrations (Spotify, MusicBrainz)  
✓ Background threading model  

---

## 14. Quick Reference: PyQt6 Element Mapping

| UI Element | PyQt6 | HTML Equivalent |
|-----------|-------|-----------------|
| Window | `QMainWindow` | `<div id="app">` |
| Button | `QPushButton` | `<button>` |
| Text Label | `QLabel` | `<p>`, `<span>` |
| Text Input | `QLineEdit` | `<input type="text">` |
| Progress | `QProgressBar` | `<progress>` or div |
| Dropdown | `QComboBox` | `<select>` |
| Checkbox | `QCheckBox` | `<input type="checkbox">` |
| Container | `QFrame` | `<div>` |
| Layout | `QVBoxLayout` | CSS flexbox/grid |
| Dialog | `QDialog` | HTML `<div class="modal">` |
| File Dialog | `QFileDialog` | Python API call |
| Status Update | `pyqtSignal` | API call from Python |

---

## Conclusion

The Metadata Updater has a **well-structured separation of concerns**:
- **Logic layer** (80%): Complex metadata processing, caching, AI integration - can be reused entirely
- **UI layer** (20%): PyQt6-based interface - needs to be completely rebuilt in HTML/CSS/JS

The migration is **technically feasible** with **no significant feature loss**. The main challenges are around real-time progress updates and file dialog integration, both of which have straightforward solutions. The estimated migration effort is **10-15 days** for a team of 1-2 developers.
