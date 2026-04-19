/**
 * Metadata Updater - Modern Web UI
 * Main JavaScript application file
 * Handles UI interactions and communication with Python backend via pywebview
 */

// ============================================
// STATE MANAGEMENT
// ============================================

const appState = {
    selectedFiles: [],
    processing: false,
    processingStats: {
        totalFiles: 0,
        processed: 0,
        successful: 0,
        errors: 0
    },
    selectedFields: {
        artist: false,
        album: false,
        genre: false,
        year: false,
        subgenres: false,
        rating: false
    },
    riddimMode: {
        isDancehall: false,
        isReggae: false
    },
    licenseStatus: {
        isActive: false,
        filesProcessed: 0,
        licenseType: 'trial'
    },
    reviewMode: {
        active: false,
        currentFile: null,
        candidates: [],
        bestMatch: null,
        selectedIndex: -1,
        queue: [] // Queue for multiple pending reviews
    }
};

// ============================================
// UTILITY FUNCTIONS
// ============================================

/**
 * Call Python API method via pywebview
 */
async function callAPI(method, ...args) {
    try {
        if (window.pywebview && window.pywebview.api) {
            return await window.pywebview.api[method](...args);
        } else {
            console.error('pywebview API not available');
            return { success: false, message: 'App not initialized' };
        }
    } catch (error) {
        console.error(`API error calling ${method}:`, error);
        return { success: false, message: `API error: ${error.message}` };
    }
}

/**
 * Show modal dialog
 */
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    const overlay = document.getElementById('modalOverlay');
    if (modal && overlay) {
        modal.classList.add('active');
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';

        // For review modal, bring it to front and add visual attention
        if (modalId === 'candidateReviewModal') {
            modal.style.zIndex = '10000';
            overlay.style.zIndex = '9999';
            // Add pulse animation to draw attention
            modal.classList.add('pulse-attention');
            
            // Only show notification for the first item in queue
            if (appState.reviewMode.queue.length <= 1) {
                showNotification('Action Required: Please review metadata candidates', 'info');
            }
        }
    }
}

/**
 * Hide modal dialog
 */
function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    const overlay = document.getElementById('modalOverlay');
    if (modal) {
        modal.classList.remove('active');
    }
    
    // Check if we need to show another review modal from queue
    if (modalId === 'candidateReviewModal' && appState.reviewMode.queue.length > 0) {
        // Don't remove overlay, just show next review
        setTimeout(() => processNextReview(), 100);
        return;
    }

    // Check if any other modals are open
    const openModals = document.querySelectorAll('.modal.active');
    const anyOpen = openModals.length > 0;
    
    if (!anyOpen && overlay) {
        overlay.classList.remove('active');
        document.body.style.overflow = 'auto';
        // Reset any specific styles that might cause issues
        overlay.style.display = '';
        overlay.style.zIndex = '';
    }
}

/**
 * Process the next review in the queue
 */
function processNextReview() {
    if (appState.reviewMode.queue.length === 0) {
        appState.reviewMode.active = false;
        return;
    }

    const nextReview = appState.reviewMode.queue.shift();
    appState.reviewMode.active = true;
    appState.reviewMode.currentFile = nextReview.filePath;
    appState.reviewMode.candidates = nextReview.candidates;
    appState.reviewMode.bestMatch = nextReview.bestMatch;
    appState.reviewMode.selectedIndex = -1;

    console.log('Processing next review from queue:', nextReview.filePath);
    console.log('Remaining in queue:', appState.reviewMode.queue.length);

    showCandidateReviewModal();
}

/**
 * Show notification to user
 */
