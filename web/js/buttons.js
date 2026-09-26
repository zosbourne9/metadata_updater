/**
 * Header/toolbar buttons and Python drop callback
 */

import { appState } from './state.js';
import { callAPI } from './api.js';
import { showConfirmation, showError, showSuccess } from './modals.js';
import { handleFileSelection, clearFiles, updateFileDisplay } from './files.js';
import { updateStartButton } from './fields.js';
import { startProcessing, cancelProcessing } from './processing.js';

/**
 * Setup button event listeners
 */
export function setupButtons() {
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

/**
 * Handle files dropped from Python backend
 * Called by Python when drag-and-drop occurs
 */
window.handleDroppedFiles = function (result) {
    if (result && result.success) {
        appState.selectedFiles = result.files;
        updateFileDisplay();
        updateStartButton();
    } else {
        showError('Error adding dropped files: ' + (result.message || 'Unknown error'));
    }
};
