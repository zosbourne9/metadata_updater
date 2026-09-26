/**
 * Metadata field selection, checkboxes, and Riddim Mode UI
 */

import { appState } from './state.js';

/**
 * Update selected fields based on checkbox state
 */
export function updateSelectedFields() {
    appState.selectedFields = {
        artist: document.getElementById('artistCheckbox')?.checked || false,
        album: document.getElementById('albumCheckbox')?.checked || false,
        genre: document.getElementById('genreCheckbox')?.checked || false,
        year: document.getElementById('yearCheckbox')?.checked || false,
        subgenres: document.getElementById('subgenreCheckbox')?.checked || false,
        rating: document.getElementById('ratingCheckbox')?.checked || false,
        rename: document.getElementById('renameCheckbox')?.checked || false
    };
    updateStartButton();
}

/**
 * Handle "Select All" checkbox
 */
export function handleSelectAll(checked) {
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
export function updateStartButton() {
    const startBtn = document.getElementById('startProcessBtn');
    const hasFiles = appState.selectedFiles.length > 0;
    const hasFields = Object.values(appState.selectedFields).some(v => v);
    startBtn.disabled = !hasFiles || !hasFields || appState.processing;
}

/**
 * Update UI when Riddim Mode toggles change
 */
export function updateRiddimModeUI() {
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

/**
 * Setup checkbox listeners
 */
export function setupCheckboxes() {
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

    // Rename toggle is an action (not a metadata field), so it has its own listener
    const renameCheckbox = document.getElementById('renameCheckbox');
    if (renameCheckbox) {
        renameCheckbox.addEventListener('change', () => {
            updateSelectedFields();
        });
    }

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
