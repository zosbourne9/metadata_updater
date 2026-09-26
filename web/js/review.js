/**
 * Candidate review modal (metadata conflicts)
 */

import { appState } from './state.js';
import { callAPI } from './api.js';
import { escapeHtml, showNotification } from './utils.js';
import { showModal, hideModal } from './modals.js';

/**
 * Process the next review in the queue
 */
export function processNextReview() {
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
 * Callback: Manual review needed when album/year metadata differs between sources
 */
window.onReviewNeeded = function (filePath, candidates, bestMatch) {
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

/**
 * Initialize candidate review modal
 */
export function initCandidateReviewModal() {
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
export function showCandidateReviewModal() {
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
                <td><input type="radio" name="candidate" value="${index}" onchange="window.selectCandidate(${index})"></td>
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
export function toggleManualMetadataForm() {
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
 * Assigned to window for use by inline onchange handlers
 */
export function selectCandidate(index) {
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
window.selectCandidate = selectCandidate;

/**
 * Submit candidate selection (either selected, manually edited, or manually added)
 */
export async function submitCandidateSelection() {
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
export async function skipCurrentFile() {
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
export function closeCandidateReviewModal() {
    hideModal('candidateReviewModal');
    // Reset current review state but PRESERVE queue
    appState.reviewMode.active = false;
    appState.reviewMode.currentFile = null;
    appState.reviewMode.candidates = [];
    appState.reviewMode.bestMatch = null;
    appState.reviewMode.selectedIndex = -1;
}

// Static inline handlers in index.html reference these as globals
window.toggleManualMetadataForm = toggleManualMetadataForm;
window.submitCandidateSelection = submitCandidateSelection;
