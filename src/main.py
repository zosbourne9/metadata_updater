import os
import sys
import platform
import logging
import warnings
from pathlib import Path

# Disable PostHog telemetry before importing pywebview
os.environ['POSTHOG_DISABLED'] = '1'

# Suppress HuggingFace tokenizers forking warning
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import webview
from api import get_api

# Suppress known deprecation warnings from third-party libraries
warnings.filterwarnings("ignore", category=UserWarning, message=".*URL.raw is deprecated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="httpx")

# Suppress urllib3 and PostHog connection logging
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('posthog').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)

# DEBUG LOGGING CONFIGURATION - Set to True to enable console logging to file
ENABLE_DEBUG_LOGGING = False  # Change to True to enable debug logging

def setup_logging():
    """Setup logging configuration for debugging."""
    if ENABLE_DEBUG_LOGGING:
        # Create logs directory in docs/ folder
        docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
        os.makedirs(docs_dir, exist_ok=True)
        log_file = os.path.join(docs_dir, 'metadata_updater_debug.txt')
        
        # Configure logging to both file and console
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='w'),  # Overwrite log file each run
                logging.StreamHandler(sys.stdout)  # Also print to console
            ]
        )
        
        # Redirect print statements to logging
        class LoggerWriter:
            def __init__(self, level):
                self.level = level
            
            def write(self, message):
                if message.strip():  # Only log non-empty messages
                    self.level(message.strip())
            
            def flush(self):
                pass
        
        # Replace stdout and stderr with logger
        sys.stdout = LoggerWriter(logging.info)
        sys.stderr = LoggerWriter(logging.error)
        
        logging.info("Debug logging enabled - logs will be written to: %s", log_file)
    else:
        # Minimal logging setup when debugging is disabled
        logging.basicConfig(level=logging.WARNING)

def get_app_cache_dir():
    """Get the appropriate cache directory for the application."""
    if platform.system() == 'Darwin':
        cache_dir = os.path.expanduser('~/Library/Application Support/Metadata Updater')
    else:
        cache_dir = os.path.expanduser('~/.metadata_updater')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def debug_print_env():
    """Print debug information about the environment."""
    for key in ['PYTHONPATH']:
        print(f"{key}: {os.environ.get(key, 'Not set')}")

def fix_macos_path():
    """Fix environment and paths for macOS bundled app."""
    if getattr(sys, 'frozen', False) and platform.system() == 'Darwin':
        debug_print_env()
        
        # Get the app bundle path
        bundle_dir = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
        
        # Set environment variables
        os.environ['PATH'] = f"{os.path.join(bundle_dir, 'MacOS')}:{os.environ.get('PATH', '')}"
        
        # Set working directory to app cache directory
        cache_dir = get_app_cache_dir()
        os.chdir(cache_dir)

def get_app_icon():
    """Get the application icon path."""
    if getattr(sys, 'frozen', False):
        # Running as bundled app - icons are in assets/ subdirectory
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            # Try platform-specific icons first
            icon_paths = [
                os.path.join(meipass, 'assets', 'icon.icns'),  # macOS
                os.path.join(meipass, 'assets', 'icon.ico'),   # Windows
                os.path.join(meipass, 'assets', 'icon.png'),   # Linux/fallback
            ]
            for path in icon_paths:
                if os.path.exists(path):
                    return path
        
        # Try alternative paths in executable directory
        icon_paths = [
            os.path.join(os.path.dirname(sys.executable), 'assets', 'icon.icns'),
            os.path.join(os.path.dirname(sys.executable), 'assets', 'icon.ico'),
            os.path.join(os.path.dirname(sys.executable), 'icon.icns'),
            os.path.join(os.path.dirname(sys.executable), 'icon.ico'),
        ]
        for path in icon_paths:
            if os.path.exists(path):
                return path
    else:
        # Running from source - assets/ directory is one level up from src/
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
        icon_paths = [
            os.path.join(assets_dir, 'icon.icns'),  # macOS
            os.path.join(assets_dir, 'icon.ico'),   # Windows
            os.path.join(assets_dir, 'icon.png'),   # Linux/fallback
        ]
        for path in icon_paths:
            if os.path.exists(path):
                return path
    
    return None

def get_html_path():
    """Get the path to the HTML file."""
    if getattr(sys, 'frozen', False):
        # Running as bundled app - web files are in web/ subdirectory
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            return os.path.join(meipass, 'web', 'index.html')
    
    # Running from source - web/ directory is one level up from src/
    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'web')
    return os.path.join(web_dir, 'index.html')

def initialize_app():
    """Initialize and start the application."""
    try:
        # Setup logging first
        setup_logging()
        
        print("Initializing Metadata Updater (pywebview)...")
        
        # Fix paths for macOS if needed
        if platform.system() == 'Darwin':
            fix_macos_path()
        
        # Set cache directory
        os.environ['CACHE_DIR'] = get_app_cache_dir()
        
        # Initialize the API
        api = get_api()
        init_result = api.initialize_app()
        if not init_result['success']:
            print(f"Warning: {init_result.get('message', 'Failed to initialize API')}")
        
        # Get HTML and icon paths
        html_path = get_html_path()
        icon_path = get_app_icon()
        
        if not os.path.exists(html_path):
            print(f"Error: HTML file not found at {html_path}")
            sys.exit(1)
        
        print(f"Loading HTML from: {html_path}")
        
        # Determine window size - optimized for two-panel layout
        if platform.system() == 'Darwin':
            # macOS - sized for two-panel layout
            width = 950
            height = 950
        else:
            # Windows/Linux
            width = 950
            height = 950
        
        # Create and show the webview window
        print("Creating webview window...")
        window = webview.create_window(
            title='Metadata Updater',
            url=html_path,
            js_api=api,
            width=width,
            height=height,
            resizable=True,
            background_color='#0f172a'
        )
        
        # Store view reference in API for callbacks
        api.set_view_reference(window)
        
        print("Starting webview...")
        webview.start(debug=False)
        
    except Exception as e:
        print("\nError initializing application:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("\nFull traceback:")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    initialize_app()
