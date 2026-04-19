"""
Simplified Metadata Updater for pywebview
Refactored to not depend on PyQt6 UI components
"""

import os
import time
import threading
import platform
import certifi
import urllib3
import logging
import collections
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Thread
from integration_helper import SimplifiedMetadataIntegration
from artist_normalizer import ArtistNormalizer
from audio_utilities import AudioUtilities
from license_key import LicenseManager
from constants import OPENROUTER_API_KEY, MAX_FILENAME_LENGTH
from genre_finder import GenreFinder
from genre_patterns import update_genre_patterns
from unified_cache_manager import UnifiedCacheManager

# Setup search debug logger
def setup_search_logger():
    """Setup a dedicated logger for search debugging."""
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs')
    os.makedirs(docs_dir, exist_ok=True)
    log_file = os.path.join(docs_dir, 'search_debug.log')

    search_logger = logging.getLogger('search_debug')
    search_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    search_logger.handlers = []

    # Create file handler
    handler = logging.FileHandler(log_file, mode='w')
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    search_logger.addHandler(handler)

    return search_logger

SEARCH_LOGGER = setup_search_logger()

VERSION = "2.0"

def extract_featured_artists(filename: str, artist_from_file: str = None) -> str:
    """
    Extract featured artists from filename and merge with primary artists.

    Parses artist string to extract featured artists (after 'ft', 'feat', etc.)
    and enriches the artist list with them.

    Example:
        "Compton Av, Steelz, Blueface & Lola Brooke ft Natalie Nunn & India Love"
        → Extracts: "Natalie Nunn & India Love"
        → Returns enriched list

    Args:
        filename: The audio filename
        artist_from_file: The artist string extracted from the file/metadata

    Returns:
        Enriched artist string with featured artists included
    """
    import re

    if not artist_from_file:
        return artist_from_file

    # Extract featured artist section after ft/feat/featuring
    featured_pattern = r'(?:ft\.?|feat\.?|featuring)\s+(.+?)(?:\s*[\(\[]|$)'
    featured_match = re.search(featured_pattern, artist_from_file, re.IGNORECASE)

    if not featured_match:
        return artist_from_file

    featured_str = featured_match.group(1).strip()

    # Remove featured artist indicator from primary artist string
    primary_artist = re.sub(
        r'\s*(?:ft\.?|feat\.?|featuring)\s+.+$',
        '',
        artist_from_file,
        flags=re.IGNORECASE
    ).strip()

    if not featured_str:
        return primary_artist

    # Parse featured artists: split by '&' and commas to get individual artists
    featured_artists = [
        artist.strip()
        for artist in re.split(r'[&,]', featured_str)
        if artist.strip()
    ]

    if not featured_artists:
        return primary_artist

    # Parse primary artists
    primary_artists = [
        artist.strip()
        for artist in re.split(r'[&,]', primary_artist)
        if artist.strip()
    ]

    # Merge and deduplicate: add featured artists that aren't already in primary
    enriched = primary_artists.copy()
    for featured in featured_artists:
        # Case-insensitive deduplication
        if not any(featured.lower() == p.lower() for p in enriched):
            enriched.append(featured)

    # Reconstruct artist string with proper separators
    # Use comma for separation but preserve ampersand pattern where it makes sense
    return ', '.join(enriched)


