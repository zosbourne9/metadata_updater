import os
import time
import threading
import platform
import certifi
import urllib3
import time
from threading import Thread
# from spotify_integration import SpotifyIntegration # REPLACED
# from mb_integration import MusicBrainzIntegration # REPLACED
from integration_helper import SimplifiedMetadataIntegration
from artist_normalizer import ArtistNormalizer
from hf_llm_utils import HFLLMUtilities
from license_key import LicenseManager
from constants import OPENROUTER_API_KEY, MAX_FILENAME_LENGTH
from genre_finder import GenreFinder
from license_key import LicenseManager
from genre_patterns import update_genre_patterns
from unified_cache_manager import UnifiedCacheManager

VERSION = "1.7"

class ProcessingThread(Thread):
    """Worker thread for file processing with smooth progress updates."""

    def __init__(self, metadata_updater, selected_fields=None):
        super().__init__()
        self.daemon = True
        self.metadata_updater = metadata_updater
        self.selected_fields = selected_fields
        self.cancel_requested = False
        # Callback functions instead of signals
        self.on_progress = None
        self.on_status = None
        self.on_current_file = None
        self.on_file_completed = None
        self.on_error = None
        self.on_finished = None
    
    def emit_progress(self, value):
        if self.on_progress: self.on_progress(value)
    
    def emit_status(self, value):
        if self.on_status: self.on_status(value)
    
    def emit_current_file(self, value):
        if self.on_current_file: self.on_current_file(value)
    
    def emit_file_completed(self, index, successful, errors):
        if self.on_file_completed: self.on_file_completed(index, successful, errors)
    
    def emit_error(self, value):
        if self.on_error: self.on_error(value)
    
    def emit_finished(self):
        if self.on_finished: self.on_finished()

    def run(self):
        try:
            total_files = len(self.metadata_updater.selected_files)
            successful_files = 0
            error_files = 0
            
            # Initialize
            self.emit_current_file("Preparing to process files...")
            self.emit_status(f"0 of {total_files} files processed")
            self.emit_progress(0)
            
            # Small delay to show initialization
            time.sleep(0.5)

            for index, file_path in enumerate(self.metadata_updater.selected_files):
                if self.cancel_requested:
                    self.current_file.emit("Processing cancelled")
                    self.status.emit("Processing cancelled.")
                    break

                try:
                    # Update current file display
                    filename = os.path.basename(file_path)
                    self.current_file.emit(f"Loading: {filename}")
                    
                    # Calculate and emit progress at start of each file
                    start_progress = int((index / total_files) * 100)
                    self.progress.emit(start_progress)

                    # Load file and get metadata for display
                    audio = self.metadata_updater.utility_tools.load_audio_file(file_path)
                    if audio:
                        artist_name, title = self.metadata_updater.utility_tools.get_artist_and_title(audio, file_path)
                        display_name = f"{artist_name} - {title}"
                        # Truncate if too long
                        if len(display_name) > 50:
                            display_name = display_name[:47] + "..."
                        self.current_file.emit(f"Processing: {display_name}")
                    else:
                        self.current_file.emit(f"Processing: {filename}")

                    # Process the file
                    success = self.metadata_updater.update_metadata(file_path, self.selected_fields)
                    
                    # Update counters
                    if success:
                        if not self.cancel_requested:
                            self.metadata_updater.license_manager.increment_processed_files()
                            successful_files += 1
                    else:
                        error_files += 1
                        self.metadata_updater.unfound_files.append(file_path)

                    # Emit completion signal with current stats
                    self.file_completed.emit(index + 1, successful_files, error_files)
                    
                    # Calculate and emit progress at completion of each file
                    end_progress = int(((index + 1) / total_files) * 100)
                    self.progress.emit(end_progress)
                    
                    # Update status with running totals
                    self.status.emit(
                        f"Processed {index + 1} of {total_files} files "
                        f"(Success: {successful_files}, Errors: {error_files})"
                    )

                except Exception as e:
                    error_files += 1
                    self.metadata_updater.unfound_files.append(file_path)
                    print(f"Error processing file {file_path}: {e}")
                    
                    # Still update progress even on error
                    error_progress = int(((index + 1) / total_files) * 100)
                    self.progress.emit(error_progress)
                    
                    self.status.emit(
                        f"Processed {index + 1} of {total_files} files "
                        f"(Success: {successful_files}, Errors: {error_files})"
                    )

            # Final completion
            if not self.cancel_requested:
                self.progress.emit(100)
                self.current_file.emit("Processing completed!")
                
                # Small delay to show completion
                time.sleep(0.5)
                
                self.current_file.emit("Ready To Process Files")
                self.status.emit(
                    f"Completed! Successfully processed {successful_files} files. "
                    f"Errors: {error_files}"
                )

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit()