function showNotification(message, type = 'info') {
    // Create notification element if it doesn't exist
    let notificationContainer = document.getElementById('notificationContainer');
    if (!notificationContainer) {
        notificationContainer = document.createElement('div');
        notificationContainer.id = 'notificationContainer';
        notificationContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 99999;
            max-width: 400px;
        `;
        document.body.appendChild(notificationContainer);
    }

    const notification = document.createElement('div');
    notification.style.cssText = `
        background: ${type === 'error' ? '#ff6b6b' : type === 'success' ? '#51cf66' : '#4dabf7'};
        color: white;
        padding: 16px 20px;
        margin-bottom: 10px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        font-size: 14px;
        animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = message;
    notificationContainer.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

/**
 * Show confirmation dialog
 * Returns a promise that resolves to true if confirmed, false if cancelled
 */
function showConfirmation(title, message) {
    return new Promise((resolve) => {
        document.getElementById('confirmationTitle').textContent = title;
        document.getElementById('confirmationMessage').textContent = message;

        const confirmBtn = document.getElementById('confirmationConfirmBtn');
        const cancelBtn = document.getElementById('confirmationCancelBtn');
        const closeBtn = document.getElementById('closeConfirmationModal');

        const handleConfirm = () => {
            cleanup();
            hideModal('confirmationModal');
            resolve(true);
        };

        const handleCancel = () => {
            cleanup();
            hideModal('confirmationModal');
            resolve(false);
        };

        const cleanup = () => {
            confirmBtn.removeEventListener('click', handleConfirm);
            cancelBtn.removeEventListener('click', handleCancel);
            closeBtn.removeEventListener('click', handleCancel);
        };

        confirmBtn.addEventListener('click', handleConfirm);
        cancelBtn.addEventListener('click', handleCancel);
        closeBtn.addEventListener('click', handleCancel);

        showModal('confirmationModal');
    });
}

/**
 * Format file size for display
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// FILE MANAGEMENT
// ============================================

/**
 * Handle file selection from file dialog
 */
async function handleFileSelection(files) {
    // Extract file paths - for pywebview, File objects should have a path property
    // For drag-and-drop, we need to get the full path differently
    const filePaths = Array.from(files).map(file => {
        // If it's a string (from choose_files), use it directly
        if (typeof file === 'string') return file;
        // If it's an object with path, use that
        if (file.path) return file.path;
        // If it's a File object, try to get webkitRelativePath or show error
        if (file.webkitRelativePath) return file.webkitRelativePath;
        // Last resort: just the name (will fail on backend, but shows the issue)
        console.warn('File object missing path property:', file);
        return file.name;
    });

    const result = await callAPI('add_files', filePaths);

    if (result.success) {
        appState.selectedFiles = result.files;
        updateFileDisplay();
        updateStartButton();
    } else {
        showError('Error adding files: ' + (result.message || 'Unknown error'));
    }
}

/**
 * Update the file list display
 */
function updateFileDisplay() {
    const fileList = document.getElementById('fileList');
    const fileListContainer = document.getElementById('fileListContainer');
    const fileCount = document.getElementById('fileCount');
    const dropZone = document.getElementById('dropZone');
    
    if (appState.selectedFiles.length === 0) {
        // Show drop zone, hide file list
        dropZone.style.display = 'flex';
        fileListContainer.classList.add('hidden');
        fileCount.textContent = '';
    } else {
        // Hide drop zone, show file list
        dropZone.style.display = 'none';
        fileListContainer.classList.remove('hidden');
        
        // Update file list
        fileList.innerHTML = appState.selectedFiles.map((file, index) => {
            const fileName = file.split('/').pop();
            return `
                <li>
                    <span class="file-name" title="${escapeHtml(file)}">${escapeHtml(fileName)}</span>
                    <button class="file-remove-btn" onclick="removeFile(${index})" title="Remove file">×</button>
                </li>
            `;
        }).join('');
        
        // Update file count
        fileCount.innerHTML = `
            <strong>${appState.selectedFiles.length}</strong> file${appState.selectedFiles.length !== 1 ? 's' : ''} selected
        `;
    }
}

/**
 * Remove a file from the selection
 */
async function removeFile(index) {
    const file = appState.selectedFiles[index];
    const result = await callAPI('remove_file', file);
    
    if (result.success) {
        appState.selectedFiles = result.files;
        updateFileDisplay();
        updateStartButton();
    }
}

/**
 * Clear all files
 */
async function clearFiles() {
    if (appState.selectedFiles.length === 0) return;

    const confirmed = await showConfirmation('Clear Files', 'Are you sure you want to clear all selected files?');
    if (confirmed) {
        const result = await callAPI('clear_files');

        if (result.success) {
            appState.selectedFiles = [];
            updateFileDisplay();
            updateStartButton();
            showSuccess('All files cleared');
        } else {
            showError(result.message || 'Failed to clear files');
        }
    }
}

/**
 * Handle drag and drop
 */
function setupDragDrop() {
    const dropZone = document.getElementById('dropZone');
    const container = document.querySelector('.container');

    // Helper to add/remove visual state
    function setDragOver(active) {
        if (active) {
            dropZone.classList.add('drag-over');
            container.classList.add('drag-over');
        } else {
            dropZone.classList.remove('drag-over');
            container.classList.remove('drag-over');
        }
    }

    // Make the whole window respond to drag events
    window.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragOver(true);
    });

    window.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        // if leaving the window entirely, clear state
        if (e.clientX === 0 && e.clientY === 0) {
            setDragOver(false);
        } else {
            // small timeout to avoid flicker when moving between child elements
            setTimeout(() => setDragOver(false), 50);
        }
    });

    window.addEventListener('drop', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragOver(false);

        // Enhanced drop handler with detailed logging for debugging (e.g., Serato DJ)
        console.log('=== DROP EVENT RECEIVED ===');
        console.log('dataTransfer types:', e.dataTransfer?.types);
        console.log('dataTransfer items count:', e.dataTransfer?.items?.length);
        
        // Log all dataTransfer types and their contents
        if (e.dataTransfer?.types) {
            for (const type of e.dataTransfer.types) {
                try {
                    const data = e.dataTransfer.getData(type);
                    console.log(`Data type "${type}":`, data?.substring(0, 200));
                } catch (err) {
                    console.log(`Could not read type "${type}":`, err.message);
                }
            }
        }
        
        // Log files and their details
        if (e.dataTransfer?.files?.length) {
            console.log('Files dropped:', e.dataTransfer.files.length);
            for (let i = 0; i < e.dataTransfer.files.length; i++) {
                const file = e.dataTransfer.files[i];
                console.log(`File ${i}:`, {
                    name: file.name,
                    type: file.type,
                    size: file.size,
                    lastModified: file.lastModified,
                    path: file.path || 'N/A'
                });
            }
        }
        
        // Log items if available (provides more detailed info)
        if (e.dataTransfer?.items?.length) {
            console.log('DataTransfer items:');
            for (let i = 0; i < e.dataTransfer.items.length; i++) {
                const item = e.dataTransfer.items[i];
                console.log(`Item ${i}:`, {
                    kind: item.kind,
                    type: item.type,
                    webkitGetAsEntry: typeof item.webkitGetAsEntry
                });
                
                // Try to get string data for text items
                if (item.kind === 'string') {
                    item.getAsString((str) => {
                        console.log(`Item ${i} string content:`, str?.substring(0, 300));
                    });
                }
            }
        }

        // Let the Python backend handle full paths; trigger a backend drop handler
        // pywebview will receive the drop event and call back into JS via handleDroppedFiles
        try {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.handle_drop_event) {
                // Some pywebview builds use a custom handler - call it if available
                await window.pywebview.api.handle_drop_event();
            }
        } catch (err) {
            console.warn('Backend drop handler not available, relying on Python to call handleDroppedFiles:', err);
        }
    });

    // Keep original dropZone interactions for clicking to browse
    dropZone.addEventListener('click', async () => {
        try {
            const filePaths = await window.pywebview.api.choose_files();
            if (filePaths && filePaths.length > 0) {
                const result = await callAPI('add_files', filePaths);
                if (result.success) {
                    appState.selectedFiles = result.files;
                    updateFileDisplay();
                    updateStartButton();
                } else {
                    showError('Error adding files: ' + (result.message || 'Unknown error'));
                }
            }
        } catch (error) {
            console.error('Error selecting files:', error);
            showError('Error selecting files: ' + error.message);
        }
    });
}

