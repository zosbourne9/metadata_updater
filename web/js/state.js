/**
 * Global application state
 */

export const appState = {
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
        rating: false,
        rename: false
    },
    riddimMode: {
        isDancehall: false,
        isReggae: false
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
