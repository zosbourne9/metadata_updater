/**
 * File selection, drag-and-drop, and file list display
 */

import { appState } from './state.js';
import { callAPI } from './api.js';
import { showNotification, escapeHtml } from './utils.js';
import { showConfirmation, showError, showSuccess } from './modals.js';
import { updateStartButton } from './fields.js';

/**
 * Handle file selection from file dialog
 */
export async function handleFileSelection(files) {
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
export function updateFileDisplay() {
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
                    <button class="file-remove-btn" onclick="window.removeFile(${index})" title="Remove file">×</button>
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
 * Assigned to window for use by inline onclick handlers
 */
export async function removeFile(index) {
    const file = appState.selectedFiles[index];
    const result = await callAPI('remove_file', file);

    if (result.success) {
        appState.selectedFiles = result.files;
        updateFileDisplay();
        updateStartButton();
    }
}
window.removeFile = removeFile;

/**
 * Clear all files
 */
export async function clearFiles() {
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
export function setupDragDrop() {
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
