from typing import List, Optional, Callable

class DialogHandler:
    """Callback-based dialog handler for showing dialogs across the application.
    
    Replaces PyQt6's signal/slot mechanism with simple Python callbacks.
    Each dialog type (features, error, warning) can have a custom callback,
    or falls back to print() for non-GUI contexts.
    """
    
    _instance = None
    _dialog_callback = None  # Callback to show dialog from main context
    
    @classmethod
    def instance(cls, parent=None, dialog_callback=None):
        """Get or create the singleton instance.
        
        Args:
            parent: Parent widget (kept for compatibility, not used)
            dialog_callback: Callback function to handle dialog requests
        """
        if cls._instance is None:
            cls._instance = cls(parent)
        if dialog_callback:
            cls._dialog_callback = dialog_callback
        return cls._instance
        
    def __init__(self, parent=None):
        """Initialize dialog handler.
        
        Args:
            parent: Parent widget (kept for compatibility, not used)
        """
        self._parent = parent
        self._dialog_result = False

    def show_features_dialog(self, featuring_artists: List[str], main_artist: str) -> bool:
        """Show features dialog using callback mechanism.
        
        Args:
            featuring_artists: List of featured artist names
            main_artist: The main artist name
            
        Returns:
            True if user accepted, False otherwise
        """
        try:
            if isinstance(featuring_artists, str):
                featuring_artists = [featuring_artists]
            
            if self._dialog_callback:
                # Use callback to show dialog
                return self._dialog_callback('features', {
                    'featuring_artists': featuring_artists,
                    'main_artist': main_artist,
                    'title': 'Features Found',
                    'message': f"Found featured artists: {', '.join(featuring_artists)}\n"
                               f"for Artist: {main_artist}\n"
                               "Would you like to include them in the metadata?"
                })
            else:
                # Fallback to console output
                print(f"Features dialog: {featuring_artists} for {main_artist}")
                return False
                
        except Exception as e:
            print(f"Error showing features dialog: {e}")
            return False

    def show_error(self, message: str, title: str = "Error"):
        """Show error dialog via callback.
        
        Args:
            message: Error message to display
            title: Dialog title
        """
        try:
            if self._dialog_callback:
                self._dialog_callback('error', {
                    'message': message,
                    'title': title
                })
            else:
                print(f"{title}: {message}")
        except Exception as e:
            print(f"Error showing error dialog: {e}")

    def show_warning(self, message: str, title: str = "Warning"):
        """Show warning dialog via callback.
        
        Args:
            message: Warning message to display
            title: Dialog title
        """
        try:
            if self._dialog_callback:
                self._dialog_callback('warning', {
                    'message': message,
                    'title': title
                })
            else:
                print(f"{title}: {message}")
        except Exception as e:
            print(f"Error showing warning dialog: {e}")