// ============================================
// FIELD SELECTION
// ============================================

/**
 * Update selected fields based on checkbox state
 */
function updateSelectedFields() {
    appState.selectedFields = {
        artist: document.getElementById('artistCheckbox')?.checked || false,
        album: document.getElementById('albumCheckbox')?.checked || false,
        genre: document.getElementById('genreCheckbox')?.checked || false,
        year: document.getElementById('yearCheckbox')?.checked || false,
        subgenres: document.getElementById('subgenreCheckbox')?.checked || false,
        rating: document.getElementById('ratingCheckbox')?.checked || false
    };
    updateStartButton();
}

/**
 * Handle "Select All" checkbox
 */
function handleSelectAll(checked) {
    const checkboxes = ['artistCheckbox', 'albumCheckbox', 'genreCheckbox', 'yearCheckbox', 'subgenreCheckbox', 'ratingCheckbox'];
    checkboxes.forEach(id => {
        const checkbox = document.getElementById(id);
        if (checkbox) {
            checkbox.checked = checked;
        }
    });
    updateSelectedFields();
}

/**
 * Update start button state
 */
function updateStartButton() {
    const startBtn = document.getElementById('startProcessBtn');
    const hasFiles = appState.selectedFiles.length > 0;
    const hasFields = Object.values(appState.selectedFields).some(v => v);
    startBtn.disabled = !hasFiles || !hasFields || appState.processing;
}

// ============================================
// PROCESSING
// ============================================

/**
 * Start processing files
 */
async function startProcessing() {
    if (appState.processing) return;
    if (appState.selectedFiles.length === 0) {
        showError('Please select files to process');
        return;
    }

    const riddimModeActive = appState.riddimMode.isDancehall || appState.riddimMode.isReggae;
    const anyFieldSelected = riddimModeActive || Object.values(appState.selectedFields).some(v => v);

    if (!anyFieldSelected) {
        showError('Please select at least one field to update or enable Riddim mode');
        return;
    }

    appState.processing = true;
    appState.processingStats = {
        totalFiles: appState.selectedFiles.length,
        processed: 0,
        successful: 0,
        errors: 0
    };

    // Clear results table
    const tableBody = document.getElementById('resultsTableBody');
    tableBody.innerHTML = '<tr class="no-results"><td colspan="7" class="placeholder">Processing...</td></tr>';

    updateProcessingUI();

    // Pass both selected fields and riddim mode to backend
    const result = await callAPI('start_processing', appState.selectedFields, appState.riddimMode);

    if (!result.success) {
        appState.processing = false;
        updateProcessingUI();
        showError('Error starting processing: ' + (result.message || 'Unknown error'));
    }
}

/**
 * Cancel processing
 */
async function cancelProcessing() {
    const result = await callAPI('cancel_processing');
    
    if (result.success) {
        appState.processing = false;
        updateProcessingUI();
        showSuccess('Processing cancelled');
    } else {
        showError('Error cancelling processing');
    }
}

/**
 * Update processing UI elements
 */
function updateProcessingUI() {
    const startBtn = document.getElementById('startProcessBtn');
    const pauseBtn = document.getElementById('pauseProcessBtn');
    const cancelBtn = document.getElementById('cancelProcessBtn');
    
    startBtn.disabled = appState.processing || appState.selectedFiles.length === 0;
    pauseBtn.disabled = !appState.processing;
    cancelBtn.disabled = !appState.processing;
    
    // Update stats display
    document.getElementById('totalFilesCount').textContent = appState.processingStats.totalFiles;
    document.getElementById('processedCount').textContent = appState.processingStats.processed;
    document.getElementById('successCount').textContent = appState.processingStats.successful;
    document.getElementById('errorCount').textContent = appState.processingStats.errors;
}

/**
 * Update progress bar
 */
function updateProgress(percentage) {
    const fill = document.getElementById('progressFill');
    const percent = document.getElementById('progressPercent');
    fill.style.width = percentage + '%';
    percent.textContent = percentage + '%';
}

// ============================================
// CALLBACKS FROM PYTHON (via pywebview)
// ============================================

/**
 * Callback: Progress update
 */
window.onProgressUpdate = function(progress) {
    updateProgress(progress);
};

/**
 * Callback: Status update
 */
window.onStatusUpdate = function(status) {
    document.getElementById('statusText').textContent = status;
};

/**
 * Callback: Current file update
 */
