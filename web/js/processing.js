/**
 * Processing flow, results table, and Python -> JS callbacks
 */

import { appState } from './state.js';
import { callAPI } from './api.js';
import { escapeHtml, showNotification } from './utils.js';
import { showError, showSuccess } from './modals.js';
import { updateStartButton } from './fields.js';

/**
 * Start processing files
 */
export async function startProcessing() {
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
export async function cancelProcessing() {
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
export function updateProcessingUI() {
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
export function updateProgress(percentage) {
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
window.onProgressUpdate = function (progress) {
    updateProgress(progress);
};

/**
 * Callback: Status update
 */
window.onStatusUpdate = function (status) {
    document.getElementById('statusText').textContent = status;
};

/**
 * Callback: Current file update
 */
window.onCurrentFileUpdate = function (filename) {
    document.getElementById('currentFileText').textContent = filename;
};

/**
 * Callback: File completed
 */
window.onFileCompleted = function (index, successful, errors) {
    appState.processingStats.processed = index;
    appState.processingStats.successful = successful;
    appState.processingStats.errors = errors;
    updateProcessingUI();
};

/**
 * Callback: Processing error
 */
window.onProcessingError = function (error) {
    console.error('Processing error:', error);
    showError(error);
};

/**
 * Callback: Processing finished
 */
window.onProcessingFinished = function (processedFilesMetadata) {
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
                        <span contenteditable="true" onblur="window.handleCellEdit(this)" onkeydown="window.handleCellKeydown(this, event)">${escapeHtml(metadata.artist || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="album">
                        <span contenteditable="true" onblur="window.handleCellEdit(this)" onkeydown="window.handleCellKeydown(this, event)">${escapeHtml(metadata.album || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="genre">
                        <span contenteditable="true" onblur="window.handleCellEdit(this)" onkeydown="window.handleCellKeydown(this, event)">${escapeHtml(metadata.genre || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="year">
                        <span contenteditable="true" onblur="window.handleCellEdit(this)" onkeydown="window.handleCellKeydown(this, event)">${escapeHtml(metadata.year || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="rating">
                        <span contenteditable="true" onblur="window.handleCellEdit(this)" onkeydown="window.handleCellKeydown(this, event)">${escapeHtml(metadata.rating || '-')}</span>
                    </td>
                    <td class="editable-cell" data-field="comments">
                        <span contenteditable="true" onblur="window.handleCellEdit(this)" onkeydown="window.handleCellKeydown(this, event)">${escapeHtml(metadata.comments || metadata.subgenres || '-')}</span>
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
 * Assigned to window for use by inline onblur handlers
 */
export async function handleCellEdit(element) {
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
window.handleCellEdit = handleCellEdit;

/**
 * Handle keydown in editable cell (Enter to blur)
 * Assigned to window for use by inline onkeydown handlers
 */
export function handleCellKeydown(element, event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        element.blur();
    }
}
window.handleCellKeydown = handleCellKeydown;

/**
 * Save edited metadata for a single field
 */
export async function saveEditedRow(filePath, field, newValue) {
    return await callAPI('save_edited_metadata', filePath, field, newValue);
}
