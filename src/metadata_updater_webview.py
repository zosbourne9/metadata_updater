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


class ProcessingThread(Thread):
    """Worker thread for file processing with smooth progress updates."""

    def __init__(self, metadata_updater, selected_fields=None, riddim_mode=None):
        super().__init__()
        self.daemon = True
        self.metadata_updater = metadata_updater
        self.selected_fields = selected_fields or {}
        self.riddim_mode = riddim_mode or {'isDancehall': False, 'isReggae': False}
        self.cancel_requested = False
        # Callback functions
        self.on_progress = None
        self.on_status = None
        self.on_current_file = None
        self.on_file_completed = None
        self.on_error = None
        self.on_finished = None
    
    def _emit(self, callback, *args):
        """Helper to safely emit callbacks"""
        try:
            if callback:
                callback(*args)
        except Exception as e:
            print(f"Callback error: {e}")

    def run(self):
        try:
            total_files = len(self.metadata_updater.selected_files)
            successful_files = 0
            error_files = 0
            
            # Initialize
            self._emit(self.on_current_file, "Preparing to process files...")
            self._emit(self.on_status, f"0 of {total_files} files processed")
            self._emit(self.on_progress, 0)
            
            # Small delay to show initialization
            time.sleep(0.5)

            for index, file_path in enumerate(self.metadata_updater.selected_files):
                if self.cancel_requested:
                    self._emit(self.on_current_file, "Processing cancelled")
                    self._emit(self.on_status, "Processing cancelled.")
                    break

                try:
                    # Update current file display
                    filename = os.path.basename(file_path)
                    self._emit(self.on_current_file, f"Loading: {filename}")
                    
                    # Calculate and emit progress at start of each file
                    start_progress = int((index / total_files) * 100)
                    self._emit(self.on_progress, start_progress)

                    # Load file and get metadata for display
                    audio = self.metadata_updater.utility_tools.load_audio_file(file_path)
                    if audio:
                        artist_name, title = self.metadata_updater.utility_tools.get_artist_and_title(audio, file_path)
                        display_name = f"{artist_name} - {title}"
                        # Truncate if too long
                        if len(display_name) > 50:
                            display_name = display_name[:47] + "..."
                        self._emit(self.on_current_file, f"Processing: {display_name}")
                    else:
                        self._emit(self.on_current_file, f"Processing: {filename}")

                    # Process the file
                    success, metadata = self.metadata_updater.update_metadata(file_path, self.selected_fields, self.riddim_mode)

                    # Update counters
                    if success:
                        if not self.cancel_requested:
                            self.metadata_updater.license_manager.increment_processed_files()
                            successful_files += 1
                    else:
                        error_files += 1
                        self.metadata_updater.unfound_files.append(file_path)

                    # Emit completion signal with current stats and metadata
                    self._emit(self.on_file_completed, index + 1, successful_files, error_files, file_path, metadata)
                    
                    # Calculate and emit progress at completion of each file
                    end_progress = int(((index + 1) / total_files) * 100)
                    self._emit(self.on_progress, end_progress)
                    
                    # Update status with running totals
                    self._emit(self.on_status,
                        f"Processed {index + 1} of {total_files} files "
                        f"(Success: {successful_files}, Errors: {error_files})"
                    )

                except Exception as e:
                    error_files += 1
                    self.metadata_updater.unfound_files.append(file_path)
                    print(f"Error processing file {file_path}: {e}")
                    
                    # Still update progress even on error
                    error_progress = int(((index + 1) / total_files) * 100)
                    self._emit(self.on_progress, error_progress)
                    
                    self._emit(self.on_status,
                        f"Processed {index + 1} of {total_files} files "
                        f"(Success: {successful_files}, Errors: {error_files})"
                    )

            # Final completion
            if not self.cancel_requested:
                self._emit(self.on_progress, 100)
                self._emit(self.on_current_file, "Processing completed!")
                
                # Small delay to show completion
                time.sleep(0.5)
                
                self._emit(self.on_current_file, "Ready To Process Files")
                self._emit(self.on_status,
                    f"Completed! Successfully processed {successful_files} files. "
                    f"Errors: {error_files}"
                )

            self._emit(self.on_finished)

        except Exception as e:
            self._emit(self.on_error, str(e))
            self._emit(self.on_finished)


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
            
            print("Simplified integration initialized")

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
    
    def update_metadata(self, file_path, selected_fields, riddim_mode=None):
        """Update metadata for a file

        Args:
            file_path: Path to the audio file
            selected_fields: Dict with field update preferences
            riddim_mode: Dict with riddim mode flags (isDancehall, isReggae)
        """
        try:
            # Load the audio file
            audio = self.utility_tools.load_audio_file(file_path)
            if not audio:
                print(f"Could not load file: {file_path}")
                return False, None

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

            # Extract featured artists from filename for later enrichment
            filename = os.path.basename(file_path)
            filename_artist, filename_title = self.utility_tools._parse_filename(filename)
            enriched_artist = extract_featured_artists(filename, filename_artist)

            # Normalize riddim_mode parameter
            if riddim_mode is None:
                riddim_mode = {'isDancehall': False, 'isReggae': False}

            # Log search query
            SEARCH_LOGGER.info(f"SEARCH QUERY: Artist='{search_artist}' | Title='{title}'")
            SEARCH_LOGGER.info(f"Filename: {filename}")
            SEARCH_LOGGER.info(f"Filename Artist (for enrichment): '{filename_artist}' → '{enriched_artist}'")

            # Search for metadata with riddim mode flag (using primary artist only)
            metadata = self.simplified_integration.search_track_metadata(
                search_artist, title,
                riddim_mode=riddim_mode
            )

            if not metadata:
                SEARCH_LOGGER.info(f"❌ NO METADATA FOUND")
                print(f"No metadata found for: {search_artist} - {title}")
                return False, None

            # Enrich artist metadata with featured artists from filename
            if enriched_artist and enriched_artist != search_artist:
                metadata['artist'] = enriched_artist
                SEARCH_LOGGER.info(f"✅ Artist enriched: '{search_artist}' → '{enriched_artist}'")
                print(f"Enriched metadata artist: {enriched_artist}")

            # Log search results
            SEARCH_LOGGER.info(f"SEARCH RESULTS:")
            SEARCH_LOGGER.info(f"  Title: {metadata.get('title', 'N/A')}")
            SEARCH_LOGGER.info(f"  Artist: {metadata.get('artist', 'N/A')}")
            SEARCH_LOGGER.info(f"  Album: {metadata.get('album', 'N/A')}")
            SEARCH_LOGGER.info(f"  Year: {metadata.get('year', 'N/A')}")
            SEARCH_LOGGER.info(f"  Genre: {metadata.get('genre', 'N/A')}")
            SEARCH_LOGGER.info(f"  Rating: {metadata.get('rating', 'N/A')}")
            SEARCH_LOGGER.info(f"---")

            print(f"DEBUG: Raw metadata from search: {metadata}")
            print(f"DEBUG: Selected fields: {selected_fields}")
            print(f"DEBUG: 'rating' in metadata: {'rating' in metadata}")
            if 'rating' in metadata:
                print(f"DEBUG: metadata['rating'] = '{metadata['rating']}' (type: {type(metadata['rating']).__name__})")
                print(f"DEBUG: metadata['rating'] != '': {metadata['rating'] != ''}")
                print(f"DEBUG: selected_fields.get('rating'): {selected_fields.get('rating')}")

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

            print(f"DEBUG: About to check rating - selected_fields.get('rating')={selected_fields.get('rating')}, 'rating' in metadata={'rating' in metadata}, metadata.get('rating')={metadata.get('rating')}")
            if selected_fields.get('rating') and 'rating' in metadata and metadata['rating'] != '':
                filtered_metadata['rating'] = metadata['rating']
                print(f"✅ Including rating in filtered metadata: {metadata['rating']}")
            else:
                print(f"❌ NOT including rating - selected_fields.get('rating')={selected_fields.get('rating')}, 'rating' in metadata={'rating' in metadata}, rating value='{metadata.get('rating')}'")

            # Set metadata using the proper interface (with file path for proper saving)
            print(f"Filtered metadata to write: {filtered_metadata}")
            self.utility_tools.set_metadata(audio, filtered_metadata, file_path)

            print(f"Successfully updated: {file_path}")
            return True, metadata  # Return success and full metadata

        except Exception as e:
            print(f"Error updating metadata for {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return False, None