class ProcessingPool(Thread):
    """Worker pool for file processing using ThreadPoolExecutor."""

    def __init__(self, metadata_updater, selected_fields=None, riddim_mode=None, max_workers=4):
        super().__init__()
        self.daemon = True
        self.metadata_updater = metadata_updater
        self.selected_fields = selected_fields or {}
        self.riddim_mode = riddim_mode or {'isDancehall': False, 'isReggae': False}
        self.max_workers = max_workers
        
        self.work_queue = collections.deque(metadata_updater.selected_files)
        self.review_queue = {}  # file_path -> (candidates, best_match)
        
        self.review_lock = threading.Lock()
        self.counter_lock = threading.Lock()
        self.cancel_event = threading.Event()
        
        self.successful_files = 0
        self.error_files = 0
        self.processed_count = 0
        self.total_files = len(metadata_updater.selected_files)
        
        self.active_files = {}  # thread_id -> filename
        self.active_lock = threading.Lock()

        # Callbacks
        self.on_progress = None
        self.on_status = None
        self.on_current_file = None
        self.on_file_completed = None
        self.on_error = None
        self.on_finished = None
        self.on_review_needed = None
    
    @property
    def cancel_requested(self):
        return self.cancel_event.is_set()
    
    @cancel_requested.setter
    def cancel_requested(self, value):
        if value:
            self.cancel_event.set()
        else:
            self.cancel_event.clear()

    def _emit(self, callback, *args):
        """Helper to safely emit callbacks"""
        try:
            if callback:
                callback(*args)
        except Exception as e:
            print(f"Callback error: {e}")

    def requeue_reviewed_file(self, file_path, selected_metadata):
        """Re-queue a file that has been reviewed by the user."""
        with self.review_lock:
            if file_path in self.review_queue:
                del self.review_queue[file_path]
        
        if selected_metadata:
            # Add back to work queue as a tuple (file_path, metadata)
            self.work_queue.append((file_path, selected_metadata))
            print(f"Re-queued file for writing: {os.path.basename(file_path)}")
        else:
            # User skipped or cancelled - count as finished but no success
            with self.counter_lock:
                self.processed_count += 1
                self.error_files += 1
                self.metadata_updater.unfound_files.append(file_path)
                
                # Emit updates
                progress = int((self.processed_count / self.total_files) * 100)
                self._emit(self.on_progress, min(progress, 100))
                self._emit(self.on_file_completed, self.processed_count, self.successful_files, self.error_files, file_path, None)
                self._emit(self.on_status,
                    f"Processed {self.processed_count} of {self.total_files} files "
                    f"(Success: {self.successful_files}, Errors: {self.error_files})"
                )
            print(f"User skipped file review: {os.path.basename(file_path)}")

    def run(self):
        try:
            self._emit(self.on_current_file, "Preparing to process files...")
            self._emit(self.on_status, f"0 of {self.total_files} files processed")
            self._emit(self.on_progress, 0)
            
            time.sleep(0.5)

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                
                while not self.cancel_event.is_set():
                    # Submit new work from work_queue
                    while self.work_queue:
                        work_item = self.work_queue.popleft()
                        if isinstance(work_item, tuple):
                            file_path, pre_selected = work_item
                        else:
                            file_path, pre_selected = work_item, None
                        
                        future = executor.submit(self._worker_task, file_path, pre_selected)
                        futures[future] = file_path

                    if not futures:
                        # No active workers. Check if we have pending reviews.
                        with self.review_lock:
                            if not self.review_queue:
                                # Everything done
                                break
                        
                        # Wait for user input or new work
                        time.sleep(0.2)
                        continue

                    # Wait for at least one task to complete
                    done, _ = wait(futures.keys(), timeout=0.2, return_when=FIRST_COMPLETED)
                    for future in done:
                        del futures[future]

            # Final completion
            if not self.cancel_event.is_set():
                self._emit(self.on_progress, 100)
                self._emit(self.on_current_file, "Processing completed!")
                time.sleep(0.5)
                self._emit(self.on_current_file, "Ready To Process Files")
                self._emit(self.on_status,
                    f"Completed! Successfully processed {self.successful_files} files. "
                    f"Errors: {self.error_files}"
                )

            self._emit(self.on_finished)

        except Exception as e:
            self._emit(self.on_error, str(e))
            self._emit(self.on_finished)

    def _worker_task(self, file_path, pre_selected=None):
        """Single file processing task for the thread pool."""
        if self.cancel_event.is_set():
            return

        thread_id = threading.get_ident()
        filename = os.path.basename(file_path)

        try:
            # Get display name
            audio = self.metadata_updater.utility_tools.load_audio_file(file_path)
            if audio:
                artist_name, title = self.metadata_updater.utility_tools.get_artist_and_title(audio, file_path)
                display_name = f"{artist_name} - {title}"
                if len(display_name) > 50:
                    display_name = display_name[:47] + "..."
            else:
                display_name = filename

            # Add to active files
            with self.active_lock:
                self.active_files[thread_id] = display_name
                active_list = list(self.active_files.values())
            
            # Emit combined status of active files
            if len(active_list) > 1:
                status_msg = f"Processing {len(active_list)} files: " + ", ".join(active_list[:2])
                if len(active_list) > 2:
                    status_msg += f" (+{len(active_list)-2} more)"
                self._emit(self.on_current_file, status_msg)
            else:
                self._emit(self.on_current_file, f"Processing: {display_name}")

            # Process the file
            success, metadata = self.metadata_updater.update_metadata(
                file_path, 
                self.selected_fields, 
                self.riddim_mode,
                pre_selected_metadata=pre_selected
            )

            # Check for review needed
            if success and metadata and metadata.get('needs_review') and not pre_selected:
                # Remove from active files since it's now waiting for user
                with self.active_lock:
                    if thread_id in self.active_files:
                        del self.active_files[thread_id]

                # Build candidates NOW while thread-local searcher state is still ours
                candidates = self.metadata_updater.get_candidates(merged_metadata=metadata)
                with self.review_lock:
                    self.review_queue[file_path] = (candidates, metadata)
                
                self._emit(self.on_review_needed, file_path, candidates, metadata)
                return 

            # Update stats
            with self.counter_lock:
                # ... (rest of code)
                self.processed_count += 1
                if success:
                    self.successful_files += 1
                    self.metadata_updater.license_manager.increment_processed_files()
                else:
                    self.error_files += 1
                    self.metadata_updater.unfound_files.append(file_path)

                # Emit updates
                progress = int((self.processed_count / self.total_files) * 100)
                self._emit(self.on_progress, min(progress, 100))
                self._emit(self.on_file_completed, self.processed_count, self.successful_files, self.error_files, file_path, metadata, success)
                self._emit(self.on_status,
                    f"Processed {self.processed_count} of {self.total_files} files "
                    f"(Success: {self.successful_files}, Errors: {self.error_files})"
                )

        except Exception as e:
            print(f"Worker error for {file_path}: {e}")
            with self.counter_lock:
                self.processed_count += 1
                self.error_files += 1
                self.metadata_updater.unfound_files.append(file_path)
                self._emit(self.on_file_completed, self.processed_count, self.successful_files, self.error_files, file_path, None, False)
        finally:
            # Always remove from active files when thread is done with this task
            with self.active_lock:
                if thread_id in self.active_files:
                    del self.active_files[thread_id]


