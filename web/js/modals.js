/**
 * Modal dialogs, message modals, and overlay handling
 */

import { appState } from './state.js';
import { showNotification } from './utils.js';
import { processNextReview, closeCandidateReviewModal } from './review.js';

/**
 * Show modal dialog
 */
export function showModal(modalId) {
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
export function hideModal(modalId) {
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
 * Show confirmation dialog
 * Returns a promise that resolves to true if confirmed, false if cancelled
 */
export function showConfirmation(title, message) {
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
 * Show error modal
 */
export function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    showModal('errorModal');
}

/**
 * Show success modal
 */
export function showSuccess(message) {
    document.getElementById('successMessage').textContent = message;
    showModal('successModal');
}

/**
 * Initialize error and success modals
 */
export function initMessageModals() {
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
export function setupModalOverlay() {
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