window.onCurrentFileUpdate = function(filename) {
    document.getElementById('currentFileText').textContent = filename;
};

/**
 * Callback: File completed
 */
window.onFileCompleted = function(index, successful, errors) {
    appState.processingStats.processed = index;
    appState.processingStats.successful = successful;
    appState.processingStats.errors = errors;
    updateProcessingUI();
};

/**
 * Callback: Processing error
 */
window.onProcessingError = function(error) {
    console.error('Processing error:', error);
    showError(error);
};

/**
 * Callback: Processing finished
 */
window.onProcessingFinished = function(processedFilesMetadata) {
    appState.processing = false;
    updateProcessingUI();

    // Parse metadata if it's a string (from JSON)
    const filesData = typeof processedFilesMetadata === 'string' ?
        JSON.parse(processedFilesMetadata) : (processedFilesMetadata || []);

    // Update results table
    const tableBody = document.getElementById('resultsTableBody');
    const { successful, errors } = appState.processingStats;

    console.log('DEBUG: Processing finished with', filesData);

    if (filesData && filesData.length > 0) {
        tableBody.innerHTML = filesData.map(file => {
            const statusClass = file.success ? 'status-success' : 'status-error';
            const statusText = file.success ? 'Success' : 'Error';
            const metadata = file.metadata || {};
            const filePath = file.file_path || '';

            return `
                <tr data-file-path="${escapeHtml(filePath)}">
                    <td title="${escapeHtml(filePath)}">${escapeHtml(file.filename)}</td>
                    <td class="status-cell ${statusClass}">${statusText}</td>
                    <td class="editable-cell" data-field="artist">
                        <span contenteditable="true" onblur="handleCellEdit(this)" onkeydown="handleCellKeydown(this, event)">${escapeHtml(metadata.artist || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="album">
                        <span contenteditable="true" onblur="handleCellEdit(this)" onkeydown="handleCellKeydown(this, event)">${escapeHtml(metadata.album || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="genre">
                        <span contenteditable="true" onblur="handleCellEdit(this)" onkeydown="handleCellKeydown(this, event)">${escapeHtml(metadata.genre || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="year">
                        <span contenteditable="true" onblur="handleCellEdit(this)" onkeydown="handleCellKeydown(this, event)">${escapeHtml(metadata.year || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="rating">
                        <span contenteditable="true" onblur="handleCellEdit(this)" onkeydown="handleCellKeydown(this, event)">${escapeHtml(metadata.rating || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="comments">
                        <span contenteditable="true" onblur="handleCellEdit(this)" onkeydown="handleCellKeydown(this, event)">${escapeHtml(metadata.comments || metadata.subgenres || '-')}</span>
                    </td>
                </tr>
            `;
        }).join('');
    } else {
        console.log('DEBUG: No files data, showing placeholder');
        tableBody.innerHTML = '<tr class="no-results"><td colspan="8" class="placeholder">No results to display</td></tr>';
    }

    showSuccess(`Processing completed! (${successful} successful, ${errors} errors)`);
};

/**
 * Handle cell content edit
 */
async function handleCellEdit(element) {
    const td = element.parentElement;
    const tr = td.parentElement;
    const filePath = tr.dataset.filePath;
    const field = td.dataset.field;
    const newValue = element.textContent.trim();
    
    // Skip if no change or placeholder
    if (newValue === '-' || !filePath) return;
    
    // Save to backend
    const result = await saveEditedRow(filePath, field, newValue);
    
    if (result.success) {
        td.classList.add('save-success');
        setTimeout(() => td.classList.remove('save-success'), 1000);
    } else {
        td.classList.add('save-error');
        setTimeout(() => td.classList.remove('save-error'), 1000);
        showNotification(`Failed to save ${field}: ${result.message}`, 'error');
    }
}

/**
 * Handle keydown in editable cell (Enter to blur)
 */
function handleCellKeydown(element, event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        element.blur();
    }
}

/**
 * Save edited metadata for a single field
 */
async function saveEditedRow(filePath, field, newValue) {
    return await callAPI('save_edited_metadata', filePath, field, newValue);
}

/**
 * Callback: Manual review needed when album/year metadata differs between sources
 */
window.onReviewNeeded = function(filePath, candidates, bestMatch) {
    console.log('Review request received for:', filePath);
    
    // Add to queue
    appState.reviewMode.queue.push({
        filePath: filePath,
        candidates: candidates || [],
        bestMatch: bestMatch || null
    });

    // If no review is active, start processing the queue
    if (!appState.reviewMode.active) {
        processNextReview();
    } else {
        console.log('Review already active, added to queue. Queue length:', appState.reviewMode.queue.length);
        // Update notification
        showNotification(`Additional file needs review: ${appState.reviewMode.queue.length} pending`, 'info');
    }
};

// ============================================
// MODALS - SETTINGS
// ============================================

/**
 * Initialize settings modal
 */
