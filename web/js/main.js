/**
 * Metadata Updater - application bootstrap
 */

import { callAPI } from './api.js';
import { showError } from './modals.js';
import { setupDragDrop, updateFileDisplay } from './files.js';
import { setupCheckboxes } from './fields.js';
import { setupButtons } from './buttons.js';
import { updateProcessingUI } from './processing.js';
import { setupModalOverlay, initMessageModals } from './modals.js';
import { initSettingsModal, initHelpModal } from './settings.js';
import { initCandidateReviewModal } from './review.js';

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