# Alias for backward compatibility
ProcessingThread = ProcessingPool



class MetadataUpdater:
    """Core metadata updater logic without UI dependencies"""
    
    def __init__(self):
        print("\nInitializing MetadataUpdater (webview)...")
        try:
            http = urllib3.PoolManager(
                cert_reqs='CERT_REQUIRED',
                ca_certs=certifi.where()
            )

            # Initialize core components
            print("Starting cache initialization...")
            self.cache_manager = UnifiedCacheManager()
            print("Cache manager initialized")

            print("Initializing core components...")
            self.utility_tools = AudioUtilities(status_update_callback=self._update_status)
            self.artist_normalizer = ArtistNormalizer(api_key=OPENROUTER_API_KEY)
            print("Core components initialized")

            # Initialize API clients with simplified integration
            print("Initializing API clients...")
            
            # Use simplified unified integration
            self.simplified_integration = SimplifiedMetadataIntegration(
                parent=None,
                status_update_callback=self._update_status,
                cache_manager=self.cache_manager
            )
            
            # Maintain compatibility with existing code
            self.spotify = self.simplified_integration
            self.musicbrainz = self.simplified_integration
            
            self.genre_finder = GenreFinder(
                self.spotify,
                self.musicbrainz,
                self.utility_tools,
                cache_manager=self.cache_manager
            )
            print("Genre finder initialized")

            # Initialize license management
            print("Setting up license manager...")
            self.license_manager = LicenseManager()

            # Initialize state variables
            print("Initializing state variables...")
            self.selected_files = []
            self.unfound_files = []
            self.current_file_index = 0
            self.cancel_requested = False
            self.processed_files_count = 0
            self.hour_start_time = time.time()
            self.processing_thread = None
            self.last_search_candidates = []  # Store top candidates for review
            self.last_search_best = None  # Store the best match for review
            print("State variables initialized")
            
            print("MetadataUpdater initialization complete!")

        except Exception as e:
            print("\nError during MetadataUpdater initialization:")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def _update_status(self, status):
        """Callback for status updates"""
        print(f"Status: {status}")

    def get_candidates(self, merged_metadata=None):
        """Get the last search candidates for review modal.

        Returns a list of candidate metadata dicts with source information.
        Uses thread-local storage from the searcher to avoid cross-thread contamination.

        Args:
            merged_metadata: The merged metadata from the current search (thread-safe)
        """
        candidates = []

        try:
            # Access the searcher through simplified_integration
            if hasattr(self.simplified_integration, 'searcher'):
                searcher = self.simplified_integration.searcher

                # Use thread-local results (safe for multi-threaded processing)
                tl = getattr(searcher, '_thread_local', None)

                # Add MusicBrainz candidate if available
                mb_result = getattr(tl, 'last_mb_result', None) if tl else getattr(searcher, 'last_mb_result', None)
                if mb_result:
                    mb_candidate = mb_result.copy()
                    mb_candidate['source'] = 'MusicBrainz'
                    candidates.append(mb_candidate)

                # Add Spotify candidate if available
                sp_result = getattr(tl, 'last_spotify_result', None) if tl else getattr(searcher, 'last_spotify_result', None)
                if sp_result:
                    sp_candidate = sp_result.copy()
                    sp_candidate['source'] = 'Spotify'
                    candidates.append(sp_candidate)

            # Add the merged result as the final candidate
            best = merged_metadata or self.last_search_best
            if best:
                merged_candidate = best.copy()
                merged_candidate['source'] = 'Merged (Best Match)'
                candidates.append(merged_candidate)

            # Return at least one candidate (the best match)
            if not candidates and best:
                b = best.copy()
                b['source'] = 'Best Match'
                return [b]

        except Exception as e:
            print(f"Error getting candidates: {e}")
            import traceback
            traceback.print_exc()

        return candidates

    
    def update_metadata(self, file_path, selected_fields, riddim_mode=None, pre_selected_metadata=None):
        """Update metadata for a file

        Args:
            file_path: Path to the audio file
            selected_fields: Dict with field update preferences
            riddim_mode: Dict with riddim mode flags (isDancehall, isReggae)
            pre_selected_metadata: Optional pre-selected metadata to write (skips search)
        """
        try:
            # Load the audio file
            audio = self.utility_tools.load_audio_file(file_path)
            if not audio:
                print(f"Could not load file: {file_path}")
                return False, None

            if pre_selected_metadata:
                metadata = pre_selected_metadata
                SEARCH_LOGGER.info(f"WRITING PRE-SELECTED METADATA: {file_path}")
            else:
                # Get artist and title from file tags/metadata
                artist_name, title = self.utility_tools.get_artist_and_title(audio, file_path)

                # Extract primary artist for searching (only use first artist)
                # This is important because Spotify/MusicBrainz searches work with primary artist only
                import re
                # First, try to remove "feat" markers
                primary = re.sub(
                    r'\s*(?:ft\.?|feat\.?|featuring)\s+.+$',
                    '',
                    artist_name,
                    flags=re.IGNORECASE
                ).strip()
                # Then extract just the first artist from comma/ampersand separated list
                search_artist = re.split(r'[,&]', primary)[0].strip()

                # Extract featured artists from filename for enrichment analysis
                filename = os.path.basename(file_path)
                filename_artist, filename_title = self.utility_tools._parse_filename(filename)
                enriched_artist = extract_featured_artists(filename, filename_artist)

                # Normalize riddim_mode parameter
                if riddim_mode is None:
                    riddim_mode = {'isDancehall': False, 'isReggae': False}

                # Log search query
                SEARCH_LOGGER.info(f"SEARCH QUERY: Artist='{search_artist}' | Title='{title}'")
                SEARCH_LOGGER.info(f"Filename: {filename}")
                SEARCH_LOGGER.info(f"Filename Artist (for reference): '{filename_artist}' → '{enriched_artist}'")

                # Search for metadata with riddim mode flag (using primary artist only)
                metadata = self.simplified_integration.search_track_metadata(
                    search_artist, title,
                    riddim_mode=riddim_mode
                )

            if not metadata:
                SEARCH_LOGGER.info(f"❌ NO METADATA FOUND")
                print(f"No metadata found for: {file_path}")
                return False, None

            if not pre_selected_metadata:
                # Log search results
                SEARCH_LOGGER.info(f"SEARCH RESULTS:")
                SEARCH_LOGGER.info(f"  Title: {metadata.get('title', 'N/A')}")
                SEARCH_LOGGER.info(f"  Artist: {metadata.get('artist', 'N/A')}")
                SEARCH_LOGGER.info(f"  Album: {metadata.get('album', 'N/A')}")
                SEARCH_LOGGER.info(f"  Year: {metadata.get('year', 'N/A')}")
                SEARCH_LOGGER.info(f"  Genre: {metadata.get('genre', 'N/A')}")
                SEARCH_LOGGER.info(f"  Rating: {metadata.get('rating', 'N/A')}")

                # Use API artist as the authoritative source (already includes all featured artists)
                # Enrichment logic just validates and logs what we found
                api_artist = metadata.get('artist', 'N/A')
                SEARCH_LOGGER.info(f"✅ Using API artist: '{api_artist}'")
                if enriched_artist != api_artist:
                    SEARCH_LOGGER.info(f"   (Filename enrichment was: '{enriched_artist}')")
                SEARCH_LOGGER.info(f"---")

            # Filter metadata based on selected fields
            filtered_metadata = {}
            if selected_fields.get('artist') and 'artist' in metadata:
                filtered_metadata['artist'] = metadata['artist']
            if selected_fields.get('album') and 'album' in metadata:
                filtered_metadata['album'] = metadata['album']
            if selected_fields.get('year') and 'year' in metadata:
                filtered_metadata['year'] = metadata['year']
            if selected_fields.get('genre') and 'genre' in metadata:
                filtered_metadata['genre'] = metadata['genre']
            if selected_fields.get('subgenres') and 'subgenres' in metadata:
                filtered_metadata['comments'] = metadata['subgenres']
            elif selected_fields.get('subgenres') and 'comments' in metadata:
                # Support both naming conventions
                filtered_metadata['comments'] = metadata['comments']

            if selected_fields.get('rating') and 'rating' in metadata and metadata['rating'] != '':
                filtered_metadata['rating'] = metadata['rating']

            # Store the best match for candidate review if not writing pre-selected
            if not pre_selected_metadata:
                self.last_search_best = metadata

            # Check if review is needed BEFORE writing
            needs_review = metadata.get('needs_review', False) if not pre_selected_metadata else False

            if not needs_review:
                # No review needed, write the metadata immediately
                print(f"Filtered metadata to write for {os.path.basename(file_path)}: {filtered_metadata}")
                self.utility_tools.set_metadata(audio, filtered_metadata, file_path)
                print(f"Successfully updated: {file_path}")
            else:
                # Review is needed, don't write yet - ProcessingPool will handle it
                print(f"⏸️  Review needed - deferring metadata write until user confirms")

            return True, metadata  # Return success and full metadata (with needs_review flag)

        except Exception as e:
            print(f"Error updating metadata for {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return False, None