async function initSettingsModal() {
    const settingsBtn = document.getElementById('settingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const closeSettingsBtn = document.getElementById('closeSettingsModal');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const resetSettingsBtn = document.getElementById('resetSettingsBtn');
    const browseSeratoBtn = document.getElementById('browseSeratoBtn');
    const clearSeratoBtn = document.getElementById('clearSeratoBtn');
    const seratoPathStatus = document.getElementById('seratoPathStatus');
    
    // Load current settings
    const settings = await callAPI('get_settings');
    if (settings.success) {
        document.getElementById('metadataSourceSelect').value = settings.metadata_source;
        document.getElementById('maxFilenameInput').value = settings.max_filename_length;
        document.getElementById('enableLLMCheckbox').checked = settings.use_ai_genre_detection;
        if (settings.serato_library_path) {
            document.getElementById('seratoLibraryInput').value = settings.serato_library_path;
            seratoPathStatus.textContent = '✓ Path set';
            seratoPathStatus.style.color = '#27ae60';
        }
    }
    
    settingsBtn.addEventListener('click', () => showModal('settingsModal'));
    closeSettingsBtn.addEventListener('click', () => hideModal('settingsModal'));
    
    // Serato library path handling
    browseSeratoBtn.addEventListener('click', async () => {
        try {
            // Use the new choose_folder API to get a directory path
            const result = await window.pywebview.api.choose_folder();
            if (result) {
                document.getElementById('seratoLibraryInput').value = result;
                seratoPathStatus.textContent = '✓ Path selected';
                seratoPathStatus.style.color = '#27ae60';
            }
        } catch (error) {
            console.error('Error browsing for Serato path:', error);
            showError('Error selecting folder: ' + error.message);
        }
    });
    
    clearSeratoBtn.addEventListener('click', async () => {
        document.getElementById('seratoLibraryInput').value = '';
        await callAPI('set_serato_library_path', '');
        seratoPathStatus.textContent = 'Path cleared';
        seratoPathStatus.style.color = '#999';
        showSuccess('Serato library path cleared');
    });
    
    saveSettingsBtn.addEventListener('click', async () => {
        const seratoPath = document.getElementById('seratoLibraryInput').value.trim();
        if (seratoPath) {
            const result = await callAPI('set_serato_library_path', seratoPath);
            if (!result.success) {
                showError('Invalid Serato path: ' + result.message);
                return;
            }
            seratoPathStatus.textContent = '✓ ' + result.message;
            seratoPathStatus.style.color = '#27ae60';
        }
        
        // Serato path is automatically saved when set via set_serato_library_path
        // Other settings are currently read-only placeholders for future functionality
        showSuccess('Settings saved successfully');
        hideModal('settingsModal');
    });
    
    resetSettingsBtn.addEventListener('click', () => {
        document.getElementById('metadataSourceSelect').value = 'auto';
        document.getElementById('maxFilenameInput').value = 200;
        document.getElementById('enableLLMCheckbox').checked = true;
        document.getElementById('seratoLibraryInput').value = '';
        seratoPathStatus.textContent = '';
    });
}

// ============================================
// MODALS - LICENSE
// ============================================

/**
 * Initialize license modal
 */
async function initLicenseModal() {
    const licenseBtn = document.getElementById('licenseBtn');
    const licenseBtnAction = document.getElementById('licenseBtnAction');
    const licenseModal = document.getElementById('licenseModal');
    const closeLicenseBtn = document.getElementById('closeLicenseModal');
    const activateLicenseBtn = document.getElementById('activateLicenseBtn');
    const removeLicenseBtn = document.getElementById('removeLicenseBtn');
    
    // Update license status
    async function updateLicenseDisplay() {
        const status = await callAPI('get_license_status');
        if (status.success) {
            appState.licenseStatus = status;

            // Update status badge
            const statusBadge = document.getElementById('licenseStatusBadge');
            if (statusBadge) {
                if (status.is_active) {
                    statusBadge.textContent = 'Active';
                    statusBadge.className = 'status-badge active';
                } else {
                    statusBadge.textContent = 'Trial';
                    statusBadge.className = 'status-badge trial';
                }
            }

            // Update license type
            const typeInfo = document.getElementById('licenseTypeInfo');
            if (typeInfo) {
                typeInfo.textContent = status.is_active ? 'Full License' : 'Free Trial';
            }

            // Update license limit display
            const limitInfo = document.getElementById('licenseLimitInfo');
            if (limitInfo) {
                if (status.is_active) {
                    limitInfo.textContent = 'Unlimited';
                } else {
                    limitInfo.textContent = status.daily_limit ? `${status.daily_limit} files` : '10 files';
                }
            }

            // Update remaining files
            const remainingInfo = document.getElementById('remainingFilesInfo');
            const remainingRow = document.getElementById('remainingFilesRow');
            if (remainingInfo && remainingRow) {
                if (status.is_active) {
                    remainingRow.style.display = 'none';
                } else {
                    remainingRow.style.display = 'flex';
                    const limit = status.daily_limit || 10;
                    const remaining = Math.max(0, limit - (status.files_processed || 0));
                    remainingInfo.textContent = `${remaining} files`;
                }
            }

            // Update banner
            const banner = document.getElementById('licenseBanner');
            if (!status.is_active) {
                banner.classList.remove('hidden');
                const limit = status.daily_limit || 10;
                const remaining = Math.max(0, limit - (status.files_processed || 0));
                document.getElementById('licenseMessage').textContent =
                    `Free trial - ${remaining} of ${limit} files remaining today. Activate a license for unlimited access.`;
            } else {
                banner.classList.add('hidden');
            }
        }
    }
    
    // Header license button
    if (licenseBtn) {
        licenseBtn.addEventListener('click', () => {
            showModal('licenseModal');
            updateLicenseDisplay();
        });
    }

    // Banner license button
    if (licenseBtnAction) {
        licenseBtnAction.addEventListener('click', () => {
            showModal('licenseModal');
            updateLicenseDisplay();
        });
    }

    closeLicenseBtn.addEventListener('click', () => hideModal('licenseModal'));
    
    activateLicenseBtn.addEventListener('click', async () => {
        const key = document.getElementById('licenseKeyInput').value.trim();
        if (!key) {
            showError('Please enter a license key');
            return;
        }
        
        const result = await callAPI('activate_license', key);
        if (result.success) {
            showSuccess('License activated successfully');
            document.getElementById('licenseKeyInput').value = '';
            updateLicenseDisplay();
        } else {
            showError(result.message || 'Failed to activate license');
        }
    });
    
    removeLicenseBtn.addEventListener('click', async () => {
        const confirmed = await showConfirmation(
            'Remove License',
            'Are you sure you want to remove the license?'
        );
        if (confirmed) {
            const result = await callAPI('remove_license');
            if (result.success) {
                showSuccess('License removed');
                updateLicenseDisplay();
            } else {
                showError('Failed to remove license');
            }
        }
    });
    
    // Initial display
    updateLicenseDisplay();
}

// ============================================
// MODALS - HELP
// ============================================

/**
 * Initialize help modal
 */
function initHelpModal() {
    const helpBtn = document.getElementById('helpBtn');
    const closeHelpBtn = document.getElementById('closeHelpModal');
    
    helpBtn.addEventListener('click', () => showModal('helpModal'));
    closeHelpBtn.addEventListener('click', () => hideModal('helpModal'));
}

// ============================================
// ERROR AND SUCCESS MESSAGES
// ============================================

/**
 * Show error modal
 */
function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    showModal('errorModal');
}

