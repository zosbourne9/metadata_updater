import musicbrainzngs
import time
import re
import json
import random
from datetime import datetime, timedelta
from hf_llm_utils import HFLLMUtilities
from labelmanager import LabelManager
from spotify_integration import SpotifyIntegration
from typing import Optional, Dict
from rate_limiter import UnifiedRateLimiter

class RateLimiter:
    def __init__(self, calls_per_second=1):
        self.calls_per_second = calls_per_second
        self.last_call_time = None
        
    def wait_if_needed(self):
        current_time = datetime.now()
        
        if self.last_call_time is not None:
            elapsed = current_time - self.last_call_time
            required_gap = timedelta(seconds=(1.0 / self.calls_per_second))
            
            if elapsed < required_gap:
                sleep_time = (required_gap - elapsed).total_seconds()
                time.sleep(sleep_time)
        
        self.last_call_time = datetime.now()

class MusicBrainzIntegration:
    def __init__(self, parent=None, status_update_callback=None, artist_normalizer=None, cache_manager=None):
        self.parent = parent  # Store parent for dialog positioning
        self.cache_manager = cache_manager
        
        # Initialize dialog handler
        from dialog_handler import DialogHandler
        self.dialog_handler = DialogHandler.instance(parent)
        
        # Store callback for status updates
        self.status_update_callback = status_update_callback

        musicbrainzngs.set_useragent("MetadataUpdaterApp", "1.0", "info@djzrex.com")
        self.utility_tools = HFLLMUtilities()

        self.label_manager = LabelManager()
        self.spotify_integration = SpotifyIntegration()
        self.artist_normalizer = artist_normalizer

        try:
            # Import the resource path helper
            from resource_path import get_resource_path
            
            # Load genre characteristics using resource path
            characteristics_path = get_resource_path('genre_characteristics.json')
            print(f"Loading genre characteristics in MusicBrainz from: {characteristics_path}")
            
            with open(characteristics_path, 'r') as f:
                self.genre_characteristics = json.load(f)
        except Exception as e:
            print(f"Error loading genre characteristics in MusicBrainz: {e}")
            self.genre_characteristics = {}

        # Initialize API call counter and rate limiting
        self.api_call_count = 0
        self.rate_limiter = UnifiedRateLimiter()
        self.consecutive_calls = 0
        self.last_call_time = None
        self.max_year_check_attempts = 5
        
        # Clear the cache on startup
        self.clear_cache()

    def handle_error(self, error_message):
        """Handle errors using thread-safe dialog."""
        self.emit_status(error_message)
        self.dialog_handler.show_error(error_message)

    def emit_status(self, message):
        """Emit status update through callback."""
        if self.status_update_callback:
            self.status_update_callback(message)
        else:
            print(message)

    def show_error_dialog(self, message, title="Error"):
        """Show error dialog via callback."""
        if self.status_update_callback:
            self.status_update_callback(f"{title}: {message}")
        else:
            print(f"{title}: {message}")

    def handle_musicbrainz_api_call(self, func, *args, **kwargs):
        """Handle MusicBrainz API calls with unified rate limiting."""
        max_retries = 3
        base_delay = 5
        max_delay = 30
        retries = 0

        while retries < max_retries:
            try:
                # Use unified rate limiter instead of custom logic
                self.rate_limiter.wait_if_needed('musicbrainz')
                
                # Make the actual API call
                response = func(*args, **kwargs)
                self.api_call_count += 1
                return response

            except Exception as e:
                retries += 1
                error_msg = f"Error in MusicBrainz API call: {e}"
                self.emit_status(error_msg)
                
                if retries == max_retries:
                    print(f"Failed after {max_retries} attempts")
                    return None
                    
                # Exponential backoff with jitter
                delay = min(base_delay * (2 ** (retries - 1)), max_delay)
                print(f"Retrying in {delay:.2f} seconds...")
                time.sleep(delay)

        return None

    def clear_cache(self):
        if self.cache_manager:
            self.cache_manager.clear('musicbrainz')

    def find_best_match(self, recordings, artist_name, track_title, handle_remixes=False):
        print(f"\nFinding best match for: {artist_name} - {track_title}")
        print(f"DEBUG: Total recordings to evaluate: {len(recordings)}")

        best_recording = None
        best_score = 0

        # Normalize the search title
        search_title = self.utility_tools.clean_track_title(track_title).lower()
        search_title_base = re.sub(r'\s*[\(\[](12\s*(?:inch|"|\')|extended|remix|version).*?[\)\]]', '', search_title)
        is_12_inch = '12' in track_title.lower() and any(x in track_title.lower() for x in ['inch', '"', "'"])

        # Track whether we're looking for a remix
        is_remix_search = 'remix' in track_title.lower()
        remix_matches = []
        non_remix_matches = []

        perfect_matches = []  # Track perfect matches for early return
        processed_count = 0
        max_recordings_to_process = 50  # Limit processing for efficiency
        
        for idx, recording in enumerate(recordings):
            processed_count += 1
            
            # Early exit if we've processed enough recordings and have a decent match
            if processed_count > max_recordings_to_process and best_score > 500:
                print(f"EARLY EXIT: Processed {processed_count} recordings, best score: {best_score}")
                break
            try:
                if 'artist-credit' not in recording or 'title' not in recording:
                    continue

                recording_artists = [self.utility_tools.clean_string(artist['artist']['name']) 
                                for artist in recording['artist-credit'] 
                                if isinstance(artist, dict) and 'artist' in artist]
                
                recording_title = self.utility_tools.clean_string(recording['title'])

                if 'instrumental' in recording_title.lower():
                    print(f"Skipping instrumental release: {recording_title}")
                    continue
                
                # Initialize base score
                base_score = 0
                
                # Initialize score
                total_score = 0

                for release in recording.get('release-list', []):
                    if release.get('primary-type') == 'album' and 'compilation' not in str(release).lower():
                        # Do additional checks to confirm it's likely the original album
                        return recording

                # Artist match (highest priority) - OPTIMIZED VERSION
                if not recording_artists:  # Handle empty artist list
                    print(f"DEBUG: Skipping recording with no artists")
                    continue
                
                print(f"DEBUG: Recording artists: {recording_artists}")
                print(f"DEBUG: Search artist: {artist_name}")
                
                # Check for exact artist match first (fast path)
                exact_match_found = False
                artist_match_score = 0
                for artist in recording_artists:
                    if artist.lower().strip() == artist_name.lower().strip():
                        artist_match_score = 100
                        exact_match_found = True
                        print(f"DEBUG: EXACT artist match found: {artist}")
                        break
                
                # If no exact match, use optimized fuzzy matching
                if not exact_match_found:
                    best_artist, artist_match_score = self.utility_tools.optimized_fuzzy_match(
                        artist_name, 
                        recording_artists, 
                        threshold=80,
                        pre_filter_threshold=30
                    )
                    print(f"DEBUG: Best fuzzy match: {best_artist} (score: {artist_match_score})")
                
                if artist_match_score < 80:  # Must be a good artist match
                    print(f"DEBUG: Artist match too low ({artist_match_score}), skipping")
                    continue
                
                # Early exit for perfect artist match + exact title match (but not remixes/live versions)
                recording_title_clean = recording_title.lower().strip()
                search_title_clean = search_title.lower().strip()
                
                # Check for exact title match and make sure it's not a remix/live version
                is_exact_title_match = recording_title_clean == search_title_clean
                is_remix_or_live = any(keyword in recording_title_clean for keyword in ['remix', 'live', 'edit', 'version', 'cover'])
                
                if artist_match_score >= 95 and is_exact_title_match and not is_remix_or_live:
                    # Check if this appears on a proper studio album release
                    has_studio_release = False
                    if 'release-list' in recording:
                        for release in recording['release-list']:
                            release_title = release.get('title', '').lower()
                            # Skip live albums, compilations, and other non-studio releases
                            if not any(bad in release_title for bad in ['live', 'compilation', 'mixtape', 'remix', 'greatest', 'best of']):
                                has_studio_release = True
                                break
                    
                    if has_studio_release:
                        print(f"EARLY EXIT: Perfect studio release match found - Artist: 100%, Title: {recording_title}")
                        return recording
                    else:
                        print(f"EXACT match found but not studio release: {recording_title} - continuing search")
                
                total_score += artist_match_score * 2

                # Title matching logic
                recording_title_base = re.sub(r'\s*[\(\[](12\s*(?:inch|"|\')|extended|remix|version).*?[\)\]]', '', recording_title)
                
                # Different title match scenarios
                exact_match = recording_title.lower().strip() == search_title.strip()
                base_match = recording_title_base.lower().strip() == search_title_base.strip()
                version_match = is_12_inch and ('12' in recording_title.lower() and 
                                            any(x in recording_title.lower() for x in ['inch', '"', "'"]))
                
                # Calculate title score
                if exact_match:
                    total_score += 100
                elif base_match and version_match:
                    total_score += 90
                elif base_match:
                    total_score += 80
                else:
                    title_match_score = self.utility_tools.fuzzy_match(search_title, recording_title)
                    if title_match_score < 70:
                        continue
                    total_score += title_match_score

                # Release information scoring
                if 'release-list' in recording:
                    for release in recording['release-list']:
                        release_score = 0
                        
                        # Heavy bonus for matching album name
                        album_name = release.get('title', '').lower()
                        if self.utility_tools.fuzzy_match(track_title, album_name) >= 85:
                            release_score += 300
                        
                        # Check release date - prioritize earlier releases
                        if 'date' in release and release['date']:
                            try:
                                year = int(release['date'][:4])
                                if 1900 < year < 2000:  # Bonus for older releases
                                    release_score += (2000 - year) * 2  # More points for earlier years
                            except (ValueError, TypeError):
                                pass
                        
                        # Bonus for being an album or single
                        if 'release-group' in release:
                            release_group = release['release-group']
                            primary_type = release_group.get('primary-type', '').lower()
                            if primary_type in ['album', 'single']:
                                release_score += 100
                        
                        # Handle remixes
                        if handle_remixes:
                            is_remix_result = 'remix' in recording_title.lower()
                            if is_remix_result:
                                remix_matches.append((recording, base_score + release_score, artist_match_score))
                            else:
                                non_remix_matches.append((recording, base_score + release_score, artist_match_score))
                            continue

                        # Combine scores
                        total_score = base_score + release_score

                        if total_score > best_score:
                            best_score = total_score
                            best_recording = recording
                            print(f"New best match! Score: {total_score}")
                            
                            # Track perfect matches (high artist + title match)
                            if artist_match_score >= 95 and (exact_match or base_match):
                                perfect_matches.append((recording, total_score))
                                print(f"Perfect match found! Artist: {artist_match_score}%, Title match: {exact_match or base_match}")
                                
                                # Early return for multiple perfect matches or very high score
                                if len(perfect_matches) >= 3 or total_score >= 1000:
                                    print(f"Stopping search early - found {len(perfect_matches)} perfect matches")
                                    return best_recording
                            
                            # Early return for very high scoring matches
                            elif total_score >= 1200:
                                print(f"Stopping search early - exceptional score: {total_score}")
                                return best_recording

            except Exception as e:
                print(f"Error evaluating recording: {e}")
                continue

        # Handle remix scenarios if applicable
        if handle_remixes and (remix_matches or non_remix_matches):
            if is_remix_search and remix_matches:
                best_remix = max(remix_matches, key=lambda x: (x[1], x[2]))
                return best_remix[0]
            elif not is_remix_search and non_remix_matches:
                best_non_remix = max(non_remix_matches, key=lambda x: (x[1], x[2]))
                return best_non_remix[0]

        print(f"DEBUG: find_best_match returning: {best_recording is not None} (score: {best_score})")
        if best_recording:
            print(f"DEBUG: Best match title: {best_recording.get('title', 'N/A')}")
        return best_recording

    def search_recording_metadata(self, recording, original_artist_name):
        """Enhanced metadata processing with better original release selection."""
        try:
            print(f"\nProcessing recording metadata for: {recording.get('title', '')}")
            
            if recording.get('release-list'):
                print("Analyzing releases...")
                preferred_releases = []
                
                for release in recording['release-list']:
                    if not release or not release.get('title'):
                        continue
                    
                    # Extract year - be more thorough
                    year = None
                    if 'date' in release and release['date']:
                        try:
                            # Handle various date formats
                            date_str = release['date']
                            if '-' in date_str:
                                year = int(date_str.split('-')[0])
                            elif len(date_str) >= 4:
                                year = int(date_str[:4])
                            else:
                                year = int(date_str)
                        except (ValueError, TypeError, IndexError):
                            print(f"Could not parse year from date: {release['date']}")
                            continue
                    
                    # Skip releases without valid years
                    if not year or year < 1950 or year > 2030:
                        print(f"Skipping release with invalid/missing year: {release.get('title')} ({release.get('date', 'No date')})")
                        continue
                    
                    # Calculate comprehensive score
                    base_score = self._calculate_release_score(release, original_artist_name)
                    
                    # Only proceed if the release has a decent base score
                    if base_score < 0.3:  # Lowered threshold
                        print(f"Skipping low-scoring release: {release.get('title')} (score: {base_score:.2f})")
                        continue
                    
                    # Additional scoring factors
                    final_score = base_score * 1000  # Scale up for easier comparison
                    
                    # Year-based multipliers - stronger preference for original era
                    if year <= 1990:
                        final_score *= 1.5  # Strong preference for classic era
                        print(f"Classic era multiplier applied: x1.5 for year {year}")
                    elif year <= 2000:
                        final_score *= 1.3  # Good preference for pre-2000
                        print(f"Pre-2000 multiplier applied: x1.3 for year {year}")
                    elif year <= 2010:
                        final_score *= 1.1  # Slight preference for 2000s
                        print(f"2000s multiplier applied: x1.1 for year {year}")
                    else:
                        # Penalty for recent releases (likely reissues/anniversary editions)
                        final_score *= 0.8
                        print(f"Recent release penalty applied: x0.8 for year {year}")
                    
                    # Check if release title matches or is similar to recording title
                    release_title_clean = self.utility_tools.clean_string(release.get('title', ''))
                    recording_title_clean = self.utility_tools.clean_string(recording.get('title', ''))
                    
                    if release_title_clean == recording_title_clean:
                        final_score *= 1.5  # Strong bonus for title match
                        print(f"Exact title match bonus: x1.5")
                    elif self.utility_tools.fuzzy_match(release_title_clean, recording_title_clean) > 80:
                        final_score *= 1.2  # Moderate bonus for similar title
                        print(f"Similar title bonus: x1.2")
                    
                    # Check for anniversary/reissue indicators
                    release_title_lower = release.get('title', '').lower()
                    if any(indicator in release_title_lower for indicator in [
                        'anniversary', 'reissue', 'remaster', 'deluxe', 'expanded', 
                        'special edition', 'collector', '20th', '25th', '30th'
                    ]):
                        final_score *= 0.7  # Penalty for reissues
                        print(f"Reissue penalty applied: x0.7")
                    
                    # Vinyl format bonus for older releases
                    is_vinyl = False
                    if 'medium-list' in release:
                        for medium in release['medium-list']:
                            format_name = medium.get('format', '').lower()
                            if 'vinyl' in format_name:
                                is_vinyl = True
                                if year < 1990:
                                    final_score *= 1.4  # Extra bonus for old vinyl
                                    print(f"Old vinyl bonus: x1.4")
                                elif year < 2000:
                                    final_score *= 1.2  # Moderate bonus for 90s vinyl
                                    print(f"90s vinyl bonus: x1.2")
                                break
                    
                    preferred_releases.append((
                        release, 
                        year,
                        final_score, 
                        is_vinyl, 
                        release.get('title', '')
                    ))
                    
                    print(f"Release scored: '{release.get('title')}' ({year}) = {final_score:.0f}")

                # Select the best release
                if preferred_releases:
                    # Sort by score (descending), then by year (ascending for tie-breaking)
                    preferred_releases.sort(key=lambda x: (-x[2], x[1]))
                    
                    best_release = preferred_releases[0][0]
                    best_year = preferred_releases[0][1]
                    best_score = preferred_releases[0][2]
                    release_title = preferred_releases[0][4]
                    
                    print(f"\n*** SELECTED BEST RELEASE ***")
                    print(f"Title: {release_title}")
                    print(f"Year: {best_year}")
                    print(f"Score: {best_score:.0f}")
                    print(f"*** END SELECTION ***\n")

                    # Handle featured artists
                    main_artist = None
                    featuring_artists = []
                    
                    if 'artist-credit' in recording:
                        artists = recording['artist-credit']
                        
                        for i, artist_credit in enumerate(artists):
                            if isinstance(artist_credit, dict) and 'artist' in artist_credit:
                                artist_name = artist_credit['artist']['name']
                                if i == 0:
                                    main_artist = artist_name
                                else:
                                    featuring_artists.append(artist_name)

                    # Handle featuring dialog
                    final_artist = original_artist_name
                    if featuring_artists:
                        print(f"Found featuring artists: {featuring_artists}")
                        include_features = self.dialog_handler.show_features_dialog(
                            featuring_artists,
                            main_artist or original_artist_name
                        )

                        if include_features:
                            if len(featuring_artists) == 1:
                                final_artist = f"{main_artist} feat. {featuring_artists[0]}"
                            else:
                                features_str = ", ".join(featuring_artists[:-1]) + " & " + featuring_artists[-1]
                                final_artist = f"{main_artist} feat. {features_str}"
                    
                    # Create metadata with the selected year
                    metadata = {
                        'artist': final_artist,
                        'title': recording.get('title', ''),
                        'album': release_title,
                        'year': int(best_year) if best_year else '',
                        'genre': '',
                        'comments': ''
                    }

                    print(f"Generated metadata: {metadata}")
                    return metadata
                        
                print("No releases met minimum quality threshold")
                return None

            print("No release list found in recording")
            return None

        except Exception as e:
            print(f"Error processing recording metadata: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _search_metadata_from_recording(self, recording, artist_name):
        """
        Enhanced method to extract metadata from a recording with better handling of featured artists.
        """
        try:
            print(f"\nProcessing metadata from recording: {recording.get('title', '')}")
            
            # Get best release using _score_release
            best_release = None
            best_score = -1
            
            if recording.get('release-list'):
                for release in recording['release-list']:
                    score = self._score_release(release, artist_name)
                    if score > best_score:
                        best_score = score
                        best_release = release
                        
            if not best_release:
                print("No suitable release found")
                return None
                
            # Extract metadata using existing helper
            return self._extract_metadata(recording, best_release)
            
        except Exception as e:
            print(f"Error extracting metadata from recording: {e}")
            return None

    def _extract_metadata(self, recording: dict, release: dict) -> Optional[dict]:
        """Extract metadata from the best recording/release match with featured artists handling."""
        try:
            # Extract genre and tag information from MusicBrainz
            genre, subgenres = self._extract_genre_from_mb_data(recording, release)
            
            # Handle featured artists properly
            main_artist = None
            featuring_artists = []
            
            if 'artist-credit' in recording:
                artists = recording['artist-credit']
                
                for i, artist_credit in enumerate(artists):
                    if isinstance(artist_credit, dict) and 'artist' in artist_credit:
                        artist_name = artist_credit['artist']['name']
                        if i == 0:
                            main_artist = artist_name
                        else:
                            featuring_artists.append(artist_name)
            
            # Start with main artist
            final_artist = main_artist or (recording['artist-credit'][0]['artist']['name'] if recording.get('artist-credit') else '')
            
            # Handle featuring dialog if we found featuring artists
            if featuring_artists:
                print(f"Found featuring artists in MusicBrainz: {featuring_artists}")
                include_features = self.dialog_handler.show_features_dialog(
                    featuring_artists,
                    main_artist or final_artist
                )

                if include_features:
                    if len(featuring_artists) == 1:
                        final_artist = f"{main_artist} feat. {featuring_artists[0]}"
                    else:
                        features_str = ", ".join(featuring_artists[:-1]) + " & " + featuring_artists[-1]
                        final_artist = f"{main_artist} feat. {features_str}"
            
            metadata = {
                'title': recording.get('title', ''),
                'artist': final_artist,
                'album': release.get('title', ''),
                'year': release.get('date', '')[:4] if release.get('date') else '',
                'genre': genre,
                'comments': subgenres
            }
            
            print(f"Extracted metadata from MusicBrainz:")
            print(f"Title: {metadata['title']}")
            print(f"Artist: {metadata['artist']}")
            print(f"Album: {metadata['album']}")
            print(f"Year: {metadata['year']}")
            print(f"Genre: {metadata['genre']}")
            print(f"Subgenres: {metadata['comments']}")
            
            return metadata
            
        except Exception as e:
            print(f"Error extracting metadata: {e}")
            return None

    def _extract_genre_from_mb_data(self, recording: dict, release: dict) -> tuple:
        """Extract genre information from MusicBrainz recording and release data."""
        try:
            genre_tags = []
            
            # Get recording ID and fetch tags separately
            recording_id = recording.get('id')
            if recording_id:
                print(f"Fetching tags for recording ID: {recording_id}")
                try:
                    recording_with_tags = self.handle_musicbrainz_api_call(
                        musicbrainzngs.get_recording_by_id,
                        recording_id,
                        includes=['tags']
                    )
                    if recording_with_tags and recording_with_tags.get('recording', {}).get('tag-list'):
                        for tag in recording_with_tags['recording']['tag-list']:
                            if tag.get('name'):
                                tag_name = tag['name'].lower()
                                count = int(tag.get('count', 0))
                                if count > 0:
                                    genre_tags.append((tag_name, count))
                except Exception as e:
                    print(f"Error fetching recording tags: {e}")
            
            # Get release ID and fetch tags separately
            release_id = release.get('id')
            if release_id:
                print(f"Fetching tags for release ID: {release_id}")
                try:
                    release_with_tags = self.handle_musicbrainz_api_call(
                        musicbrainzngs.get_release_by_id,
                        release_id,
                        includes=['tags', 'release-groups']
                    )
                    if release_with_tags and release_with_tags.get('release', {}).get('tag-list'):
                        for tag in release_with_tags['release']['tag-list']:
                            if tag.get('name'):
                                tag_name = tag['name'].lower()
                                count = int(tag.get('count', 0))
                                if count > 0:
                                    genre_tags.append((tag_name, count))
                    
                    # Also get release group tags
                    release_group = release_with_tags.get('release', {}).get('release-group')
                    if release_group and release_group.get('tag-list'):
                        for tag in release_group['tag-list']:
                            if tag.get('name'):
                                tag_name = tag['name'].lower()
                                count = int(tag.get('count', 0))
                                if count > 0:
                                    genre_tags.append((tag_name, count))
                except Exception as e:
                    print(f"Error fetching release tags: {e}")
            
            if not genre_tags:
                print("No genre tags found in MusicBrainz data")
                return '', ''
            
            # Sort tags by count (popularity) and clean them
            genre_tags.sort(key=lambda x: x[1], reverse=True)
            print(f"Found MusicBrainz tags: {genre_tags[:10]}")  # Show top 10
            
            # Process tags to find primary genre and subgenres
            primary_genre, subgenres = self._process_mb_tags(genre_tags)
            
            return primary_genre, ', '.join(subgenres) if subgenres else ''
            
        except Exception as e:
            print(f"Error extracting genre from MusicBrainz data: {e}")
            return '', ''

    def _process_mb_tags(self, genre_tags: list) -> tuple:
        """Process MusicBrainz tags to determine primary genre and subgenres."""
        try:
            # Define genre mappings for common MusicBrainz tags
            genre_mappings = {
                'hip hop': 'Hip-Hop',
                'hip-hop': 'Hip-Hop',
                'rap': 'Hip-Hop',
                'trap': 'Hip-Hop',
                'r&b': 'R&B',
                'rnb': 'R&B',
                'rhythm and blues': 'R&B',
                'contemporary r&b': 'R&B',
                'soul': 'Soul',  # Keep soul separate from R&B
                'pop': 'Pop',
                'pop music': 'Pop',
                'rock': 'Rock',
                'reggae': 'Reggae',
                'dancehall': 'Dancehall',
                'soca': 'Soca',
                'afrobeats': 'Afrobeats',
                'afrobeat': 'Afrobeats',
                'funk': 'Funk',
                'disco': 'Disco',
                'electronic': 'Electronic',
                'house': 'Electronic',
                'techno': 'Electronic',
                'jazz': 'Jazz',
                'blues': 'Blues',
                'country': 'Country',
                'folk': 'Folk',
                'alternative': 'Alternative',
                'indie': 'Alternative',
                'metal': 'Metal',
                'punk': 'Punk'
            }
            
            primary_genre = ''
            subgenres = set()  # Use set to avoid duplicates
            
            # Look for the highest-weighted genre tag that maps to our categories
            for tag_name, count in genre_tags:
                if tag_name in genre_mappings and not primary_genre:
                    primary_genre = genre_mappings[tag_name]
                elif tag_name in genre_mappings:
                    mapped_genre = genre_mappings[tag_name]
                    if mapped_genre != primary_genre:
                        subgenres.add(mapped_genre)
                        
            # If no primary genre found, try partial matches
            if not primary_genre:
                for tag_name, count in genre_tags:
                    for key, value in genre_mappings.items():
                        if key in tag_name and not primary_genre:
                            primary_genre = value
                            break
                    if primary_genre:
                        break
            
            # Add high-confidence specific subgenres (avoiding duplicates)
            for tag_name, count in genre_tags[:5]:  # Top 5 tags only
                if count > 2:  # Reasonable confidence threshold
                    # Look for specific subgenres that don't map to main genres
                    subgenre_candidates = {
                        'trap': 'Trap',
                        'drill': 'Drill', 
                        'conscious rap': 'Conscious Rap',
                        'gangsta rap': 'Gangsta Rap',
                        'neo soul': 'Neo Soul',
                        'contemporary r&b': 'Contemporary R&B',
                        'smooth jazz': 'Smooth Jazz',
                        'alternative rock': 'Alternative Rock',
                        'indie rock': 'Indie Rock',
                        'hard rock': 'Hard Rock',
                        'deep house': 'Deep House',
                        'progressive house': 'Progressive House',
                        'acid house': 'Acid House'
                    }
                    
                    for candidate, formatted_name in subgenre_candidates.items():
                        if candidate in tag_name or tag_name in candidate:
                            if formatted_name != primary_genre:
                                subgenres.add(formatted_name)
            
            # Convert set back to list and sort for consistency
            subgenres_list = sorted(list(subgenres))[:3]  # Limit to 3 subgenres
            
            print(f"Processed MusicBrainz genres - Primary: {primary_genre}, Subgenres: {subgenres_list}")
            return primary_genre, subgenres_list
            
        except Exception as e:
            print(f"Error processing MusicBrainz tags: {e}")
            return '', []

    def search_recording_with_priority(self, artist_name: str, track_title: str) -> Optional[dict]:
        """
        Enhanced MusicBrainz recording search that prioritizes original releases.
        """
        try:
            print(f"\nSearching for recording: {artist_name} - {track_title}")
            
            # First try exact recording search
            query = f'artist:"{artist_name}" AND recording:"{track_title}"'
            recordings = self.handle_musicbrainz_api_call(
                musicbrainzngs.search_recordings,
                query=query,
                limit=100  # Get more results to find original releases
            )
            
            if not recordings or 'recording-list' not in recordings:
                return None
                
            # Group recordings by their releases
            recording_releases = {}
            for recording in recordings['recording-list']:
                if 'release-list' not in recording:
                    continue
                    
                # Score each release
                scored_releases = []
                for release in recording['release-list']:
                    score = self._score_release(release, artist_name)
                    if score > 0:  # Only keep valid releases
                        scored_releases.append((release, score))
                
                if scored_releases:
                    # Sort releases by score and keep the best one
                    best_release = max(scored_releases, key=lambda x: x[1])
                    recording_releases[recording['id']] = {
                        'recording': recording,
                        'release': best_release[0],
                        'score': best_release[1]
                    }
            
            if not recording_releases:
                return None
                
            # Get the recording with the highest-scored release
            best_recording_id = max(recording_releases.items(), 
                                key=lambda x: x[1]['score'])[0]
            best_match = recording_releases[best_recording_id]
            
            return self._extract_metadata(best_match['recording'], 
                                        best_match['release'])
                                        
        except Exception as e:
            print(f"Error in enhanced recording search: {e}")
            return None

    def _score_release(self, release: dict, artist_name: str) -> float:
        try:
            score = 0.0
            release_title = release.get('title', '').lower()
            release_group = release.get('release-group', {})

            # Immediate rejection patterns for compilations
            compilation_patterns = [
                r'best\s+of', r'\bvybin\b', r'essential', r'collection', r'greatest\s+hits',
                r'anthology', r'presents', r'compilation', r'\bselected\b', r'selected works',
                r'definitive', r'\bgold\b', r'\bsilver\b', r'\bplatinum\b', r'mixtape',
                r'deluxe', r'expanded', r'remastered', r'anniversary', r'complete',
                r'special edition', r'bonus tracks?', r'original classics?', r'\bhits\b',
                r'ultimate', r'singles collection', r'classics', r'rare tracks?',
                r'b-sides', r'unreleased', r'archives?', r'collected', r'bass\s+all-stars?',
                r'streetjam', r'street\s*jam', r'various\s*artists', r'v\.?a\.?', 
                r'sampler', r'promo', r'promotional', r'mix\s*tape', r'dj\s*mix',
                r'radio\s*mix', r'club\s*mix', r'mega\s*mix', r'party\s*mix',
                r'volume\s*\d+', r'vol\s*\.?\s*\d+', r'part\s*\d+', r'chapter\s*\d+',
                r'series\s*\d+', r'edition\s*\d+', r'now\s*\d+', r'now\s*that\'s',
                r'tribute\s*to', r'as\s*heard', r'movie\s*soundtrack', r'film\s*soundtrack',
                r'tv\s*soundtrack', r'original\s*motion', r'ost', r'soundtrack',
                r'dance\s*\d{4}', r'pop\s*\d{4}', r'hits\s*\d{4}', r'music\s*\d{4}',
                r'summer\s*\d{4}', r'winter\s*\d{4}', r'spring\s*\d{4}', r'autumn\s*\d{4}',
                r'party\s*\d{4}', r'club\s*\d{4}', r'radio\s*\d{4}'
            ]
            
            if any(re.search(pattern, release_title) for pattern in compilation_patterns):
                return 0

            # Release type scoring
            primary_type = release_group.get('primary-type', '').lower()
            if primary_type == 'album':
                score += 800  # Strong preference for albums
            elif primary_type == 'single':
                score += 200  # Lower score for singles

            # Check release status
            if release.get('status', '').lower() == 'official':
                score += 300

            # Prioritize original releases by release date
            if 'date' in release and release['date']:
                try:
                    year = int(release['date'][:4])
                    score += 1000 - ((year - 1900) * 2)  # Earlier releases get higher scores
                except (ValueError, TypeError):
                    pass

            # Check for original album indicators
            original_indicators = {
                'vinyl': 300,
                'lp': 300,
                'original': 200,
                'studio album': 400
            }
            for indicator, bonus in original_indicators.items():
                if indicator in release_title:
                    score += bonus

            # Penalty for remix/reissue indicators
            remix_indicators = [
                'remix', 'radio edit', 'extended', 'reissue', 'remaster',
                'live', 'demo', 'single version', 'radio version', 'all stars',
                'volume', 'total dance', 'vol'
            ]
            if any(ind in release_title for ind in remix_indicators):
                score -= 500

            # Check formats
            if 'medium-list' in release:
                for medium in release['medium-list']:
                    format = medium.get('format', '').lower()
                    if format in ['vinyl', '12" vinyl', 'lp']:
                        score += 200
                    elif format == 'cd':
                        score += 100

            # Label quality check
            if 'label-info-list' in release:
                for label_info in release['label-info-list']:
                    if 'label' in label_info and 'name' in label_info['label']:
                        label_name = label_info['label']['name'].lower()
                        if 'compilation' in label_name or 'presents' in label_name:
                            score -= 300

            # Track count check - prefer standard album lengths
            if 'medium-list' in release:
                track_count = sum(len(medium.get('track-list', [])) 
                                for medium in release['medium-list'])
                if 8 <= track_count <= 15:  # Standard album length
                    score += 200
                elif track_count > 20:  # Likely compilation
                    score -= 200

            return max(0.0, score)

        except Exception as e:
            print(f"Error scoring release: {e}")
            return 0.0
        
    def search_metadata(self, artist_name, track_title):
        """
        Enhanced metadata search with better handling of original releases, versions, and featured artists.
        """
        try:           
            # Check cache first
            metadata = self.cache_manager.get_metadata(artist_name, track_title)
            if metadata:
                return metadata

            print(f"\nSearching MusicBrainz for: {artist_name} - {track_title}")

            # Use utility tools to handle featured artists
            processed_artist = self.utility_tools.handle_featured_artists(artist_name)
            print(f"Processed artist name: {processed_artist}")

            # Extract version information and base title
            clean_title = self.utility_tools.clean_track_title(track_title)
            clean_title = re.sub(r'\s*,\s*', ' ', clean_title)  # Remove commas
            clean_title = ' '.join(clean_title.split())  # Normalize spaces
            
            base_title = clean_title
            is_remix = False
            version_info = ""

            # Look for version indicators (remix, clean, dirty, etc.)
            version_patterns = [
                (r'\(remix\)', 'remix'),
                (r'\bremix\b', 'remix'),
                (r'\(.*?mix\)', 'remix'),
                (r'\b.*?mix\b', 'remix'),
                (r'\(clean\)', 'clean'),
                (r'\(dirty\)', 'dirty'),
                (r'\(explicit\)', 'explicit'),
                (r'\(radio\s+version\)', 'radio'),
                (r'\(album\s+version\)', 'album')
            ]

            # Find any version information in the title
            for pattern, version_type in version_patterns:
                match = re.search(pattern, clean_title.lower())
                if match:
                    version_info = match.group(0)
                    # Remove version info for search
                    base_title = re.sub(pattern, '', clean_title, flags=re.IGNORECASE).strip()
                    is_remix = version_type == 'remix'
                    print(f"Detected version: {version_info}")
                    print(f"Base title: {base_title}")
                    break

            # Fallback to traditional search with full artist name
            metadata = self._search_recording_with_fallback(
                artist_name, 
                track_title, 
                base_title=base_title, 
                version_info=version_info, 
                is_remix=is_remix, 
                processed_artist=processed_artist
            )
            if metadata:
                print(f"Metadata found: {metadata}")
                # Cache the metadata before returning
                self.cache_manager.set_metadata(artist_name, track_title, metadata)
                return metadata

            # Try prioritized search first with full artist name
            metadata = self.search_recording_with_priority(artist_name, base_title)
            if metadata:
                # Add back version info if found
                if version_info and metadata.get('title'):
                    metadata['title'] = f"{metadata['title']} {version_info}".strip()
                print(f"Found metadata via prioritized search: {metadata}")
                # Cache the metadata before returning
                self.cache_manager.set_metadata(artist_name, track_title, metadata)
                return metadata

            # If no results, try with main artist only
            main_artist = self.utility_tools.get_main_artist_name(artist_name)
            if main_artist != artist_name:
                print(f"No results, trying with main artist only: {main_artist}")
                
                # Try prioritized search with main artist
                metadata = self.search_recording_with_priority(main_artist, base_title)
                if metadata:
                    if version_info and metadata.get('title'):
                        metadata['title'] = f"{metadata['title']} {version_info}".strip()
                    # Cache the metadata before returning
                    self.cache_manager.set_metadata(artist_name, track_title, metadata)
                    return metadata
                    
                # Final fallback with main artist
                metadata = self._search_recording_with_fallback(
                    main_artist, 
                    track_title, 
                    base_title=base_title, 
                    version_info=version_info, 
                    is_remix=is_remix, 
                    processed_artist=processed_artist
                )
                if metadata:
                    # Cache the metadata before returning
                    self.cache_manager.set_metadata(artist_name, track_title, metadata)
                return metadata

            return None

        except Exception as e:
            print(f"Error in MusicBrainz search_metadata: {e}")
            return None

    def _search_recording_with_fallback(self, artist_name, track_title, base_title=None, version_info=None, is_remix=False, processed_artist=None):
        """
        Internal method to search for recordings with multiple fallback strategies.
        
        Args:
            artist_name (str): Original artist name
            track_title (str): Original track title
            base_title (str, optional): Cleaned base title without version info
            version_info (str, optional): Version information (e.g., remix, clean version)
            is_remix (bool, optional): Flag to indicate if it's a remix search
            processed_artist (str, optional): Processed artist name
        
        Returns:
            dict or None: Metadata dictionary if found, None otherwise
        """
        try:
            # If base_title is not provided, clean the track title
            if base_title is None:
                base_title = self.utility_tools.clean_track_title(track_title)

            print("\n===== DETAILED MUSICBRAINZ SEARCH DEBUGGING =====")
            print(f"Original Artist: {artist_name}")
            print(f"Processed Artist: {processed_artist}")
            print(f"Track Title: {track_title}")
            print(f"Base Title: {base_title}")
            print(f"Is Remix: {is_remix}")
            print(f"Version Info: {version_info}")

            # Get main artist and possible featured artists
            main_artist = self.utility_tools.get_main_artist_name(artist_name)
            featured_artists = self.utility_tools.handle_featured_artists(artist_name)
            
            # Ensure processed_artist is set
            processed_artist = processed_artist or featured_artists or artist_name

            # Search strategy with fallback to featured artists
            search_artists = [main_artist] + (featured_artists.split(',') if isinstance(featured_artists, str) else [])

            for current_artist in search_artists:
                print(f"\n--- Attempting search with artist: {current_artist} ---")
                
                # First try: Search recordings (more accurate than releases)
                query = f'artist:"{current_artist}" AND recording:"{base_title}"'
                print(f"Recording Search Query: {query}")
                
                recordings = self.handle_musicbrainz_api_call(
                    musicbrainzngs.search_recordings,
                    query=query,
                    limit=50
                )

                # Process recordings directly
                if recordings and 'recording-list' in recordings:
                    print(f"Total Recordings Found: {len(recordings['recording-list'])}")
                    
                    # Print out detailed recording information
                    for idx, recording in enumerate(recordings['recording-list'], 1):
                        print(f"\nRecording {idx}:")
                        print(f"Title: {recording.get('title', 'N/A')}")
                        
                        # Print artists
                        if 'artist-credit' in recording:
                            artists = [artist['artist']['name'] for artist in recording['artist-credit'] if isinstance(artist, dict) and 'artist' in artist]
                            print(f"Artists: {artists}")
                        
                        # Print releases this recording appears on
                        if 'release-list' in recording:
                            releases = []
                            for release in recording['release-list'][:3]:  # Show first 3 releases
                                date = release.get('date', 'N/A')
                                releases.append(f"{release.get('title', 'N/A')} ({date})")
                            print(f"Releases: {releases}")

                    # Find best match considering remix status
                    best_recording = self.find_best_match(
                        recordings['recording-list'],
                        current_artist,
                        base_title,
                        handle_remixes=is_remix
                    )

                    if best_recording:
                        # Extract metadata from recording
                        earliest_year, earliest_release = self.get_release_year(best_recording)
                        if earliest_release is not None:
                            # If it's not unwanted (compilation, remix, etc.)
                            if not self.is_unwanted_release_type(earliest_release):
                                # Check how “good” the release is
                                release_score = self._calculate_release_score(earliest_release, current_artist)
                                if release_score > 0.5:
                                    # Use the alternative metadata extraction approach
                                    metadata = self._search_metadata_from_recording(best_recording, processed_artist)
                                    
                                    if metadata:
                                        # Restore version info in the title if present
                                        if version_info and metadata.get('title'):
                                            metadata['title'] = f"{metadata['title']} {version_info}".strip()
                                        return metadata
                                    else:
                                        # Fallback to your existing method
                                        metadata = self.search_recording_metadata(best_recording, processed_artist)
                                        if metadata and version_info and metadata.get('title'):
                                            metadata['title'] = f"{metadata['title']} {version_info}".strip()
                                        return metadata
                                else:
                                    print("Release did not pass the minimum score threshold.")
                            else:
                                print("Earliest release was deemed unwanted (e.g. compilation, live, etc.).")
                        metadata = self.search_recording_metadata(best_recording, processed_artist)
                        
                        if metadata:
                            # Restore version information in the title
                            if version_info and metadata.get('title'):
                                metadata['title'] = f"{metadata['title']} {version_info}".strip()

                            return metadata

                # Fallback: try broader search if no results
                print("\nNo results from specific recording search, trying broader search...")
                query = f'artist:"{current_artist}" AND recording:"{track_title}"'  # Use original track title
                print(f"Broader Recording Search Query: {query}")
                recordings = self.handle_musicbrainz_api_call(
                    musicbrainzngs.search_recordings,
                    query=query,
                    limit=50
                )

                if recordings and 'recording-list' in recordings:
                    print(f"Total Recordings Found: {len(recordings['recording-list'])}")
                    
                    # Print out detailed recording information
                    for idx, recording in enumerate(recordings['recording-list'], 1):
                        print(f"\nRecording {idx}:")
                        print(f"Title: {recording.get('title', 'N/A')}")
                        
                        # Print artists
                        if 'artist-credit' in recording:
                            artists = [artist['artist']['name'] for artist in recording['artist-credit'] if isinstance(artist, dict) and 'artist' in artist]
                            print(f"Artists: {artists}")
                        
                        # Print releases
                        if 'release-list' in recording:
                            releases = [
                                f"{release.get('title', 'N/A')} ({release.get('date', 'N/A')})" 
                                for release in recording['release-list']
                            ]
                            print(f"Releases: {releases}")

                    # Find best match considering remix status
                    best_recording = self.find_best_match(
                        recordings['recording-list'],
                        current_artist,
                        base_title,
                        handle_remixes=is_remix
                    )

                    if best_recording:
                        earliest_year, earliest_release = self.get_release_year(best_recording)
                        if earliest_release and not self.is_unwanted_release_type(earliest_release):
                            release_score = self._calculate_release_score(earliest_release, current_artist)
                            if release_score > 0.5:
                                metadata = self._search_metadata_from_recording(best_recording, processed_artist)
                                if metadata:
                                    if version_info and metadata.get('title'):
                                        metadata['title'] = f"{metadata['title']} {version_info}".strip()
                                    return metadata
                                else:
                                    metadata = self.search_recording_metadata(best_recording, processed_artist)
                                    if metadata and version_info and metadata.get('title'):
                                        metadata['title'] = f"{metadata['title']} {version_info}".strip()
                                    return metadata
                        # Extract metadata from recording
                        metadata = self.search_recording_metadata(best_recording, processed_artist)
                        
                        if metadata:
                            # Restore version information in the title
                            if version_info and metadata.get('title'):
                                metadata['title'] = f"{metadata['title']} {version_info}".strip()

                            return metadata

                print("No valid metadata found after release and recording searches")
                return None

        except Exception as e:
            print(f"Error in _search_recording_with_fallback: {e}")
            return None

    def is_compilation(self, release):
        """Check if a release is a compilation."""
        try:
            # Check release group type
            if 'release-group' in release:
                release_group = release['release-group']
                
                # Check if compilation is in secondary types
                if 'secondary-type-list' in release_group:
                    if 'Compilation' in release_group['secondary-type-list']:
                        return True

            # Check title for compilation indicators
            if 'title' in release:
                title = release['title'].lower()
                compilation_indicators = [
                    'greatest hits', 'best of', 'collection', 'anthology',
                    'essential', 'definitive', 'gold', 'platinum', 
                    'hits', 'classics', 'compilation', 'remixed',
                    'remastered', 'radio gold', 'am radio', 'radio hits',
                    'radio classics', 'selected works', 'ultimate',
                    'singles collection', 'very best', 'streetjam', 'street jam',
                    'various artists', 'v.a.', 'sampler', 'promo', 'promotional',
                    'mix tape', 'mixtape', 'dj mix', 'radio mix', 'club mix',
                    'mega mix', 'party mix', 'tribute to', 'as heard',
                    'movie soundtrack', 'film soundtrack', 'tv soundtrack',
                    'original motion', 'ost', 'soundtrack'
                ]
                # Also check for numbered volumes/parts/series and year-based compilations
                volume_patterns = [
                    r'volume\s*\d+', r'vol\s*\.?\s*\d+', r'part\s*\d+', 
                    r'chapter\s*\d+', r'series\s*\d+', r'edition\s*\d+',
                    r'now\s*\d+', r'now\s*that\'s',
                    r'dance\s*\d{4}', r'pop\s*\d{4}', r'hits\s*\d{4}', r'music\s*\d{4}',
                    r'summer\s*\d{4}', r'winter\s*\d{4}', r'spring\s*\d{4}', r'autumn\s*\d{4}',
                    r'party\s*\d{4}', r'club\s*\d{4}', r'radio\s*\d{4}'
                ]
                if (any(indicator in title for indicator in compilation_indicators) or
                    any(re.search(pattern, title) for pattern in volume_patterns)):
                    return True

            # Check if multiple artists are involved
            if 'artist-credit' in release:
                if len(release['artist-credit']) > 1:
                    # Check if it's not just a collaboration
                    artist_names = set()
                    for credit in release['artist-credit']:
                        if isinstance(credit, dict) and 'artist' in credit:
                            artist_names.add(credit['artist']['name'])
                    if len(artist_names) > 2:  # More than 2 artists likely indicates compilation
                        return True

            return False

        except Exception as e:
            print(f"Error checking if release is compilation: {e}")
            return False

    def is_preferred_release(self, release, recording_title, original_artist_name):
        """
        Enhanced release filtering with stronger compilation detection and original release preference.
        
        Args:
            release (dict): Release data from MusicBrainz
            recording_title (str): Title of the recording being searched
            original_artist_name (str): Original artist name from the file
            
        Returns:
            bool: Whether this is a preferred release
        """
        try:
            # Basic validation
            if not release or not isinstance(release, dict):
                print("Rejected: Invalid release structure")
                return False

            if self.is_compilation(release):
                print("Rejected: Compilation detected")
                return False

            # Initialize scoring system
            score = 0
            
            # Extract release details
            release_title = release.get('title', '').lower()
            recording_title_lower = recording_title.lower()
            release_group = release.get('release-group', {})

            if recording_title_lower == release_title:
                print(f"★ Found exact album title match: {release_title}")
                return True

            # Check artist appearance in track list
            if 'medium-list' in release:
                artist_track_count = 0
                total_tracks = 0
                
                # Normalize original artist name for comparison
                original_artist_lower = original_artist_name.lower()
                
                for medium in release['medium-list']:
                    if 'track-list' in medium:
                        for track in medium['track-list']:
                            total_tracks += 1
                            if 'artist-credit' in track:
                                track_artists = [artist['artist']['name'].lower() 
                                            for artist in track['artist-credit'] 
                                            if isinstance(artist, dict) and 'artist' in artist]
                                if any(original_artist_lower in artist for artist in track_artists):
                                    artist_track_count += 1
                
                # If artist appears in less than 25% of tracks, likely a compilation
                if total_tracks > 0 and (artist_track_count / total_tracks) < 0.25:
                    print(f"Rejected: Artist only appears in {artist_track_count}/{total_tracks} tracks")
                    return False

            # Strong compilation indicators - immediate rejection
            compilation_indicators = [
                'strictly the best', 'reggae gold', 'reggae hits', 
                'greatest hits', 'best of', 'collection', 'anthology',
                'essential', 'definitive', 'gold', 'platinum', 
                'hits', 'classics', 'volume', 'vol.', 'mixtape',
                'various', 'presents', ' mix', 'mixed', 'part', 'vol', 'disc',
                'legends', 'tribute', 'story of', 'story', 'selection',
                'series', 'reggae legends', 'reggae anthology', 'reggae series',
                'special', 'showcase', 'featuring', 'presents', 'collector',
                'collection', 'collected', 'anniversary', 'legacy', 'history',
                'archive', 'archives', 'chapter', 'chapters', 'the best', 'sound of',
                'mega', 'ediition', 'exclusive', 'streetjam', 'street jam',
                'sampler', 'promo', 'promotional', 'dj mix', 'radio mix',
                'club mix', 'party mix', 'movie soundtrack', 'film soundtrack',
                'tv soundtrack', 'original motion', 'ost', 'soundtrack'
            ]
            
            # Also check for numbered volumes/parts/series patterns and year-based compilations  
            volume_patterns = [
                r'volume\s*\d+', r'vol\s*\.?\s*\d+', r'part\s*\d+', 
                r'chapter\s*\d+', r'series\s*\d+', r'edition\s*\d+',
                r'now\s*\d+', r'now\s*that\'s',
                r'dance\s*\d{4}', r'pop\s*\d{4}', r'hits\s*\d{4}', r'music\s*\d{4}',
                r'summer\s*\d{4}', r'winter\s*\d{4}', r'spring\s*\d{4}', r'autumn\s*\d{4}',
                r'party\s*\d{4}', r'club\s*\d{4}', r'radio\s*\d{4}'
            ]
            
            if (any(indicator in release_title for indicator in compilation_indicators) or
                any(re.search(pattern, release_title) for pattern in volume_patterns)):
                print(f"Rejected: Compilation indicator found in title: {release_title}")
                return False

            # Check if it's a various artists release
            if 'artist-credit' in release:
                artist_names = set()
                for credit in release['artist-credit']:
                    if isinstance(credit, dict) and 'artist' in credit:
                        artist_name = credit['artist']['name'].lower()
                        artist_names.add(artist_name)
                
                # Reject if "various artists" is in the artist names
                if any('various artists' in name for name in artist_names):
                    print("Rejected: Various Artists release")
                    return False
                
                # Previous multiple artist check
                if len(artist_names) > 2:  # Allow for collaborations but not compilations
                    print("Rejected: Multiple artists indicating compilation")
                    return False
                    
                # Strong preference for releases where artist is the main artist
                if original_artist_name.lower() not in artist_names:
                    print(f"Rejected: Original artist {original_artist_name} not in release artists")
                    return False

            # Check primary type - strongly prefer albums and singles
            if 'release-group' in release:
                primary_type = release_group.get('primary-type', '').lower()
                print(f"Primary Type: {primary_type}")  # Diagnostic print
                
                if primary_type not in ['album', 'single']:
                    print(f"Rejected: Non-album/single primary type: {primary_type}")
                    return False
                    
                # Check secondary types
                if 'secondary-type-list' in release['release-group']:
                    secondary_types = [t.lower() for t in release['release-group']['secondary-type-list']]
                    print(f"Secondary Types: {secondary_types}")  # Diagnostic print
                    
                    unwanted_types = ['compilation', 'soundtrack', 'remix', 'dj-mix', 'mixtape']
                    if any(t in unwanted_types for t in secondary_types):
                        print(f"Rejected: Unwanted secondary type found: {secondary_types}")
                        return False

            # Check if it's a various artists release
            if 'artist-credit' in release:
                artist_names = set()
                for credit in release['artist-credit']:
                    if isinstance(credit, dict) and 'artist' in credit:
                        artist_names.add(credit['artist']['name'].lower())
                
                if len(artist_names) > 2:  # Allow for collaborations but not compilations
                    print("Rejected: Multiple artists indicating compilation")
                    return False
                    
                # Strong preference for releases where artist is the main artist
                if original_artist_name.lower() not in artist_names:
                    print(f"Rejected: Original artist {original_artist_name} not in release artists")
                    return False

            # Check release date - prefer original releases
            if 'date' in release and release['date']:
                try:
                    year = int(release['date'][:4])
                    if year < 1960 or year > 2024:
                        print(f"Rejected: Suspicious release year: {year}")
                        return False
                except (ValueError, TypeError):
                    pass

            # Media format check - prefer vinyl for older releases
            if 'format-list' in release:
                media_formats = [format.get('name', '').lower() for format in release.get('format-list', [])]
                if any('cd compilation' in fmt for fmt in media_formats):
                    print("Rejected: CD compilation format")
                    return False

            # Label check - certain labels are known for compilations or reissues
            compilation_labels = [
                'greensleeves', 'vp records compilations', 'jet star', 'trojan records',
                'treasure isle', 'heartbeat', 'pressure sounds', 'vp records', 
                'studio one', 'kingston sounds', 'rhino', 'sanctuary', 'front line',
                'island records compilation', 'dynamic sounds', 'music club', 'pre',
                'studio one compilation', 'reggae retro', 'archive', 'classic', 'sound of'
            ]
            if 'label-info-list' in release:
                for label_info in release['label-info-list']:
                    if 'label' in label_info and 'name' in label_info['label']:
                        label_name = label_info['label']['name'].lower()
                        if any(comp_label in label_name for comp_label in compilation_labels):
                            print(f"Rejected: Known compilation label: {label_name}")
                            return False

            # If album has too many tracks for single artist
            if total_tracks > 18:  # Common max tracks for single-artist album
                print(f"Rejected: Track count ({total_tracks}) too high for single artist album")
                return False

            # Check unique artists ratio if we have track count
            if total_tracks > 0:
                unique_artists = set()
                artist_count = 0
                
                for medium in release['medium-list']:
                    for track in medium.get('track-list', []):
                        if 'artist-credit' in track:
                            for credit in track['artist-credit']:
                                if isinstance(credit, dict) and 'artist' in credit:
                                    unique_artists.add(credit['artist']['name'].lower())
                                    if credit['artist']['name'].lower() == original_artist_name.lower():
                                        artist_count += 1

                # Too many different artists = compilation
                if len(unique_artists) > 4:
                    print(f"Rejected: Too many unique artists ({len(unique_artists)})")
                    return False
                
                # Artist doesn't appear enough = compilation
                artist_ratio = artist_count / total_tracks
                if artist_ratio < 0.35:
                    print(f"Rejected: Artist only in {artist_count}/{total_tracks} tracks ({artist_ratio:.1%})")
                    return False

            # Additional format check for vinyl and original releases
            likely_original = False
            if 'format-list' in release:
                media_formats = [format.get('name', '').lower() for format in release.get('format-list', [])]
                
                # Prefer original 7" singles and vinyl albums from the correct era
                if any('7"' in fmt or 'vinyl' in fmt for fmt in media_formats):
                    if 'date' in release:
                        try:
                            year = int(release['date'][:4])
                            if 1960 <= year <= 1990:  # Adjust year range as needed
                                likely_original = True
                        except (ValueError, TypeError):
                            pass

            # Final check - must be either a likely original release or a standard album/single
            if likely_original or (release_group.get('primary-type', '').lower() in ['album', 'single'] and 
                                'secondary-type-list' not in release_group):
                print(f"Accepted release: {release_title}")
                return True
                
            print(f"Rejected: Release does not meet final criteria: {release_title}")
            return False

        except Exception as e:
            print(f"Error evaluating release: {e}")
            return False

    def _calculate_release_score(self, release, artist_name):
        """Calculate a quality score for a release with better original release detection."""
        score = 0.0
        
        try:
            # Check release group type
            if 'release-group' in release:
                release_group = release['release-group']
                
                # Primary type scoring
                primary_type = release_group.get('primary-type', '').lower()
                if primary_type == 'album':
                    score += 0.5  # Increased from 0.4
                elif primary_type == 'single':
                    score += 0.3  # Increased from 0.2

                # Secondary type penalties
                if 'secondary-type-list' in release_group:
                    secondary_types = [t.lower() for t in release_group['secondary-type-list']]
                    if 'compilation' in secondary_types:
                        score -= 0.4  # Increased penalty
                    if 'remix' in secondary_types:
                        score -= 0.3  # Increased penalty

            # Check release status
            if release.get('status', '').lower() == 'official':
                score += 0.3

            # Enhanced release title analysis
            title = release.get('title', '').lower()
            
            # STRONG positive indicators for original albums
            original_indicators = [
                r'\b(original|first|debut|initial)\b',
                r'^\w+$',  # Single word titles are often original albums
            ]
            
            for pattern in original_indicators:
                if re.search(pattern, title):
                    score += 0.4
                    print(f"Original indicator bonus: +0.4 for pattern '{pattern}' in title '{title}'")
                    break

            # Enhanced year-based scoring for likely original releases
            if 'date' in release and release['date']:
                try:
                    year = int(release['date'][:4])
                    current_year = 2024
                    
                    # Strong bonus for releases from classic eras
                    if 1960 <= year <= 1990:
                        age_bonus = min((1990 - year) * 0.02, 0.3)  # Up to 0.3 bonus for very old releases
                        score += age_bonus
                        print(f"Classic era bonus: +{age_bonus:.2f} for year {year}")
                    
                    # Moderate bonus for releases before 2000
                    elif 1990 < year <= 2000:
                        score += 0.2
                        print(f"Pre-2000 bonus: +0.2 for year {year}")
                    
                    # Small bonus for releases before 2010
                    elif 2000 < year <= 2010:
                        score += 0.1
                        print(f"Pre-2010 bonus: +0.1 for year {year}")
                    
                    # Penalty for very recent releases (likely reissues/compilations)
                    elif year > current_year - 5:
                        score -= 0.2
                        print(f"Recent release penalty: -0.2 for year {year}")
                        
                except (ValueError, TypeError):
                    pass

            # Negative indicators with stronger penalties
            compilation_patterns = [
                (r'\b(greatest|best)\s+(hits?|of)\b', -0.5),
                (r'\b(collection|anthology|essential|definitive)\b', -0.4),
                (r'\b(gold|platinum|ultimate|complete)\b', -0.3),
                (r'\b(hits?|classics?|selected)\b', -0.3),
                (r'\b(remaster|reissue|anniversary|deluxe|expanded)\b', -0.2),
                (r'\b(tribute|karaoke|covers?)\b', -0.4),
                (r'\b(volume|vol\.?\s*\d+|part\s*\d+)\b', -0.3),
                (r'\b(presents|featuring|vs\.?)\b', -0.2),
            ]
            
            for pattern, penalty in compilation_patterns:
                if re.search(pattern, title):
                    score += penalty
                    print(f"Compilation penalty: {penalty} for pattern '{pattern}' in title '{title}'")

            # Enhanced track count analysis
            if 'medium-list' in release:
                track_count = sum(len(medium.get('track-list', [])) 
                                for medium in release['medium-list'])
                
                # Optimal track counts for different eras and types
                if 6 <= track_count <= 12:  # Sweet spot for original albums
                    score += 0.3
                    print(f"Optimal track count bonus: +0.3 for {track_count} tracks")
                elif 13 <= track_count <= 18:  # Still good for albums
                    score += 0.2
                    print(f"Good track count bonus: +0.2 for {track_count} tracks")
                elif track_count > 25:  # Likely compilation
                    score -= 0.3
                    print(f"Compilation track count penalty: -0.3 for {track_count} tracks")

            # Enhanced label analysis using LabelManager
            if 'label-info-list' in release:
                for label_info in release['label-info-list']:
                    if 'label' in label_info and 'name' in label_info['label']:
                        label_name = label_info['label']['name']
                        
                        # Check if it's a major label
                        if self.label_manager.is_major_label(label_name):
                            category = self.label_manager.get_label_category(label_name)
                            if category in ['universal', 'sony', 'warner']:
                                score += 0.3
                                print(f"Major label bonus: +0.3 for {label_name}")
                            elif category == 'independent':
                                score += 0.2
                                print(f"Independent label bonus: +0.2 for {label_name}")
                            elif category == 'historic':
                                score += 0.4  # Historic labels often have original releases
                                print(f"Historic label bonus: +0.4 for {label_name}")
                        
                        # Penalty for known compilation labels
                        compilation_label_indicators = [
                            'compilation', 'presents', 'sound of', 'story of', 
                            'archive', 'collection', 'legacy', 'treasury'
                        ]
                        if any(indicator in label_name.lower() for indicator in compilation_label_indicators):
                            score -= 0.3
                            print(f"Compilation label penalty: -0.3 for {label_name}")
                        
                        break  # Only check first label

            # Format-based scoring
            if 'medium-list' in release:
                for medium in release['medium-list']:
                    format_name = medium.get('format', '').lower()
                    
                    # Original format bonuses
                    if format_name in ['vinyl', '7" vinyl', '12" vinyl', 'lp']:
                        score += 0.2
                        print(f"Original format bonus: +0.2 for {format_name}")
                    elif format_name == 'cd':
                        score += 0.1
                        print(f"CD format bonus: +0.1")

            # Artist consistency check
            if 'artist-credit' in release:
                release_artists = [artist['artist']['name'].lower() 
                                for artist in release['artist-credit'] 
                                if isinstance(artist, dict) and 'artist' in artist]
                
                if artist_name.lower() in release_artists:
                    score += 0.2
                    print(f"Artist consistency bonus: +0.2")
                
                # Penalty for multiple unrelated artists (compilation indicator)
                if len(set(release_artists)) > 3:
                    score -= 0.2
                    print(f"Multiple artists penalty: -0.2 for {len(set(release_artists))} artists")

            print(f"Final release score for '{release.get('title', 'Unknown')}': {score:.2f}")
            return max(0.0, min(1.0, score))  # Normalize between 0 and 1

        except Exception as e:
            print(f"Error calculating release score: {e}")
            return 0.0

    def is_unwanted_release_type(self, release):
        """Check if a release is an unwanted type. 'Live' is handled by scoring."""
        try:
            if 'release-group' in release:
                release_group = release['release-group']
                primary_type = release_group.get('primary-type', '').lower()
                secondary_types = release_group.get('secondary-type-list', [])
                
                # Define unwanted types (excluding 'live' for primary type)
                unwanted_primary_types = ['compilation', 'remix', 'soundtrack'] # 'live' removed
                unwanted_secondary_types = ['compilation', 'remix', 'interview', 'spokenword'] # 'spoken word' not 'spoken word '

                if primary_type in unwanted_primary_types:
                    # print(f"Rejected (Unwanted Primary Type): {primary_type} for release '{release.get('title', '')}'")
                    return True
                
                if any(secondary_type.lower() in unwanted_secondary_types for secondary_type in secondary_types):
                    # print(f"Rejected (Unwanted Secondary Type): {secondary_types} for release '{release.get('title', '')}'")
                    return True
            
            release_title = release.get('title', '').lower()
            # These title indicators are generally for compilations or non-original versions
            unwanted_title_indicators = [
                'greatest hits', 'best of', 'collection', 'anthology',
                'essential', 'definitive', 'gold', 'platinum', 
                'hits', 'classics', 'very best', 'selected works', 'ultimate',
                'singles collection', 'streetjam', 'street jam', 'various artists',
                'v.a.', 'sampler', 'promo', 'promotional', 'mix tape', 'mixtape',
                'dj mix', 'radio mix', 'club mix', 'mega mix', 'party mix',
                'tribute to', 'as heard', 'movie soundtrack', 'film soundtrack',
                'tv soundtrack', 'original motion', 'ost', 'soundtrack'
            ]
            
            # Check for numbered volumes/parts/series patterns and year-based compilations
            volume_patterns = [
                r'volume\s*\d+', r'vol\s*\.?\s*\d+', r'part\s*\d+', 
                r'chapter\s*\d+', r'series\s*\d+', r'edition\s*\d+',
                r'now\s*\d+', r'now\s*that\'s',
                r'dance\s*\d{4}', r'pop\s*\d{4}', r'hits\s*\d{4}', r'music\s*\d{4}',
                r'summer\s*\d{4}', r'winter\s*\d{4}', r'spring\s*\d{4}', r'autumn\s*\d{4}',
                r'party\s*\d{4}', r'club\s*\d{4}', r'radio\s*\d{4}'
            ]
            
            if (any(indicator in release_title for indicator in unwanted_title_indicators) or
                any(re.search(pattern, release_title) for pattern in volume_patterns)):
                # print(f"Rejected (Unwanted Title Indicator): for release '{release.get('title', '')}'")
                return True
            
            return False
        
        except Exception as e:
            print(f"Error checking release type in is_unwanted_release_type: {e}")
            return False # Default to not unwanted on error to allow scoring

    def get_release_year(self, recording):
        """
        Enhanced method to get earliest release year with better filtering for classic songs.
        """
        try:
            if 'release-list' in recording and recording['release-list']:
                earliest_year = None
                best_release = None
                
                for release in recording['release-list']:
                    if not self.is_unwanted_release_type(release):
                        if 'date' in release and release['date']:
                            try:
                                year = int(release['date'][:4])
                                
                                # Skip obviously wrong years
                                if year < 1900:
                                    continue
                                    
                                # For classic songs, strongly prefer pre-1980 releases
                                if earliest_year is None or (year < 1980 and year < earliest_year):
                                    earliest_year = year
                                    best_release = release
                                # For modern songs, just take the earliest valid release
                                elif earliest_year is None or year < earliest_year:
                                    earliest_year = year
                                    best_release = release
                                    
                            except (ValueError, IndexError):
                                continue
                                
                if earliest_year:
                    print(f"Found release year {earliest_year} from release: {best_release.get('title', 'Unknown')}")
                    return earliest_year, best_release
                        
        except Exception as e:
            print(f"Error getting release year: {e}")
        return None, None

    def get_artist_genres_from_mb(self, artist_name: str) -> Optional[tuple]:
        """Get artist genres from MusicBrainz artist tags."""
        try:
            print(f"\nFetching artist genres from MusicBrainz for: {artist_name}")
            
            # Check cache first for artist genres
            if self.cache_manager:
                cache_key = f"artist_genre_{artist_name.lower().replace(' ', '_')}"
                cached_result = self.cache_manager.get('musicbrainz', cache_key)
                if cached_result:
                    print(f"Found cached artist genres for {artist_name}")
                    return cached_result.get('genre'), cached_result.get('comments')
            
            # Search for the artist
            artist_results = self.handle_musicbrainz_api_call(
                musicbrainzngs.search_artists,
                query=f'artist:"{artist_name}"',
                limit=20
            )
            
            if not artist_results or 'artist-list' not in artist_results:
                print("No artist found in MusicBrainz")
                return None
            
            # Find best matching artist
            best_artist = None
            best_score = 0
            
            for artist in artist_results['artist-list']:
                if not artist.get('name'):
                    continue
                    
                score = self.utility_tools.fuzzy_match(artist_name, artist['name'])
                if isinstance(score, bool):
                    score = 100 if score else 0  # Convert boolean to numeric score
                if score > best_score:
                    best_score = score
                    best_artist = artist
            
            if not best_artist or best_score < 80:
                print(f"No good artist match found (best score: {best_score})")
                return None
            
            print(f"Found artist: {best_artist['name']} (score: {best_score})")
            
            # Get detailed artist info with tags
            artist_id = best_artist['id']
            artist_detail = self.handle_musicbrainz_api_call(
                musicbrainzngs.get_artist_by_id,
                artist_id,
                includes=['tags']
            )
            
            if not artist_detail or 'artist' not in artist_detail:
                print("Could not fetch artist details")
                return None
            
            artist_data = artist_detail['artist']
            if 'tag-list' not in artist_data or not artist_data['tag-list']:
                print("No tags found for artist")
                return None
            
            # Process artist tags
            genre_tags = []
            for tag in artist_data['tag-list']:
                if tag.get('name'):
                    tag_name = tag['name'].lower()
                    count = int(tag.get('count', 0))
                    if count > 0:
                        genre_tags.append((tag_name, count))
            
            if not genre_tags:
                print("No valid genre tags found")
                return None
            
            # Sort by popularity and get genres
            genre_tags.sort(key=lambda x: x[1], reverse=True)
            print(f"Artist tags found: {genre_tags[:10]}")  # Show top 10
            
            primary_genre, subgenres = self._process_mb_tags(genre_tags)
            
            if primary_genre:
                print(f"Artist genres - Primary: {primary_genre}, Subgenres: {subgenres}")
                result = (primary_genre, ', '.join(subgenres) if subgenres else '')
                
                # Cache the result
                if self.cache_manager:
                    cache_key = f"artist_genre_{artist_name.lower().replace(' ', '_')}"
                    cache_data = {
                        'genre': primary_genre,
                        'comments': ', '.join(subgenres) if subgenres else ''
                    }
                    self.cache_manager.set('musicbrainz', cache_key, cache_data)
                    print(f"Cached artist genres for {artist_name}")
                
                return result
            else:
                print("Could not determine primary genre from artist tags")
                return None
                
        except Exception as e:
            print(f"Error fetching artist genres from MusicBrainz: {e}")
            return None