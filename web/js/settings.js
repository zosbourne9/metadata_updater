/**
 * Settings and Help modals
 */

import { callAPI } from './api.js';
import { showModal, hideModal, showError, showSuccess } from './modals.js';

/**
 * Initialize settings modal
 */
export async function initSettingsModal() {
    const settingsBtn = document.getElementById('settingsBtn');
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

/**
 * Initialize help modal
 */
export function initHelpModal() {
    const helpBtn = document.getElementById('helpBtn');
    const closeHelpBtn = document.getElementById('closeHelpModal');

    helpBtn.addEventListener('click', () => showModal('helpModal'));
    closeHelpBtn.addEventListener('click', () => hideModal('helpModal'));
}
