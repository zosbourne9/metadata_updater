/**
 * Python API bridge via pywebview
 */

/**
 * Call Python API method via pywebview
 */
export async function callAPI(method, ...args) {
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