/**
 * Show success modal
 */
function showSuccess(message) {
    document.getElementById('successMessage').textContent = message;
    showModal('successModal');
}

/**
 * Initialize error and success modals
 */
function initMessageModals() {
    const closeErrorBtn = document.getElementById('closeErrorBtn');
    const closeErrorModal = document.getElementById('closeErrorModal');
    const closeSuccessBtn = document.getElementById('closeSuccessBtn');
    const closeSuccessModal = document.getElementById('closeSuccessModal');
    
    closeErrorBtn.addEventListener('click', () => hideModal('errorModal'));
    closeErrorModal.addEventListener('click', () => hideModal('errorModal'));
    closeSuccessBtn.addEventListener('click', () => hideModal('successModal'));
    closeSuccessModal.addEventListener('click', () => hideModal('successModal'));
}

/**
 * Close modal when clicking overlay
 */
function setupModalOverlay() {
    const overlay = document.getElementById('modalOverlay');
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            // Close all modals
            document.querySelectorAll('.modal.active').forEach(modal => {
                modal.classList.remove('active');
            });
            overlay.classList.remove('active');
            document.body.style.overflow = 'auto';
            // Force reset blur and display if stuck
            overlay.style.display = '';
            overlay.style.zIndex = '';
            
            // If it was the review modal being closed via overlay, we might need to reset state
            if (appState.reviewMode.active) {
                closeCandidateReviewModal();
            }
        }
    });
}

// ============================================
// MODALS - CANDIDATE REVIEW (for metadata conflicts)
// ============================================

/**
 * Initialize candidate review modal
 */
function initCandidateReviewModal() {
    const closeBtn = document.getElementById('closeCandidateReviewModal');
    const skipBtn = document.getElementById('skipFileBtn');

    if (closeBtn) {
        closeBtn.addEventListener('click', closeCandidateReviewModal);
    }
    if (skipBtn) {
        skipBtn.addEventListener('click', skipCurrentFile);
    }
}

/**
 * Show candidate review modal with side-by-side candidates
 */
