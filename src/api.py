"""
API module for pywebview - exposes backend functionality to frontend
Handles communication between JavaScript frontend and Python backend
"""

import os
import json
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from metadata_updater_webview import MetadataUpdater, ProcessingThread
from license_key import LicenseManager
from settings_manager import SettingsManager

class MetadataUpdaterAPI:
    """API interface for the Metadata Updater application"""
    
    def __init__(self):
        """Initialize the API with a MetadataUpdater instance"""
        self.metadata_updater = None
        self.processing_thread = None
        self.processing_active = False
        self.callbacks = {}
        self.processed_files_metadata = []  # Store metadata for completed files
        self._view: Optional[Any] = None
        self._always_on_top = False

        # Initialize settings manager to load cached preferences
        self.settings_manager = SettingsManager()
        self.serato_library_paths: List[str] = self.settings_manager.get_serato_library_paths()
        self.serato_library_path: Optional[str] = self.settings_manager.get_serato_library_path()

        # Auto-detect Serato databases if paths not set
        if not self.serato_library_paths:
            detected_paths = self._auto_detect_serato_databases()
            if detected_paths:
                self.serato_library_paths = detected_paths
                self.serato_library_path = detected_paths[0]  # Primary library is first
                self.settings_manager.set_serato_library_paths(detected_paths)
                print(f"✓ Auto-detected {len(detected_paths)} Serato database(s)")
                for i, path in enumerate(detected_paths, 1):
                    print(f"  [{i}] {path}")
        
    def initialize_app(self):
        """Initialize the metadata updater instance"""
        try:
            if self.metadata_updater is None:
                self.metadata_updater = MetadataUpdater()

            # Set up drag-and-drop after window is ready
            self._setup_drag_drop()

            return {
                'success': True,
                'message': 'Application initialized',
                'version': '2.0'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to initialize: {str(e)}'
            }
    
    def add_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """Add files to the processing queue
        
        Accepts:
        - Full filesystem paths (e.g., "/path/to/file.mp3")
        - File names (e.g., "song.mp3") - useful for Serato drag-and-drop
          (requires serato_library_path to be set for resolution)
        """
        try:
            if not self.metadata_updater:
                return {'success': False, 'message': 'App not initialized'}
            
            # Filter for supported formats and resolve paths
            supported_formats = ('.mp3', '.m4a')
            valid_files = []
            
            for file_path in file_paths:
                if not file_path.lower().endswith(supported_formats):
                    continue
                
                # Check if it's already a full path
                if Path(file_path).exists():
                    valid_files.append(file_path)
                else:
                    # Try to resolve as Serato filename
                    resolved = self._resolve_serato_filename(file_path)
                    if resolved:
                        valid_files.append(resolved)
                        print(f"✓ Resolved Serato file: {file_path} → {resolved}")
                    else:
                        print(f"⚠ Could not find file: {file_path}")
                        if not self.serato_library_path:
                            print(f"  Tip: Set Serato library path to enable filename resolution")
            
            if not valid_files:
                return {
                    'success': False,
                    'count': 0,
                    'total': len(self.metadata_updater.selected_files),
                    'message': 'No files found. Please set Serato library path or check file paths.'
                }
             
            # Replace selected files with new ones (don't append)
            # When user drags or selects new files, they're replacing the previous selection
            self.metadata_updater.selected_files = valid_files
            
            return {
                'success': True,
                'count': len(valid_files),
                'total': len(self.metadata_updater.selected_files),
                'files': self.metadata_updater.selected_files
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error adding files: {str(e)}'
            }
    
    def remove_file(self, file_path: str) -> Dict[str, Any]:
        """Remove a file from the processing queue"""
        try:
            if not self.metadata_updater:
                return {'success': False, 'message': 'App not initialized'}
            
            if file_path in self.metadata_updater.selected_files:
                self.metadata_updater.selected_files.remove(file_path)
            
            return {
                'success': True,
                'total': len(self.metadata_updater.selected_files),
                'files': self.metadata_updater.selected_files
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error removing file: {str(e)}'
            }
    
    def clear_files(self) -> Dict[str, Any]:
        """Clear all files from the processing queue"""
        try:
            if not self.metadata_updater:
                return {'success': False, 'message': 'App not initialized'}
            
            self.metadata_updater.selected_files = []
            return {
                'success': True,
                'total': 0,
                'files': []
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error clearing files: {str(e)}'
            }
    
    def get_files(self) -> Dict[str, Any]:
        """Get the current list of selected files"""
        try:
            if not self.metadata_updater:
                return {'success': False, 'message': 'App not initialized'}
            
            files = self.metadata_updater.selected_files or []
            return {
                'success': True,
                'count': len(files),
                'files': files
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error getting files: {str(e)}'
            }
    
    def start_processing(self, selected_fields: Dict[str, bool], riddim_mode: Dict[str, bool] = None) -> Dict[str, Any]:
        """Start processing the selected files with the specified fields

        Args:
            selected_fields: Dict with field update preferences (artist, album, genre, etc.)
            riddim_mode: Dict with riddim mode flags (isDancehall, isReggae)
        """
        try:
            if not self.metadata_updater:
                return {'success': False, 'message': 'App not initialized'}

            if not self.metadata_updater.selected_files:
                return {'success': False, 'message': 'No files selected'}

            if self.processing_active:
                return {'success': False, 'message': 'Processing already in progress'}

            # Normalize riddim_mode parameter
            if riddim_mode is None:
                riddim_mode = {'isDancehall': False, 'isReggae': False}

            # Convert selected fields dict to what ProcessingThread expects
            processing_fields = {
                'artist': selected_fields.get('artist', False),
                'album': selected_fields.get('album', False),
                'genre': selected_fields.get('genre', False),
                'year': selected_fields.get('year', False),
                'subgenres': selected_fields.get('subgenres', False),
                'rating': selected_fields.get('rating', False),
            }

            self.processing_active = True
            self.metadata_updater.unfound_files = []
            self.processed_files_metadata = []  # Clear previous results

            # Create and start processing thread
            self.processing_thread = ProcessingThread(
                self.metadata_updater,
                selected_fields=processing_fields,
                riddim_mode=riddim_mode
            )
            
            # Set up callbacks instead of signals
            self.processing_thread.on_progress = self._on_progress  # type: ignore
            self.processing_thread.on_status = self._on_status  # type: ignore
            self.processing_thread.on_current_file = self._on_current_file  # type: ignore
            self.processing_thread.on_file_completed = self._on_file_completed  # type: ignore
            self.processing_thread.on_error = self._on_error  # type: ignore
            self.processing_thread.on_finished = self._on_finished  # type: ignore
            self.processing_thread.on_review_needed = self._on_review_needed  # type: ignore
            
            self.processing_thread.start()
            
            return {
                'success': True,
                'message': 'Processing started',
                'total_files': len(self.metadata_updater.selected_files)
            }
        except Exception as e:
            self.processing_active = False
            return {
                'success': False,
                'message': f'Error starting processing: {str(e)}'
            }
    
    def cancel_processing(self) -> Dict[str, Any]:
        """Cancel the current processing operation"""
        try:
            if self.processing_thread and self.processing_active:
                self.processing_thread.cancel_requested = True
                # Wait for thread to finish
                self.processing_thread.join(timeout=5.0)
                self.processing_active = False
                return {'success': True, 'message': 'Processing cancelled'}
            return {'success': False, 'message': 'No processing in progress'}
        except Exception as e:
            return {
                'success': False,
                'message': f'Error cancelling processing: {str(e)}'
            }

    def set_selected_candidate(self, file_path: str, selected_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user selection from the review modal.

        Called by frontend when user selects a candidate or submits manual edits.

        Args:
            file_path: Path to the file being reviewed
            selected_metadata: The metadata dict user selected or edited
        """
        try:
            if not self.processing_thread:
                return {'success': False, 'message': 'No processing in progress'}

            # Directly set the metadata and flag on the processing thread
            print(f"API: Setting selected candidate metadata: {selected_metadata}")
            self.processing_thread.selected_candidate_metadata = selected_metadata
            self.processing_thread.review_pending = False

            return {
                'success': True,
                'message': 'Metadata selected, resuming processing'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error setting selected candidate: {str(e)}'
            }
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get the current processing status"""
        try:
            return {
                'success': True,
                'processing_active': self.processing_active,
                'total_files': len(self.metadata_updater.selected_files) if self.metadata_updater else 0,
                'unfound_files': len(self.metadata_updater.unfound_files) if self.metadata_updater else 0
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error getting status: {str(e)}'
            }
    
    def get_license_status(self) -> Dict[str, Any]:
        """Get the current license status"""
        try:
            if not self.metadata_updater:
                return {'success': False, 'message': 'App not initialized'}
            
            license_manager = self.metadata_updater.license_manager
            is_licensed = license_manager.is_licensed()

            return {
                'success': True,
                'is_active': is_licensed,
                'files_processed': license_manager.processed_files_count,
                'daily_limit': license_manager.max_free_files if not is_licensed else None,
                'license_type': 'full' if is_licensed else 'trial'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error getting license status: {str(e)}'
            }
    
    def activate_license(self, license_key: str) -> Dict[str, Any]:
        """Activate a license with the provided key"""
        try:
            if not self.metadata_updater:
                return {'success': False, 'message': 'App not initialized'}
            
            license_manager = self.metadata_updater.license_manager
            
            # Validate and save the license
            if license_manager.validate_key(license_key):
                license_manager.save_license(license_key)
                return {
                    'success': True,
                    'message': 'License activated successfully'
                }
            else:
                return {
                    'success': False,
                    'message': 'Invalid license key'
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error activating license: {str(e)}'
            }
    
    def remove_license(self) -> Dict[str, Any]:
        """Remove the current license"""
        try:
            if not self.metadata_updater:
                return {'success': False, 'message': 'App not initialized'}
            
            license_manager = self.metadata_updater.license_manager
            # Clear the license by removing the saved key file
            license_file_path = Path(license_manager.license_file)
            if license_file_path.exists():
                license_file_path.unlink()
            
            license_manager.current_license = None
            license_manager.processed_files_count = 0
            
            return {
                'success': True,
                'message': 'License removed'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error removing license: {str(e)}'
            }
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current application settings"""
        try:
            return {
                'success': True,
                # UI placeholder settings for future functionality
                'metadata_source': 'auto',
                'max_filename_length': 200,
                'use_ai_genre_detection': True,
                # Persistent setting
                'serato_library_path': self.serato_library_path
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error getting settings: {str(e)}'
            }
    
    def get_serato_library_paths(self) -> Dict[str, Any]:
        """Get all detected/configured Serato library paths

        Returns:
            Dictionary with list of paths and metadata
        """
        try:
            return {
                'success': True,
                'paths': self.serato_library_paths,
                'count': len(self.serato_library_paths),
                'primary': self.serato_library_path
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error getting library paths: {str(e)}'
            }

    def set_serato_library_path(self, path: str) -> Dict[str, Any]:
        """Set the Serato music library path for resolving filenames

        Args:
            path: Filesystem path to Serato's music library (e.g., external drive mount point)
        """
        try:
            if not path:
                self.serato_library_path = None
                self.serato_library_paths = []
                self.settings_manager.set_serato_library_paths([])
                return {
                    'success': True,
                    'message': 'Serato library paths cleared'
                }

            # Verify the path exists
            lib_path = Path(path)
            if not lib_path.exists():
                return {
                    'success': False,
                    'message': f'Path does not exist: {path}'
                }

            if not lib_path.is_dir():
                return {
                    'success': False,
                    'message': f'Path is not a directory: {path}'
                }

            self.serato_library_path = path
            self.serato_library_paths = [path]
            # Cache the path for next app startup
            self.settings_manager.set_serato_library_paths([path])
            print(f"✓ Serato library path set to: {path}")
            return {
                'success': True,
                'message': f'Serato library path set',
                'path': path
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error setting Serato library path: {str(e)}'
            }

    def set_serato_library_paths(self, paths: list) -> Dict[str, Any]:
        """Set multiple Serato library paths

        Args:
            paths: List of filesystem paths to Serato libraries
        """
        try:
            if not paths:
                self.serato_library_path = None
                self.serato_library_paths = []
                self.settings_manager.set_serato_library_paths([])
                return {
                    'success': True,
                    'message': 'Serato library paths cleared'
                }

            # Verify all paths exist
            valid_paths = []
            for path in paths:
                lib_path = Path(path)
                if not lib_path.exists():
                    return {
                        'success': False,
                        'message': f'Path does not exist: {path}'
                    }
                if not lib_path.is_dir():
                    return {
                        'success': False,
                        'message': f'Path is not a directory: {path}'
                    }
                valid_paths.append(path)

            self.serato_library_paths = valid_paths
            self.serato_library_path = valid_paths[0]  # Primary is first
            self.settings_manager.set_serato_library_paths(valid_paths)
            print(f"✓ Set {len(valid_paths)} Serato library path(s)")
            for i, path in enumerate(valid_paths, 1):
                print(f"  [{i}] {path}")
            return {
                'success': True,
                'message': f'Set {len(valid_paths)} library path(s)',
                'paths': valid_paths,
                'count': len(valid_paths)
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error setting Serato library paths: {str(e)}'
            }
    
    def _resolve_serato_filename(self, filename: str) -> Optional[str]:
        """Attempt to resolve a Serato filename to a full filesystem path

        Strategy:
        1. Try all Serato library paths (if set and accessible)
        2. For each Serato path, also try parent and sibling directories
           (e.g., if path is /volume/Music/_Serato_, also search /volume/Music/)
        3. Try common user directories (Downloads, Music, Documents)
        4. Try current working directory

        Args:
            filename: Just the filename (e.g., "Song Name.mp3")

        Returns:
            Full path if found, None otherwise
        """
        if not filename:
            return None

        search_paths = []
        added_paths = set()  # Track to avoid duplicates

        # Helper to add path if not already added
        def add_search_path(path):
            path_str = str(path)
            if path_str not in added_paths:
                search_paths.append(path)
                added_paths.add(path_str)

        # 1. Add all Serato library paths and their parent directories (highest priority)
        if self.serato_library_paths:
            for serato_path_str in self.serato_library_paths:
                serato_path = Path(serato_path_str)
                # Add the Serato path itself
                add_search_path(serato_path)

                # Add parent directory (important for finding music files)
                if serato_path.parent:
                    add_search_path(serato_path.parent)

                # Add sibling directories that look like music folders
                if serato_path.parent:
                    try:
                        for sibling in serato_path.parent.iterdir():
                            if sibling.is_dir() and sibling.name not in ['._', '.']:
                                # Include Music, Audio, Library, and similar folders
                                if any(keyword in sibling.name.lower() for keyword in ['music', 'audio', 'library', 'tracks', 'collection']):
                                    add_search_path(sibling)
                    except Exception:
                        pass

        # Fallback to single path for backward compatibility
        if not self.serato_library_paths and self.serato_library_path:
            serato_path = Path(self.serato_library_path)
            add_search_path(serato_path)
            if serato_path.parent:
                add_search_path(serato_path.parent)

        # 2. Add common user directories
        home = Path.home()
        common_dirs = [
            home / 'Downloads',
            home / 'Music',
            home / 'Documents',
            home / 'Downloads' / 'Audio',  # Common audio subdirectory
        ]
        for path in common_dirs:
            add_search_path(path)

        # 3. Add current working directory
        add_search_path(Path.cwd())

        try:
            # Try each search path
            for lib_path in search_paths:
                if not lib_path.exists():
                    continue

                print(f"  Searching in: {lib_path}")

                # Try exact filename match
                for audio_file in lib_path.rglob(filename):
                    if audio_file.is_file():
                        print(f"  ✓ Found at: {audio_file}")
                        return str(audio_file)

                # If exact filename not found, try case-insensitive search
                filename_lower = filename.lower()
                for audio_file in lib_path.rglob('*'):
                    if audio_file.is_file() and audio_file.name.lower() == filename_lower:
                        print(f"  ✓ Found (case-insensitive) at: {audio_file}")
                        return str(audio_file)
        except Exception as e:
            print(f"Error resolving Serato filename '{filename}': {e}")

        return None

    def _auto_detect_serato_databases(self) -> List[str]:
        """Auto-detect all Serato database locations by scanning common paths.

        Searches for _Serato_ folder in:
        1. User's Music folder
        2. User's Downloads folder
        3. User's Documents folder
        4. All mounted volumes/external drives
        5. Common external drive mount points

        Returns:
            List of paths to _Serato_ folders found, ordered by:
            - Internal drive paths first (Music > Downloads > Documents)
            - External drive paths second
        """
        found_libraries = []
        search_order = []

        # 1. User's home directory paths (internal drive) - highest priority
        home = Path.home()
        search_order.append((home / 'Music', 'internal'))
        search_order.append((home / 'Downloads', 'internal'))
        search_order.append((home / 'Documents', 'internal'))

        # 2. External drive mount points (lower priority)
        volumes_path = Path('/Volumes')
        if volumes_path.exists():
            try:
                for volume in volumes_path.iterdir():
                    # Skip special system volumes
                    if volume.name not in ['Macintosh HD', 'System']:
                        search_order.append((volume, 'external'))
            except Exception:
                pass

        print("🔍 Auto-detecting Serato database(s)...")
        print(f"Searching in: {len(search_order)} locations")

        # Search for _Serato_ folder and collect all matches
        for base_path, location_type in search_order:
            if not base_path.exists():
                continue

            try:
                # First, try direct path
                serato_path = base_path / '_Serato_'
                if serato_path.exists() and serato_path.is_dir():
                    path_str = str(serato_path)
                    if path_str not in found_libraries:  # Avoid duplicates
                        found_libraries.append(path_str)
                        print(f"  ✓ Found {location_type} library: {serato_path}")

                # Also search recursively for _Serato_ folder
                # (limit depth to avoid scanning everything)
                try:
                    for item in base_path.rglob('_Serato_'):
                        if item.is_dir():
                            path_str = str(item)
                            # Skip if already found
                            if path_str not in found_libraries:
                                # Only add if it's a reasonable match (not too deep)
                                depth = len(item.relative_to(base_path).parts)
                                if depth <= 2:  # Max 2 levels deep
                                    found_libraries.append(path_str)
                                    print(f"  ✓ Found {location_type} library: {item}")
                except Exception:
                    pass

            except Exception as e:
                print(f"  ⚠ Error searching {base_path}: {e}")
                continue

        if found_libraries:
            print(f"✓ Found {len(found_libraries)} Serato database(s)")
        else:
            print("  ℹ No Serato database found. You can set it manually in settings.")

        return found_libraries

    # Callback handlers for ProcessingThread signals
    def _safe_eval(self, js_cmd: str):
        """Evaluate JS on the view safely; log exceptions without raising."""
        try:
            if hasattr(self, '_view') and self._view:
                self._view.evaluate_js(js_cmd)
        except Exception as e:
            # Avoid raising exceptions that break background threads; log and continue
            print(f"JS evaluation error: {e}")

    def _on_progress(self, progress: int):
        """Handle progress updates"""
        self._safe_eval(f"window.onProgressUpdate({progress})")
    
    def _on_status(self, status: str):
        """Handle status updates"""
        escaped_status = status.replace("'", "\\'") if status is not None else ''
        self._safe_eval(f"window.onStatusUpdate('{escaped_status}')")
    
    def _on_current_file(self, filename: str):
        """Handle current file updates"""
        escaped_filename = filename.replace("'", "\\'") if filename is not None else ''
        self._safe_eval(f"window.onCurrentFileUpdate('{escaped_filename}')")
    
    def _on_file_completed(self, index: int, successful: int, errors: int, file_path: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Handle file completion updates"""
        # Store metadata for completed file
        if file_path is not None and metadata is not None:
            import os
            try:
                self.processed_files_metadata.append({
                    'filename': os.path.basename(file_path),
                    'path': file_path,
                    'success': successful > 0,
                    'metadata': metadata
                })
            except Exception as _e:
                print(f"Error storing processed file metadata: {_e}")

        self._safe_eval(f"window.onFileCompleted({index}, {successful}, {errors})")
    
    def _on_error(self, error: str):
        """Handle errors"""
        escaped_error = error.replace("'", "\\'") if error is not None else ''
        self._safe_eval(f"window.onProcessingError('{escaped_error}')")
    
    def _on_review_needed(self, file_path: str, candidates: List[Dict[str, Any]], best_match: Dict[str, Any]):
        """Handle manual review request when metadata sources differ"""
        try:
            import json
            print(f"DEBUG _on_review_needed: file_path={file_path}")
            print(f"DEBUG _on_review_needed: candidates={candidates}")
            print(f"DEBUG _on_review_needed: best_match={best_match}")

            # Prepare candidates for JSON serialization
            candidates_json = json.dumps(candidates)
            best_match_json = json.dumps(best_match)

            print(f"DEBUG _on_review_needed: candidates_json={candidates_json}")
            print(f"DEBUG _on_review_needed: best_match_json={best_match_json[:200]}...")

            # Escape file path for JavaScript
            escaped_path = file_path.replace("'", "\\'")

            # Call frontend to show review modal
            print(f"DEBUG _on_review_needed: Calling window.onReviewNeeded with {len(candidates)} candidates")
            self._safe_eval(f"window.onReviewNeeded('{escaped_path}', {candidates_json}, {best_match_json})")
        except Exception as e:
            print(f"Error handling review needed: {e}")
            import traceback
            traceback.print_exc()

    def _on_finished(self):
        """Handle processing finished"""
        self.processing_active = False
        import json
        try:
            print(f"DEBUG: Sending {len(self.processed_files_metadata)} files to frontend")
            print(f"DEBUG: Metadata: {self.processed_files_metadata}")
            metadata_json = json.dumps(self.processed_files_metadata)
            # Send processed files metadata to frontend safely
            # Use the safe eval helper which logs errors instead of raising
            self._safe_eval(f"window.onProcessingFinished({metadata_json})")
        except Exception as e:
            print(f"Error serializing processed files metadata: {e}")
    
    def set_view_reference(self, view):
        """Set reference to the webview for callbacks"""
        self._view = view
        # Try to set up drag-and-drop after view is assigned. The view.dom
        # object may not be immediately available, so poll for a short time
        # in a background thread and attempt setup when ready.
        def delayed_setup():
            attempts = 0
            while attempts < 25:  # ~5 seconds (25 * 0.2s)
                try:
                    if hasattr(self, '_view') and self._view and hasattr(self._view, 'dom'):
                        # DOM ready, attempt setup
                        self._setup_drag_drop()
                        return
                except Exception:
                    pass
                attempts += 1
                time.sleep(0.2)
            print("Drag-and-drop setup deferred: view DOM not available after retries")

        t = threading.Thread(target=delayed_setup, daemon=True)
        t.start()
    
    def _setup_drag_drop(self):
        """Set up drag-and-drop handler with full file path support and debugging"""
        try:
            from webview.dom import DOMEventHandler

            def on_drop(e):
                """Handle file drop events with full paths and comprehensive logging"""
                try:
                    # ===== COMPREHENSIVE LOGGING FOR DEBUGGING =====
                    print("\n" + "="*70)
                    print("DROP EVENT RECEIVED - Comprehensive Debug Info")
                    print("="*70)
                    
                    # Log the entire event structure
                    print(f"Event keys: {list(e.keys()) if isinstance(e, dict) else 'N/A'}")
                    
                    data_transfer = e.get('dataTransfer', {})
                    print(f"\nDataTransfer keys: {list(data_transfer.keys())}")
                    
                    # Log all available data types
                    if 'types' in data_transfer:
                        print(f"DataTransfer types: {data_transfer['types']}")
                    
                    # Log files details
                    files = data_transfer.get('files', [])
                    print(f"\nFiles count: {len(files)}")
                    for idx, file in enumerate(files):
                        print(f"\n  File {idx}:")
                        print(f"    Keys: {list(file.keys())}")
                        for key in sorted(file.keys()):
                            value = file[key]
                            # Truncate long values for readability
                            if isinstance(value, str) and len(value) > 100:
                                value = value[:97] + "..."
                            print(f"    {key}: {value}")
                    
                    # Log items if available
                    items = data_transfer.get('items', [])
                    if items:
                        print(f"\nDataTransfer items count: {len(items)}")
                        for idx, item in enumerate(items):
                            print(f"  Item {idx}: {item}")
                    
                    # Log raw data types
                    raw_data = data_transfer.get('data', {})
                    if raw_data:
                        print(f"\nRaw data types available:")
                        for dtype, dvalue in raw_data.items():
                            if isinstance(dvalue, str) and len(dvalue) > 100:
                                dvalue = dvalue[:97] + "..."
                            print(f"  {dtype}: {dvalue}")
                    
                    print("="*70 + "\n")
                    # ===== END LOGGING =====

                    # Extract file paths/names from dropped files
                    file_paths = []
                    serato_files = []  # Track Serato files separately
                    
                    for file in files:
                        # Try to get full path first
                        full_path = file.get('pywebviewFullPath')
                        if full_path:
                            print(f"✓ Got pywebviewFullPath: {full_path}")
                            if full_path.lower().endswith(('.mp3', '.m4a')):
                                file_paths.append(full_path)
                        else:
                            # No full path - likely Serato or other drag-drop source
                            file_name = file.get('name', 'unknown')
                            print(f"⚠ No pywebviewFullPath. File: {file_name}")
                            
                            # For Serato and similar DJ apps, use the filename
                            # The file object might be used later if we get File API support
                            if file_name and file_name.lower().endswith(('.mp3', '.m4a')):
                                print(f"  → Adding Serato file by name: {file_name}")
                                file_paths.append(file_name)
                                serato_files.append({
                                    'name': file_name,
                                    'type': file.get('type'),
                                    'size': file.get('size'),
                                    'source': 'serato_or_similar'
                                })
                            else:
                                # Log what we got instead
                                print(f"  ✗ File not supported. Available keys: {list(file.keys())}")
                                for alt_key in ['path', 'webkitRelativePath', 'name', 'filename']:
                                    if alt_key in file and file[alt_key]:
                                        print(f"    Alternative '{alt_key}': {file[alt_key]}")

                    # Add files to the app
                    if file_paths:
                        print(f"\n✓ Processing {len(file_paths)} valid audio files")
                        if serato_files:
                            print(f"  → {len(serato_files)} from Serato DJ or similar DJ app")
                        result = self.add_files(file_paths)
                        print(f"  Result: {result.get('message', 'Success')}")
                        
                        # Notify frontend via JS callback
                        if hasattr(self, '_view') and self._view and result.get('success'):
                            try:
                                payload = json.dumps(result)
                                # Ensure proper JS boolean/null literals
                                self._view.evaluate_js(f"if (window.handleDroppedFiles) window.handleDroppedFiles({payload});")
                            except Exception as _e:
                                print(f"Error sending drop result to frontend: {_e}")
                    else:
                        print("\n✗ No valid audio files found in drop event")
                        print("  Files may be from unsupported sources or formats")
                        print("  Supported: .mp3, .m4a files from filesystem, Serato DJ, or other drag sources")
                        
                except Exception as e:
                    print(f"Error in drop handler: {e}")
                    import traceback
                    traceback.print_exc()

            # Bind the drop event handler only if view and DOM are ready
            if not hasattr(self, '_view') or not self._view:
                print("View not set; deferring drag-and-drop setup")
                return

            if not hasattr(self._view, 'dom'):
                print("View DOM not ready; deferring drag-and-drop setup")
                return

            self._view.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
            print("Drag-and-drop handler registered successfully")
        except Exception as e:
            print(f"Error setting up drag-and-drop: {e}")
            import traceback
            traceback.print_exc()

    def choose_files(self) -> List[str]:
        """Open file dialog and return selected files"""
        try:
            import webview
            from webview import FileDialog
            # Use pywebview's file dialog to get full file paths
            if not self._view:
                print("Error: View not initialized")
                return []
            
            file_types = ('Audio Files (*.mp3;*.m4a)', 'All files (*.*)')
            result = self._view.create_file_dialog(
                FileDialog.OPEN,
                allow_multiple=True,
                file_types=file_types
            )
  
            if result:
                return result
            return []
        except Exception as e:
            print(f"Error in choose_files: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def choose_folder(self) -> Optional[str]:
        """Open folder/directory dialog and return selected path"""
        try:
            import webview
            from webview import FileDialog
            # Use pywebview's folder dialog to get directory path
            if not self._view:
                print("Error: View not initialized")
                return None
            
            result = self._view.create_file_dialog(
                FileDialog.FOLDER,
                allow_multiple=False
            )
  
            if result:
                # create_file_dialog returns a list, get first item
                return result[0] if isinstance(result, list) else result
            return None
        except Exception as e:
            print(f"Error in choose_folder: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def clear_cache(self, cache_type: str = 'all') -> Dict[str, Any]:
        """Clear the application cache"""
        try:
            if not self.metadata_updater:
                return {'success': False, 'message': 'App not initialized'}
            
            # Determine what cache to clear
            if cache_type == 'all':
                self.metadata_updater.cache_manager.clear()
                message = 'All caches cleared successfully'
            else:
                self.metadata_updater.cache_manager.clear(cache_type)
                message = f'{cache_type.title()} cache cleared successfully'
            
            return {
                'success': True,
                'message': message,
                'cache_type': cache_type
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error clearing cache: {str(e)}'
            }


# Global API instance
_api_instance = None

def get_api() -> MetadataUpdaterAPI:
    """Get or create the global API instance"""
    global _api_instance
    if _api_instance is None:
        _api_instance = MetadataUpdaterAPI()
    return _api_instance