class MetadataUpdater(QMainWindow):
    def on_closing(self):
        """Handle window closing event"""
        try:
            # Clean up any resources
            if hasattr(self, '_style'):
                self._style = None
            
            # Destroy the window
            self.quit()
            self.destroy()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            self.destroy()  # Force destroy if cleanup fails

    def __init__(self):
        print("\nInitializing MetadataUpdater...")
        try:
            super().__init__()

            http = urllib3.PoolManager(
                cert_reqs='CERT_REQUIRED',
                ca_certs=certifi.where()
            )

            # Hide window during initialization
            self.hide()
            print("Window hidden during initialization")

            # Initialize core components
            print("Starting cache initialization...")
            self.cache_manager = UnifiedCacheManager()
            print("Cache manager initialized")

            print("Initializing core components...")
            self.utility_tools = HFLLMUtilities(parent=self, update_status_callback=self.update_status_label)
            self.artist_normalizer = ArtistNormalizer(api_key=OPENROUTER_API_KEY)
            print("Core components initialized")

            # Initialize API clients with simplified integration
            print("Initializing API clients...")
            
            # Use simplified unified integration
            self.simplified_integration = SimplifiedMetadataIntegration(
                parent=self,
                status_update_callback=self.update_status_label,
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
            
            # Initialize UI elements
            print("Setting up UI elements...")
            self.ui_elements = UIElements(
                self, 
                version=VERSION, 
                license_manager=self.license_manager
            )
            self.setCentralWidget(self.ui_elements)
            print("UI elements initialized")

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

            # Configure window appearance
            print("Final window configuration...")
            if platform.system() == 'Darwin':
                self.raise_()
                self.activateWindow()

            # Finally show the window
            self.show()
            print("Window shown")
            print("MetadataUpdater initialization complete!")

        except Exception as e:
            print("\nError during MetadataUpdater initialization:")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
   
    def closeEvent(self, event):
        """Handle window closing event"""
        try:
            if self.processing_thread and self.processing_thread.isRunning():
                self.processing_thread.cancel_requested = True
                self.processing_thread.wait()
            event.accept()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            event.accept()

    def on_drop_files(self, event):
        try:
            files = self.tk.splitlist(event.data)
            self.selected_files = []
            
            for file in files:
                if os.path.isdir(file):
                    for root, dirs, filenames in os.walk(file):
                        for filename in filenames:
                            if filename.lower().endswith(('.mp3', '.m4a', '.wav')):
                                self.selected_files.append(os.path.join(root, filename))
                elif file.lower().endswith(('.mp3', '.m4a', '.wav')):
                    self.selected_files.append(file)

            if self.selected_files:
                self.ui_elements.status_label.configure(text=f"Selected Files: {len(self.selected_files)}")
                self.enable_ui_components()
            else:
                self.ui_elements.status_label.configure(text="No supported audio files selected.")
        except Exception as e:
            self.update_status_label(f"Error handling dropped files: {e}")

    @pyqtSlot()
    def select_files_or_folder_threaded(self):
        if self.ui_elements.combobox.currentText() == 'File(s)':
            self.select_files()
        else:
            self.select_folder()

    def select_files(self):
        """Select files with validation."""
        try:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Audio Files",
                "",
                "Audio Files (*.mp3 *.m4a)"
            )
            if file_paths:
                # Validate files are accessible
                valid_files = []
                invalid_files = []
                
                for file_path in file_paths:
                    try:
                        if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                            # Try to get file size to ensure it's readable
                            size = os.path.getsize(file_path)
                            if size > 0:
                                valid_files.append(file_path)
                            else:
                                invalid_files.append(f"{file_path} (empty file)")
                        else:
                            invalid_files.append(f"{file_path} (not accessible)")
                    except Exception as e:
                        invalid_files.append(f"{file_path} (error: {e})")
                
                if valid_files:
                    self.selected_files = valid_files
                    status_msg = f"Selected {len(valid_files)} valid file(s)"
                    if invalid_files:
                        status_msg += f" ({len(invalid_files)} files skipped)"
                    self.ui_elements.status_label.setText(status_msg)
                    self.enable_ui_components()
                else:
                    self.ui_elements.status_label.setText("No valid MP3 or M4A files found.")
                    
                # Log any invalid files
                if invalid_files:
                    print("Invalid files skipped:")
                    for invalid_file in invalid_files:
                        print(f"  - {invalid_file}")
                        
            else:
                self.ui_elements.status_label.setText("No files selected.")
        except Exception as e:
            self.update_status_label(f"Error selecting files: {e}")

    def select_folder(self):
        """Select folder with validation."""
        try:
            folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
            if folder_path:
                # Find valid audio files
                valid_files = []
                for filename in os.listdir(folder_path):
                    if filename.lower().endswith(('.mp3', '.m4a')):
                        file_path = os.path.join(folder_path, filename)
                        try:
                            if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                                size = os.path.getsize(file_path)
                                if size > 0:
                                    valid_files.append(file_path)
                        except Exception as e:
                            print(f"Error validating {file_path}: {e}")
                
                if valid_files:
                    self.selected_files = valid_files
                    self.ui_elements.status_label.setText(f"Selected Folder: {folder_path} ({len(valid_files)} files)")
                    self.enable_ui_components()
                else:
                    self.ui_elements.status_label.setText("No valid MP3 or M4A files found in the selected folder.")
        except Exception as e:
            self.update_status_label(f"Error selecting folder: {e}")

    def on_processing_finished(self):
        """Handle completion of processing thread."""
        self.enable_ui_components()
        self.cancel_requested = False
        # Update license banner to reflect new file count
        self.ui_elements.license_banner.update_status()

    @pyqtSlot(str)
    def on_processing_error(self, error_message):
        """Handle processing thread errors."""
        self.update_current_file_label("Ready To Process Files")
        self.update_status_label(f"Error processing files: {error_message}")
        self.ui_elements.progress_bar.setValue(0)  # Reset progress on error
        self.enable_ui_components()

    def update_metadata(self, file_path, selected_fields=None):
        """Enhanced metadata update with better hint passing and source comparison."""
        try:
            print("Starting metadata update process...")
            
            # Load audio file ONCE at the beginning
            audio = self.utility_tools.load_audio_file(file_path)
            if not audio: 
                return False
            if not (hasattr(audio, 'tags') or hasattr(audio, '_tags')):
                print(f"ERROR: Invalid audio file format for: {file_path}")
                return False

            # Get metadata from the already loaded audio object
            artist_name, original_title = self.utility_tools.get_artist_and_title_from_audio(audio, file_path)
            if not artist_name or not original_title:
                print("ERROR: Could not extract artist name or title")
                return False
            
            print(f"Using metadata - Artist: {artist_name}, Title: {original_title}")
            simplified_title = self.utility_tools.clean_track_title(original_title)
            cleaned_artist_name = self.utility_tools.remove_featuring_artists(artist_name)

            # Check cache (no file loading needed)
            cached_metadata = self.cache_manager.get_metadata(artist_name, simplified_title)
            if cached_metadata:
                print("Found valid metadata in cache")
                if self.utility_tools.set_metadata(audio, cached_metadata):
                    print(f"Successfully applied cached metadata for: {file_path}")
                    return True
                else:
                    print(f"Failed to apply cached metadata for: {file_path}")
                    return False
            print("No valid cache found, proceeding with metadata retrieval...")

            # 6. Try MusicBrainz first
            musicbrainz_metadata = self.musicbrainz.search_metadata(cleaned_artist_name, simplified_title)
            print(f"Debug - MusicBrainz metadata received: {musicbrainz_metadata}")

            mb_preferred_year = None
            mb_preferred_album_title = None
            # Ensure musicbrainz_metadata is a dictionary before accessing keys
            if isinstance(musicbrainz_metadata, dict):
                if musicbrainz_metadata.get('year'):
                    try:
                        mb_preferred_year = int(musicbrainz_metadata['year'])
                    except (ValueError, TypeError):
                        print(f"Warning: Could not parse year from MusicBrainz: {musicbrainz_metadata['year']}")
                mb_preferred_album_title = musicbrainz_metadata.get('album') # Assuming 'album' key holds album title
            
            print(f"Hints from MusicBrainz - Preferred Year: {mb_preferred_year}, Preferred Album: {mb_preferred_album_title}")

            # 7. Check if MusicBrainz has complete metadata before trying Spotify
            def has_complete_metadata(metadata):
                """Check if metadata has all essential fields filled."""
                if not isinstance(metadata, dict):
                    return False
                required_fields = ['title', 'artist', 'album', 'year']
                return all(metadata.get(field) and str(metadata.get(field)).strip() != '' for field in required_fields)
            
            spotify_metadata = None
            
            if has_complete_metadata(musicbrainz_metadata):
                print("MusicBrainz provided complete metadata - skipping Spotify search for efficiency")
                spotify_metadata = {}  # Empty dict to indicate no Spotify search needed
            else:
                print("MusicBrainz metadata incomplete - proceeding with Spotify search for additional info...")
                spotify_metadata = self.spotify.extract_metadata_from_spotify(
                    cleaned_artist_name,
                    simplified_title,
                    {'artist': cleaned_artist_name, 'file_path': file_path}, # Existing context dict
                    mb_preferred_year=mb_preferred_year,
                    mb_preferred_album_title=mb_preferred_album_title
                )
            if isinstance(spotify_metadata, dict):
                spotify_summary = {
                    'artist': spotify_metadata.get('artist'),
                    'title': spotify_metadata.get('title'),
                    'album': spotify_metadata.get('album'),
                    'year': spotify_metadata.get('year'),
                    'spotify_id': spotify_metadata.get('spotify_id'),
                }
                print(f"Debug - Spotify metadata received: {spotify_summary}")
            else:
                print(f"Debug - Spotify metadata received: {spotify_metadata}")

            # 8. Determine final metadata source with smarter comparison
            final_metadata = None
            
            # Normalize titles for comparison if needed (using a shared utility if possible)
            def normalize_for_comparison(text):
                import re
                if not text: return ""
                text = text.lower()
                text = re.sub(r'\s*[\[\(\]][^)]*[\]\)]', '', text) 
                text = re.sub(r'[^\w\s]', '', text)
                text = ' '.join(text.split())
                return text

            # Handle the case where Spotify was skipped
            if isinstance(musicbrainz_metadata, dict) and not spotify_metadata:
                print("Using MusicBrainz metadata directly (Spotify search was skipped)")
                final_metadata = musicbrainz_metadata
            elif isinstance(musicbrainz_metadata, dict) and isinstance(spotify_metadata, dict) and spotify_metadata:
                print("Comparing MusicBrainz and Spotify metadata...")
                
                # Get normalized data
                spotify_year = None
                mb_year = None
                try:
                    if spotify_metadata.get('year'): 
                        spotify_year = int(spotify_metadata['year'])
                    if musicbrainz_metadata.get('year'): 
                        mb_year = int(musicbrainz_metadata['year'])
                except:
                    pass

                spotify_album_norm = normalize_for_comparison(spotify_metadata.get('album', ''))
                mb_album_norm = normalize_for_comparison(musicbrainz_metadata.get('album', ''))
                
                # Calculate quality scores for each source
                mb_quality_score = 0
                spotify_quality_score = 0
                
                # MusicBrainz quality factors
                if mb_year and mb_year <= 1990:
                    mb_quality_score += 3  # Strong bonus for classic era
                    print(f"MusicBrainz classic era bonus: +3 for year {mb_year}")
                elif mb_year and mb_year <= 2000:
                    mb_quality_score += 2  # Moderate bonus for pre-2000
                    print(f"MusicBrainz pre-2000 bonus: +2 for year {mb_year}")
                
                # Check if MusicBrainz album title matches song title (indicates original single)
                song_title_norm = normalize_for_comparison(simplified_title)
                if mb_album_norm == song_title_norm:
                    mb_quality_score += 2
                    print(f"MusicBrainz album=song title bonus: +2")
                
                # Penalize MusicBrainz for compilation indicators
                mb_album_lower = musicbrainz_metadata.get('album', '').lower()
                compilation_indicators = ['greatest hits', 'best of', 'collection', 'anthology', 'essential']
                if any(indicator in mb_album_lower for indicator in compilation_indicators):
                    mb_quality_score -= 2
                    print(f"MusicBrainz compilation penalty: -2")
                
                # Spotify quality factors
                if spotify_year and spotify_year <= 1990:
                    spotify_quality_score += 2  # Less bonus than MB for same era
                    print(f"Spotify classic era bonus: +2 for year {spotify_year}")
                elif spotify_year and spotify_year <= 2000:
                    spotify_quality_score += 1
                    print(f"Spotify pre-2000 bonus: +1 for year {spotify_year}")
                
                # Penalize Spotify for later releases when MB has earlier
                if mb_year and spotify_year and spotify_year > mb_year + 5:
                    spotify_quality_score -= 2
                    print(f"Spotify later release penalty: -2 (Spotify {spotify_year} vs MB {mb_year})")
                
                # Penalize Spotify for compilation indicators
                spotify_album_lower = spotify_metadata.get('album', '').lower()
                if any(indicator in spotify_album_lower for indicator in compilation_indicators):
                    spotify_quality_score -= 2
                    print(f"Spotify compilation penalty: -2")
                
                # Check for "Mr." prefix which often indicates compilation/reissue
                if spotify_album_lower.startswith('mr. ') and not mb_album_lower.startswith('mr. '):
                    spotify_quality_score -= 1
                    print(f"Spotify 'Mr.' prefix penalty: -1")
                
                # Bonus for having complete metadata
                if spotify_metadata.get('spotify_id') and spotify_metadata.get('artist_id'):
                    spotify_quality_score += 1
                    print(f"Spotify completeness bonus: +1")
                
                print(f"Quality scores - MusicBrainz: {mb_quality_score}, Spotify: {spotify_quality_score}")
                
                # Decision logic
                if mb_quality_score > spotify_quality_score:
                    print(f"Choosing MusicBrainz metadata (quality score {mb_quality_score} > {spotify_quality_score})")
                    final_metadata = musicbrainz_metadata
                elif spotify_quality_score > mb_quality_score:
                    print(f"Choosing Spotify metadata (quality score {spotify_quality_score} > {mb_quality_score})")
                    final_metadata = spotify_metadata
                else:
                    # Tie-breaker: prefer earlier year
                    if mb_year and spotify_year and mb_year < spotify_year:
                        print(f"Tie-breaker: choosing MusicBrainz for earlier year ({mb_year} < {spotify_year})")
                        final_metadata = musicbrainz_metadata
                    else:
                        print(f"Tie-breaker: choosing Spotify for completeness")
                        final_metadata = spotify_metadata

            elif isinstance(spotify_metadata, dict):
                print("Only Spotify metadata found. Using Spotify.")
                final_metadata = spotify_metadata
            elif isinstance(musicbrainz_metadata, dict):
                print("Only MusicBrainz metadata found. Using MusicBrainz.")
                final_metadata = musicbrainz_metadata
            else:
                print("No metadata found from any source.")
                return False

            # 9. Enhanced Genre Detection: Artist genres from MusicBrainz, then song-level fallbacks
            if final_metadata:
                # (Ensure to use artist name from final_metadata for genre search if it changed)
                artist_for_genre = final_metadata.get('artist', artist_name)
                title_for_genre = final_metadata.get('title', simplified_title)
                
                # Enhanced multi-artist genre analysis
                main_artist_for_genre = self.utility_tools.get_main_artist_name(artist_for_genre)

                # Extract all artists from the artist string (main + featured)
                all_artist_genres = []

                # Get main artist genre
                print(f"\nTrying artist-level genres from MusicBrainz for main artist: {main_artist_for_genre}")
                main_artist_genre_result = self.musicbrainz.get_artist_genres_from_mb(main_artist_for_genre)
                if main_artist_genre_result and main_artist_genre_result[0] and main_artist_genre_result[0] != "No Genre":
                    all_artist_genres.append({
                        'artist': main_artist_for_genre,
                        'genre': main_artist_genre_result[0],
                        'subgenres': main_artist_genre_result[1] or ""
                    })
                    print(f"Main artist {main_artist_for_genre}: {main_artist_genre_result[0]}")

                # Check if there are featured artists and get their genres too
                if "feat" in artist_for_genre.lower() or "ft." in artist_for_genre.lower() or "f." in artist_for_genre.lower() or " x " in artist_for_genre.lower():
                    try:
                        # First try simple string parsing (faster and more reliable)
                        featured_artists = []

                        # Simple regex-based extraction
                        import re

                        # Remove the main artist and extract featured artists
                        feat_pattern = r'(?:feat\.?|ft\.?|f\.?|featuring)\s*([^()]+)'
                        feat_match = re.search(feat_pattern, artist_for_genre, re.IGNORECASE)

                        if feat_match:
                            feat_string = feat_match.group(1).strip()
                            # Split by common separators and clean up
                            separators = [',', ' & ', ' and ', ' x ', ' X ']
                            for sep in separators:
                                feat_string = feat_string.replace(sep, '|')

                            featured_artists = [name.strip() for name in feat_string.split('|') if name.strip()]

                        # If simple parsing didn't work, fall back to AI
                        if not featured_artists:
                            print("Simple parsing failed, using AI extraction...")
                            featured_extraction_prompt = f"""Extract all individual artist names from this collaboration string:

Artist String: "{artist_for_genre}"

Rules:
1. Return each artist name on a separate line
2. Include the main artist and ALL featured artists
3. Remove any collaboration keywords (feat., ft., featuring, x, &, etc.)
4. Clean up each artist name (remove extra spaces, punctuation)
5. Return only the artist names, one per line

Example:
Input: "Calvin Harris feat. Young Thug, Pharrell Williams & Ariana Grande"
Output:
Calvin Harris
Young Thug
Pharrell Williams
Ariana Grande"""

                            all_artists_text = self.utility_tools._query_llm(featured_extraction_prompt, "extract_featured_artists")
                            all_artists = [artist.strip() for artist in all_artists_text.split('\n') if artist.strip()]
                            featured_artists = [artist for artist in all_artists if artist != main_artist_for_genre]

                        print(f"Extracted featured artists: {featured_artists}")

                        # Get genres for each featured artist
                        for featured_artist in featured_artists[:3]:  # Limit to 3 featured artists to avoid API limits
                            print(f"Getting genres for featured artist: {featured_artist}")
                            featured_genre_result = self.musicbrainz.get_artist_genres_from_mb(featured_artist)
                            if featured_genre_result and featured_genre_result[0] and featured_genre_result[0] != "No Genre":
                                all_artist_genres.append({
                                    'artist': featured_artist,
                                    'genre': featured_genre_result[0],
                                    'subgenres': featured_genre_result[1] or ""
                                })
                                print(f"Featured artist {featured_artist}: {featured_genre_result[0]}")
                    except Exception as e:
                        print(f"Error extracting featured artists: {e}")

                # If we have multiple artist genres, use AI to determine the best overall genre
                if len(all_artist_genres) > 1:
                    print(f"\nAnalyzing {len(all_artist_genres)} artist genres for best overall genre...")

                    # Create prompt for AI genre and subgenre analysis
                    artist_genre_info = []
                    all_subgenres = []
                    for artist_info in all_artist_genres:
                        genre_text = f"- {artist_info['artist']}: {artist_info['genre']}"
                        if artist_info['subgenres'] and artist_info['subgenres'].strip():
                            genre_text += f" (subgenres: {artist_info['subgenres']})"
                            all_subgenres.append(artist_info['subgenres'])
                        artist_genre_info.append(genre_text)

                    genre_analysis_prompt = f"""Analyze these artist genres to determine the best overall genre and subgenres for their collaboration:

{chr(10).join(artist_genre_info)}

Song: "{title_for_genre}" by {artist_for_genre}

Rules:
1. Consider the dominant genre among all artists
2. For collaborations, the genre should reflect the overall sound/style
3. If there's a mix (e.g., Electronic + Pop/Hip-Hop), choose the genre that best represents the collaboration
4. Popular collaborations between Electronic/Dance and Pop/Hip-Hop artists often result in Pop or Dance-Pop
5. For subgenres, combine relevant subgenres from all artists that fit with the chosen main genre
6. Return format: "Genre|Subgenres" (e.g., "Pop|Dance-Pop, Latin Pop" or just "Pop|" if no relevant subgenres)

Best genre and subgenres for this collaboration:"""

                    try:
                        ai_response = self.utility_tools._query_llm(genre_analysis_prompt, "analyze_collaboration_genre").strip()
                        # Clean up the response - remove markdown formatting and extra content
                        ai_response = ai_response.split('\n')[0].strip()
                        # Remove markdown formatting (bold, italic, etc.)
                        ai_response = ai_response.replace('**', '').replace('*', '').replace('_', '')
                        # Remove any quotes or other formatting
                        ai_response = ai_response.replace('"', '').replace("'", "").strip()

                        # Parse the response
                        if '|' in ai_response:
                            best_genre, best_subgenres = ai_response.split('|', 1)
                            best_genre = best_genre.strip()
                            best_subgenres = best_subgenres.strip()
                        else:
                            best_genre = ai_response
                            best_subgenres = ""

                        if best_genre and best_genre != "No Genre":
                            final_metadata['genre'] = best_genre
                            final_metadata['comments'] = best_subgenres if best_subgenres else ""
                            print(f"AI determined best genre from multiple artists: {best_genre}")
                            if best_subgenres:
                                print(f"AI determined best subgenres: {best_subgenres}")
                            print("Skipping song-level genre detection - multi-artist analysis complete")
                        else:
                            raise Exception("AI returned invalid genre")
                    except Exception as e:
                        print(f"Error in AI genre analysis: {e}, falling back to main artist genre")
                        # Fallback to main artist genre
                        if all_artist_genres:
                            artist_genre, artist_subgenres = all_artist_genres[0]['genre'], all_artist_genres[0]['subgenres']
                            final_metadata['genre'] = artist_genre
                            final_metadata['comments'] = artist_subgenres
                            print(f"Using main artist genre as fallback: {artist_genre}")
                            print("Skipping song-level genre detection - fallback genre applied")
                        else:
                            print("No artist genres found, proceeding to song-level detection")
                elif len(all_artist_genres) == 1:
                    # Single artist or only main artist has genre data
                    artist_genre, artist_subgenres = all_artist_genres[0]['genre'], all_artist_genres[0]['subgenres']
                    final_metadata['genre'] = artist_genre
                    # Only set comments if there are actual subgenres
                    if artist_subgenres and artist_subgenres.strip():
                        final_metadata['comments'] = artist_subgenres
                    print(f"Using single artist genre: {artist_genre}")
                    print("Skipping song-level genre detection - artist genres found")

                # Only proceed to song-level detection if no artist genres were found
                if not all_artist_genres or 'genre' not in final_metadata:
                    # Fallback to song-level genre detection
                    print("No reliable artist genres found, falling back to song-level detection")
                    
                    # Strategic Genre Detection: Use AI when MusicBrainz is unreliable
                    mb_genre = ""
                    mb_subgenres = ""
                    mb_has_reliable_genre = False
                    
                    if isinstance(musicbrainz_metadata, dict):
                        mb_genre = musicbrainz_metadata.get('genre', '')
                        mb_subgenres = musicbrainz_metadata.get('comments', '')
                        
                        # Check if MusicBrainz genre is reliable
                        if mb_genre and mb_genre != "No Genre" and mb_genre.strip():
                            # Consider MusicBrainz unreliable if it's too generic or commonly wrong
                            unreliable_mb_genres = [
                                "popular music", "pop music", "music", "general", 
                                "contemporary", "modern", "various", "miscellaneous",
                                "other", "unknown", "unclassified"
                            ]
                            
                            if mb_genre.lower().strip() not in unreliable_mb_genres:
                                mb_has_reliable_genre = True
                                print(f"MusicBrainz provided reliable genre: {mb_genre}")
                            else:
                                print(f"MusicBrainz genre '{mb_genre}' considered unreliable, will use AI")
                    
                    # Use AI in two cases: No MusicBrainz genre OR unreliable MusicBrainz genre
                    use_ai_genre = not mb_has_reliable_genre
                    
                    if use_ai_genre:
                        print(f"Using AI for genre detection: {artist_for_genre} - {title_for_genre}")
                        ai_genre_result = self.genre_finder.get_artist_genre_from_ai(
                            artist_for_genre, title_for_genre
                        )
                        
                        if ai_genre_result and ai_genre_result.get('genre') != "No Genre" and ai_genre_result.get('conf', 0) >= 70:
                            final_metadata['genre'] = ai_genre_result['genre']
                            final_metadata['comments'] = ', '.join(ai_genre_result.get('subs', []))
                            print(f"Using AI genre (confidence: {ai_genre_result.get('conf', 0)}%) - Genre: {final_metadata['genre']}, Subgenres: {final_metadata['comments']}")
                        elif mb_has_reliable_genre:
                            # Fallback to MusicBrainz if AI fails but we have something from MB
                            final_metadata['genre'] = mb_genre
                            final_metadata['comments'] = mb_subgenres
                            print(f"AI failed, falling back to MusicBrainz - Genre: {mb_genre}, Subgenres: {mb_subgenres}")
                        else:
                            print("Both AI and MusicBrainz failed to provide reliable genre")
                            final_metadata['genre'] = "No Genre"
                            final_metadata['comments'] = ""
                    else:
                        # Use reliable MusicBrainz genre with conflict resolution
                        resolved_genre = self.utility_tools.resolve_genre_conflicts(mb_genre, mb_subgenres)
                        final_metadata['genre'] = resolved_genre
                        final_metadata['comments'] = mb_subgenres
                        print(f"Using reliable MusicBrainz genre - Original: {mb_genre}, Resolved: {resolved_genre}, Subgenres: {mb_subgenres}")
                
                # Log key metadata fields without dumping raw API data
                metadata_summary = {k: v for k, v in final_metadata.items() 
                                   if k in ['artist', 'title', 'album', 'year', 'genre', 'comments']}
                print(f"Final combined metadata: {metadata_summary}")
                return self.save_metadata_to_file(
                    audio, file_path, artist_name, simplified_title, # original_artist_name, original_title for cache key
                    final_metadata, selected_fields
                )

            print("No metadata found from any source after all checks.")
            return False
        except Exception as e:
            import traceback
            print(f"Error updating metadata: {e}\n{traceback.format_exc()}")
            # self.update_status_label(f"Error updating metadata: {e}") # If this is a GUI app
            return False

    def is_valid_year(self, year):
        """Check if a year is valid (between 1900 and 2000)."""
        try:
            year_int = int(year) if year else 0
            return 1900 <= year_int <= 2000
        except (ValueError, TypeError):
            return False

    def start_update_thread(self, selected_fields=None):
        """Start the processing thread with enhanced progress tracking."""
        try:
            if not self.selected_files:
                self.update_status_label("No files selected.")
                return

            # Check license
            can_process, message = self.license_manager.can_process_files(len(self.selected_files))
            if not can_process:
                self.update_status_label(message)
                return

            # Initialize
            self.total_files_count = len(self.selected_files)
            self.processed_files_count = 0
            self.error_files_count = 0
            
            # Reset UI
            self.ui_elements.progress_bar.setValue(0)
            self.update_status_label("Preparing to process files...")
            self.update_current_file_label("Initializing...")

            if not self.processing_thread or not self.processing_thread.isRunning():
                self.processing_thread = ProcessingThread(self, selected_fields)
                
                # Connect all signals
                self.processing_thread.progress.connect(self.ui_elements.progress_bar.setValue)
                self.processing_thread.status.connect(self.update_status_label)
                self.processing_thread.current_file.connect(self.update_current_file_label)
                self.processing_thread.finished.connect(self.on_processing_finished)
                self.processing_thread.error.connect(self.on_processing_error)
                self.processing_thread.file_completed.connect(self.on_file_completed)
                
                self.disable_ui_components()
                self.processing_thread.start()
            else:
                self.update_status_label("Processing is already running.")
                
        except Exception as e:
            self.update_status_label(f"Error starting update thread: {e}")

    @pyqtSlot(int, int, int)

    def on_file_completed(self, current_index, successful, errors):
        """Handle completion of individual files."""
        # Update license banner periodically (every 5 files or so)
        if current_index % 5 == 0:
            self.ui_elements.license_banner.update_status()
        
        # Could add more per-file completion logic here if needed
        pass

    def update_filenames(self):
        """Update filenames with proper progress tracking."""
        if not self.selected_files:
            self.update_status_label("No files selected.")
            return

        def update_and_clear():
            try:
                total_files = len(self.selected_files)
                success_count = 0
                error_count = 0
                
                # Reset progress bar
                self.ui_elements.progress_bar.setValue(0)
                
                for index, file_path in enumerate(self.selected_files):
                    try:
                        # Update current file label
                        filename = os.path.basename(file_path)
                        self.update_current_file_label(f"Renaming: {filename}")
                        
                        # Update progress
                        progress = int((index / total_files) * 100)
                        self.ui_elements.progress_bar.setValue(progress)
                        
                        # Update status
                        self.update_status_label(f"Renaming {index + 1} of {total_files} files...")
                        
                        new_path = self.rename_file(file_path)
                        if new_path and new_path != file_path:
                            success_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        error_msg = f"Error renaming {os.path.basename(file_path)}: {e}"
                        print(error_msg)

                # Final updates
                self.ui_elements.progress_bar.setValue(100)
                self.update_current_file_label("Ready To Process Files")
                self.update_status_label(
                    f"Filename update complete. Success: {success_count}, Errors: {error_count}"
                )
                
                # Clear selected files and disable UI
                self.selected_files = []
                self.disable_ui_components()
                
            except Exception as e:
                self.update_status_label(f"Error during filename update: {e}")
                self.enable_ui_components()

        # Disable UI during processing
        self.disable_ui_components()
        
        # Run in separate thread to avoid blocking UI
        threading.Thread(target=update_and_clear, daemon=True).start()

    @pyqtSlot()

    def rename_file(self, file_path):
        metadata = self.utility_tools.get_metadata(self.utility_tools.load_audio_file(file_path))
        artist = metadata.get('artist', 'Unknown Artist')
        title = metadata.get('title', 'Unknown Title')

        if artist and title:
            sanitized_artist = self.utility_tools.sanitize_filename(artist)
            sanitized_title = self.utility_tools.sanitize_filename(title)
            new_name = f"{sanitized_artist} - {sanitized_title}{os.path.splitext(file_path)[1]}"
            new_name = self.utility_tools.truncate_filename(new_name, MAX_FILENAME_LENGTH)
            new_name = self.utility_tools.generate_unique_filename(os.path.dirname(file_path), new_name)
            new_path = os.path.join(os.path.dirname(file_path), new_name)
            os.rename(file_path, new_path)
            return new_path
        return file_path

    def save_metadata_to_file(self, audio, file_path, artist_name, simplified_title, new_metadata, selected_fields=None):
        try:
            # Verify we have metadata to work with
            if not new_metadata:
                print("No metadata available to save")
                return False

            print("\n--- Metadata Saving Debug ---")
            print(f"New Metadata: {new_metadata}")
            print(f"Selected Fields: {selected_fields}")

            # Get existing metadata from audio file
            existing_metadata = self.utility_tools.get_metadata(audio) or {}
            print(f"Existing Metadata: {existing_metadata}")

            # Create final metadata dict by combining existing and new metadata
            final_metadata = existing_metadata.copy()  # Start with existing metadata

            # Only update the selected fields
            if selected_fields:
                print(f"Updating only selected fields: {selected_fields}")
                for field in selected_fields:
                    if field in new_metadata:
                        final_metadata[field] = new_metadata[field]
                        print(f"Updated {field}: {new_metadata[field]}")
                    else:
                        print(f"Field {field} not found in new metadata")
            else:
                # If no fields selected, update all fields (shouldn't happen with UI)
                final_metadata.update(new_metadata)

            print("Final Metadata to Save:")
            for key, value in final_metadata.items():
                print(f"{key}: {value}")

            # Save to cache manager
            self.cache_manager.set_metadata(artist_name, simplified_title, final_metadata)

            # Attempt to write metadata to file
            success = self.utility_tools.set_metadata(audio, final_metadata)
            
            if success:
                print(f"Successfully updated metadata for: {file_path}")
                return True
            else:
                print(f"Failed to update metadata for: {file_path}")
                return False

        except Exception as e:
            print(f"Error in save_metadata_to_file: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_status_label(self, message):
        """Update the bottom status label"""
        self.ui_elements.status_label.setText(message)
        print(f"Status Update: {message}")

    def update_current_file_label(self, message):
        """Update the top status label"""
        self.ui_elements.current_file_label.setText(message)

    def enable_ui_components(self):
        """Enable UI components after processing."""
        self.ui_elements.update_tags_btn.setEnabled(True)
        self.ui_elements.update_filenames_btn.setEnabled(True)
        self.ui_elements.reset_app_btn.setEnabled(True)
        self.ui_elements.select_files_btn.setEnabled(True)

    def disable_ui_components(self):
        """Disable UI components during processing."""
        self.ui_elements.update_tags_btn.setEnabled(False)
        self.ui_elements.update_filenames_btn.setEnabled(False)
        self.ui_elements.reset_app_btn.setEnabled(True)  # Keep reset enabled
        self.ui_elements.select_files_btn.setEnabled(False)

    def request_cancel(self):
        """Request cancellation of current processing."""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.cancel_requested = True
            self.ui_elements.status_label.setText("Cancellation requested...")
            self.ui_elements.progress_bar.setValue(0)  # Reset progress
        else:
            # If no thread running, just reset the app
            self.reset_application()

    def reset_application(self):
        """Reset the application state."""
        # Cancel any running threads
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.cancel_requested = True
            self.processing_thread.wait(5000)  # Wait up to 5 seconds for thread to finish

        # Clear caches
        self.cache_manager.clear()
        
        # Reset state
        self.selected_files = []
        self.unfound_files = []
        
        # Reset UI
        self.ui_elements.current_file_label.setText("Ready To Process Files")
        self.ui_elements.status_label.setText("Select an MP3 or M4A file to update metadata.")
        self.ui_elements.progress_bar.setValue(0)  # Reset progress bar
        
        # Disable buttons
        self.disable_ui_components()