function showCandidateReviewModal() {
    const modal = document.getElementById('candidateReviewModal');
    if (!modal) {
        console.error('Candidate review modal not found in HTML');
        return;
    }

    const { candidates, bestMatch } = appState.reviewMode;
    const tableBody = document.getElementById('candidatesBody');

    if (!tableBody) {
        console.error('Candidates table body not found');
        return;
    }

    // Clear previous rows
    tableBody.innerHTML = '';

    // Add candidates as rows
    if (candidates && candidates.length > 0) {
        candidates.forEach((candidate, index) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="radio" name="candidate" value="${index}" onchange="selectCandidate(${index})"></td>
                <td>${escapeHtml(candidate.title || '-')}</td>
                <td>${escapeHtml(candidate.artist || '-')}</td>
                <td>${escapeHtml(candidate.album || '-')}</td>
                <td>${escapeHtml(candidate.year || '-')}</td>
                <td>${escapeHtml(candidate.source || 'Unknown')}</td>
            `;
            tableBody.appendChild(row);
        });
    } else {
        tableBody.innerHTML = '<tr><td colspan="6">No candidates available</td></tr>';
    }

    // Pre-fill manual metadata form with title and artist from best match
    if (bestMatch) {
        document.getElementById('manualTitle').value = bestMatch.title || '';
        document.getElementById('manualArtist').value = bestMatch.artist || '';
        // Clear other fields
        document.getElementById('manualAlbum').value = '';
        document.getElementById('manualYear').value = '';
        document.getElementById('manualGenre').value = '';
        document.getElementById('manualSubgenres').value = '';
    }

    // Hide manual metadata form initially
    document.getElementById('manualMetadataForm').classList.add('hidden');
    document.getElementById('editFields').classList.add('hidden');

    // Show modal
    showModal('candidateReviewModal');
}

/**
 * Toggle between candidates table and manual metadata form
 */
function toggleManualMetadataForm() {
    const manualForm = document.getElementById('manualMetadataForm');
    const candidatesTable = document.querySelector('#candidateReviewModal table');

    if (manualForm.classList.contains('hidden')) {
        // Show manual form, hide table
        manualForm.classList.remove('hidden');
        if (candidatesTable) candidatesTable.style.display = 'none';
        document.getElementById('editFields').classList.add('hidden');
    } else {
        // Hide manual form, show table
        manualForm.classList.add('hidden');
        if (candidatesTable) candidatesTable.style.display = 'table';
    }
}

/**
 * Handle candidate selection
 */
function selectCandidate(index) {
    appState.reviewMode.selectedIndex = index;
    const candidates = appState.reviewMode.candidates;

    if (index >= 0 && index < candidates.length) {
        const selected = candidates[index];
        console.log('Selected candidate:', selected);

        // Populate edit fields with selected candidate's data
        const editFields = {
            title: document.getElementById('editTitle'),
            artist: document.getElementById('editArtist'),
            album: document.getElementById('editAlbum'),
            year: document.getElementById('editYear')
        };

        for (const [key, field] of Object.entries(editFields)) {
            if (field) {
                field.value = selected[key] || '';
            }
        }

        // Show edit fields
        const editDiv = document.getElementById('editFields');
        if (editDiv) {
            editDiv.classList.remove('hidden');
        }
    }
}

/**
 * Submit candidate selection (either selected, manually edited, or manually added)
 */
async function submitCandidateSelection() {
    let selectedMetadata = {};

    // Check if manual metadata form is active
    const manualForm = document.getElementById('manualMetadataForm');
    if (!manualForm.classList.contains('hidden')) {
        // Using manually entered metadata
        const manualTitle = document.getElementById('manualTitle')?.value || '';
        const manualArtist = document.getElementById('manualArtist')?.value || '';
        const manualAlbum = document.getElementById('manualAlbum')?.value || '';
        const manualYear = document.getElementById('manualYear')?.value || '';
        const manualGenre = document.getElementById('manualGenre')?.value || '';
        const manualSubgenres = document.getElementById('manualSubgenres')?.value || '';

        selectedMetadata = {
            title: manualTitle,
            artist: manualArtist,
            album: manualAlbum,
            year: manualYear,
            genre: manualGenre,
            subgenres: manualSubgenres,
            comments: manualSubgenres  // Also set comments for backward compatibility
        };

        console.log('Submitting manually entered metadata:', selectedMetadata);
    } else {
        // Using candidate selection or edited candidate
        const editTitle = document.getElementById('editTitle')?.value || '';
        const editArtist = document.getElementById('editArtist')?.value || '';
        const editAlbum = document.getElementById('editAlbum')?.value || '';
        const editYear = document.getElementById('editYear')?.value || '';

        // Start with selected candidate as base
        if (appState.reviewMode.selectedIndex >= 0 && appState.reviewMode.selectedIndex < appState.reviewMode.candidates.length) {
            selectedMetadata = { ...appState.reviewMode.candidates[appState.reviewMode.selectedIndex] };
        }

        // Override with any manual edits
        if (editTitle) selectedMetadata.title = editTitle;
        if (editArtist) selectedMetadata.artist = editArtist;
        if (editAlbum) selectedMetadata.album = editAlbum;
        if (editYear) selectedMetadata.year = editYear;

        console.log('Submitting candidate:', selectedMetadata);
    }

    // Send selection back to backend
    const result = await callAPI('set_selected_candidate', appState.reviewMode.currentFile, selectedMetadata);

    if (result.success) {
        console.log('Selection submitted successfully');
    } else {
        console.error('Error submitting selection:', result.message);
    }

    closeCandidateReviewModal();
}

/**
 * Skip the current file and use best match as-is
 */
async function skipCurrentFile() {
    console.log('Skipping review for file:', appState.reviewMode.currentFile);

    // Use best match (no modifications)
    const result = await callAPI('set_selected_candidate', appState.reviewMode.currentFile, appState.reviewMode.bestMatch);

    if (result.success) {
        console.log('File skipped, using best match');
    } else {
        console.error('Error skipping file:', result.message);
    }

    closeCandidateReviewModal();
}

/**
 * Close candidate review modal
 */
function closeCandidateReviewModal() {
    hideModal('candidateReviewModal');
    // Reset current review state but PRESERVE queue
    appState.reviewMode.active = false;
    appState.reviewMode.currentFile = null;
    appState.reviewMode.candidates = [];
    appState.reviewMode.bestMatch = null;
    appState.reviewMode.selectedIndex = -1;
}

// ============================================
// RIDDIM MODE UI
// ============================================

/**
 * Update UI when Riddim Mode toggles change
 */
function updateRiddimModeUI() {
    const riddimMode = appState.riddimMode.isDancehall || appState.riddimMode.isReggae;
    const otherCheckboxes = ['artistCheckbox', 'albumCheckbox', 'genreCheckbox', 'yearCheckbox', 'subgenreCheckbox', 'ratingCheckbox'];

    // Disable other search-related checkboxes when riddim mode is active
    otherCheckboxes.forEach(id => {
        const checkbox = document.getElementById(id);
        if (checkbox) {
            checkbox.disabled = riddimMode;
            if (riddimMode) {
                checkbox.checked = false;
            }
        }
    });

    // Update visual feedback
    const riddimSection = document.querySelector('[style*="border-left: 3px solid #ff6b35"]');
    if (riddimSection) {
        riddimSection.style.opacity = riddimMode ? '1' : '0.7';
        riddimSection.style.backgroundColor = riddimMode ? '#2a3a2a' : '#2a2a2a';
    }
}

// ============================================
// CHECKBOX SETUP
// ============================================

/**
 * Setup checkbox listeners
 */
function setupCheckboxes() {
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    const individualCheckboxes = ['artistCheckbox', 'albumCheckbox', 'genreCheckbox', 'yearCheckbox', 'subgenreCheckbox', 'ratingCheckbox'];

    selectAllCheckbox.addEventListener('change', (e) => {
        handleSelectAll(e.target.checked);
    });

    individualCheckboxes.forEach(id => {
        const checkbox = document.getElementById(id);
        if (checkbox) {
            checkbox.addEventListener('change', () => {
                updateSelectedFields();
                // Update select all checkbox state
                const allChecked = individualCheckboxes.every(checkId => {
                    const cb = document.getElementById(checkId);
                    return cb ? cb.checked : false;
                });
                selectAllCheckbox.checked = allChecked;
            });
        }
    });

    // Setup Riddim Mode toggles
    const isDancehallCheckbox = document.getElementById('isDancehallCheckbox');
    const isReggaeCheckbox = document.getElementById('isReggaeCheckbox');

    if (isDancehallCheckbox) {
        isDancehallCheckbox.addEventListener('change', (e) => {
            appState.riddimMode.isDancehall = e.target.checked;
            // If dancehall is enabled, disable reggae (mutually exclusive)
            if (e.target.checked && isReggaeCheckbox) {
                isReggaeCheckbox.checked = false;
                appState.riddimMode.isReggae = false;
            }
            updateRiddimModeUI();
        });
    }

    if (isReggaeCheckbox) {
        isReggaeCheckbox.addEventListener('change', (e) => {
            appState.riddimMode.isReggae = e.target.checked;
            // If reggae is enabled, disable dancehall (mutually exclusive)
            if (e.target.checked && isDancehallCheckbox) {
                isDancehallCheckbox.checked = false;
                appState.riddimMode.isDancehall = false;
            }
            updateRiddimModeUI();
        });
    }
}

// ============================================
// BUTTON SETUP
// ============================================

/**
 * Setup button event listeners
 */
function setupButtons() {
    document.getElementById('addFilesBtn').addEventListener('click', async () => {
        try {
            const files = await window.pywebview.api.choose_files();
            if (files && files.length > 0) {
                await handleFileSelection(files.map(f => ({ name: f, path: f })));
            }
        } catch (error) {
            console.error('Error selecting files:', error);
        }
    });

    // Toggle always-on-top pin
    const pinBtn = document.getElementById('alwaysOnTopBtn');
    if (pinBtn) {
        pinBtn.addEventListener('click', async () => {
            try {
                const result = await callAPI('toggle_always_on_top');
                if (result && result.success) {
                    pinBtn.style.color = result.always_on_top ? '#3b82f6' : '';
                    pinBtn.title = result.always_on_top ? 'Pinned (Always on Top)' : 'Always on Top (Pin)';
                }
            } catch (e) {
                console.warn('Could not toggle always-on-top:', e);
            }
        });
    }
    
     document.getElementById('clearFilesBtn').addEventListener('click', clearFiles);
     
     // Clear cache button
     const clearCacheBtn = document.getElementById('clearCacheBtn');
     if (clearCacheBtn) {
         clearCacheBtn.addEventListener('click', async () => {
             const confirmed = await showConfirmation(
                 'Clear Cache',
                 'Clear all cached metadata? This action cannot be undone.'
             );
             if (confirmed) {
                 try {
                     const result = await callAPI('clear_cache', 'all');
                     if (result.success) {
                         showSuccess(result.message);
                     } else {
                         showError(result.message || 'Failed to clear cache');
                     }
                 } catch (error) {
                     console.error('Error clearing cache:', error);
                     showError('Error clearing cache: ' + error.message);
                 }
             }
         });
     }
     
     document.getElementById('startProcessBtn').addEventListener('click', startProcessing);
     document.getElementById('pauseProcessBtn').addEventListener('click', () => {
         // Pause functionality not yet implemented
         console.log('Pause not yet implemented');
     });
     document.getElementById('cancelProcessBtn').addEventListener('click', cancelProcessing);
 }

// ============================================
// DRAG-AND-DROP CALLBACK
// ============================================

/**
 * Handle files dropped from Python backend
 * Called by Python when drag-and-drop occurs
 */
window.handleDroppedFiles = function(result) {
    if (result && result.success) {
        appState.selectedFiles = result.files;
        updateFileDisplay();
        updateStartButton();
    } else {
        showError('Error adding dropped files: ' + (result.message || 'Unknown error'));
    }
};

// ============================================
// INITIALIZATION
// ============================================

/**
 * Initialize the application
 */
async function initializeApp() {
    console.log('Initializing Metadata Updater UI...');
    
    // Wait for pywebview to be ready
    window.addEventListener('pywebviewready', async () => {
        console.log('pywebview ready');
        
        // Initialize API
        const initResult = await callAPI('initialize_app');
        if (!initResult.success) {
            showError('Failed to initialize application: ' + initResult.message);
            return;
        }
        
        // Setup UI components
        setupDragDrop();
        setupCheckboxes();
        setupButtons();
        setupModalOverlay();
        initMessageModals();
        initHelpModal();
        initCandidateReviewModal();
        await initSettingsModal();
        await initLicenseModal();
        
        // Initial display update
        updateFileDisplay();
        updateProcessingUI();
        
        console.log('App initialized successfully');
    });
}

// Start initialization when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}
