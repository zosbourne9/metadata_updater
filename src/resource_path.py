import os
import sys

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller on macOS
    
    In development:
    - Projects root is two directories up from src/resource_path.py
    - Config files are in config/
    - Web files are in web/
    - Assets are in assets/
    
    In PyInstaller bundle:
    - Directory structure is preserved:
      - Config files in config/
      - Web files in web/
      - Assets in assets/
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        if getattr(sys, '_MEIPASS', None):
            base_path = getattr(sys, '_MEIPASS')
        else:
            # Running in development mode - base path is the project root
            # (two directories up from src/ where this file is located)
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        full_path = os.path.join(base_path, relative_path)
                    
        if os.path.exists(full_path):
            return full_path
        else:
            # Try alternate locations
            alt_paths = [
                os.path.join(os.path.dirname(sys.executable), relative_path),
                os.path.join(os.getcwd(), relative_path)
            ]
            for path in alt_paths:
                if os.path.exists(path):
                    return path
            
            raise FileNotFoundError(f"Resource not found: {relative_path}")

    except Exception as e:
        print(f"Error in get_resource_path: {e}")
        raise
