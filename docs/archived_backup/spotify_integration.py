import spotipy
import requests
import base64
import time
import re
from threading import Lock
from spotipy.exceptions import SpotifyException
from artist_normalizer import ArtistNormalizer
from hf_llm_utils import HFLLMUtilities
from constants import CLIENT_ID, CLIENT_SECRET, OPENROUTER_API_KEY
from dialog_handler import DialogHandler
from rate_limiter import UnifiedRateLimiter

class SpotifyIntegration:
    def __init__(self, parent=None, status_update_callback=None, artist_normalizer=None, ui_elements=None, cache_manager=None):
        self.parent = parent
        self._refresh_lock = Lock()
        
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.utility_tools = HFLLMUtilities()
        self.dialog_handler = DialogHandler.instance(parent)
        
        # Store callback for status updates
        self.status_update_callback = status_update_callback
        
        self.artist_normalizer = ArtistNormalizer(OPENROUTER_API_KEY) if artist_normalizer is None else artist_normalizer
        self.ui_elements = ui_elements
        
        self.current_genre = None
        self.cache_manager = cache_manager
        
        # Initialize API counters and rate limiting
        self.api_call_count = 0
        self.current_session_calls = 0
        self.max_api_calls = 5
        self.consecutive_calls = 0
        self.last_call_time = None
        self.rate_limiter = UnifiedRateLimiter()
        
        # Initialize token info
        self.token_info = None
        self.token_expiry = None
        
        # Clear the cache on startup
        self.clear_cache()
        self.initialize_spotify_client()

    def refresh_token(self):
        with self._refresh_lock:  # Only one thread can refresh at a time
            try:
                # Check if token is still valid
                if self.token_info and time.time() < self.token_expiry - 30:
                    return  # Token still valid, no need to refresh
                    
                token_url = "https://accounts.spotify.com/api/token"
                auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
                headers = {
                    "Authorization": f"Basic {auth_header}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                data = {
                    "grant_type": "client_credentials"
                }

                response = requests.post(token_url, headers=headers, data=data)
                response.raise_for_status()

                self.token_info = response.json()
                self.token_expiry = time.time() + self.token_info['expires_in']
                self.sp = spotipy.Spotify(auth=self.token_info['access_token'])

            except Exception as e:
                pass
                # Re-raise to allow proper error handling
                raise

    def initialize_spotify_client(self):
        self.refresh_token()

    def handle_spotify_api_call(self, func, *args, **kwargs):
        """Handle Spotify API calls with unified rate limiting."""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Check token expiration
                if time.time() > self.token_expiry - 60:
                    self.refresh_token()

                # Use unified rate limiter
                self.rate_limiter.wait_if_needed('spotify')

                # Make the API call
                response = func(*args, **kwargs)
                self.api_call_count += 1
                return response

            except SpotifyException as e:
                retry_count += 1
                
                if e.http_status == 401:  # Unauthorized
                    self.refresh_token()
                    continue
                    
                elif e.http_status == 429:  # Rate limited
                    retry_after = int(e.headers.get('Retry-After', 5))
                    time.sleep(retry_after)
                    # Reset rate limiter state since we got rate limited
                    self.rate_limiter.reset_service('spotify')
                    continue
                    
                else:
                    raise
                    
            except Exception as e:
                raise

        raise Exception(f"Failed to complete Spotify API call after {max_retries} attempts")

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

    def clear_cache(self):
        if self.cache_manager:
            self.cache_manager.clear('spotify')

    def search_artist(self, artist_name):
        """Search for artist with improved artist name handling and fallback."""
        _, processed_name = self.artist_normalizer.preprocess_artist_name(artist_name)
        time.sleep(1)
        try:
            # Try with preserved group name first
            results = self.handle_spotify_api_call(
                self.sp.search,
                q=processed_name,
                type='artist',
                limit=50
            )

            # If no results, try with simplified name
            if not results or not results.get('artists', {}).get('items'):
                # Simplify the group name
                simplified_name = self.utility_tools.clean_string(artist_name)
                simplified_name = re.sub(r'[&,]', ' ', simplified_name)
                
                results = self.handle_spotify_api_call(
                    self.sp.search,
                    q=simplified_name,
                    type='artist',
                    limit=50
                )

            if results and 'artists' in results and results['artists']['items']:
                # First try exact matches with good popularity
                for artist in results['artists']['items']:
                    if not artist.get('name'):
                        continue
                        
                    current_name = artist['name']
                    popularity = artist.get('popularity', 0)
                    
                    # Skip very low popularity artists
                    if popularity < 30:
                        continue

                    # Try matching both original and simplified names
                    original_match = self.utility_tools.fuzzy_match(
                        current_name, artist_name
                    ) >= 85
                    
                    simplified_match = self.utility_tools.fuzzy_match(
                        current_name, simplified_name
                    ) >= 85 if 'simplified_name' in locals() else False

                    if original_match or simplified_match:
                        return artist['id']

                # If no exact match found, try fuzzy matching with lower threshold
                for artist in results['artists']['items']:
                    if not artist.get('name') or artist.get('popularity', 0) < 30:
                        continue
                        
                    # Use artist_normalizer for fuzzy matching
                    match_score = self.artist_normalizer.fuzzy_match_artists(
                        artist['name'],
                        processed_name
                    )
                    
                    if match_score >= 75:
                        return artist['id']

            return None

        except Exception as e:
            return None
        

    def extract_metadata_from_spotify(self, cleaned_artist_name, simplified_title, file_metadata, selected_fields=None, mb_preferred_year=None, mb_preferred_album_title=None):
        """Enhanced metadata extraction with multiple search attempts."""
        try:
                    
            # Check cache first
            metadata = self.cache_manager.get_metadata(cleaned_artist_name, simplified_title)
            if metadata:
                return metadata

            # Search attempts with different query formats
            search_attempts = [
                # First attempt: Full title with featuring
                (cleaned_artist_name, simplified_title),
                
                # Second attempt: Clean title without featuring
                (cleaned_artist_name, self.utility_tools.clean_track_title(simplified_title)),
                
                # Third attempt: Base title only
                (cleaned_artist_name, self.utility_tools.normalize_title_for_comparison(simplified_title))
            ]
            
            for _, (artist, title) in enumerate(search_attempts, 1):
                query = f"{artist} {title}"
                
                results = self.handle_spotify_api_call(
                    self.sp.search,
                    q=query,
                    type="track",
                    limit=50
                )

                if not results or 'tracks' not in results or not results['tracks']['items']:
                    continue

                filtered_results = self.filter_track_results(
                    results['tracks']['items'],
                    cleaned_artist_name,
                    title  # Use the current attempt's title for filtering
                )

                if filtered_results:
                    best_match = self.find_best_match_track(
                        filtered_results,
                        cleaned_artist_name,
                        title,
                        mb_preferred_year=mb_preferred_year,
                        mb_preferred_album_title_norm=mb_preferred_album_title
                    )
                    
                    if best_match:
                        return self.process_track_result(best_match, file_metadata)
                
                # Add delay between attempts
                time.sleep(1)

            return None

        except Exception as e:
            return None
        
    def filter_track_results(self, tracks, artist_name, track_title):
        """Enhanced track filtering with better matching."""
        filtered = []
        
        # Clean the search title using utility tools
        search_title_clean = self.utility_tools.normalize_title_for_comparison(track_title)
        
        # Get main artist name
        main_artist = self.utility_tools.get_main_artist_name(artist_name)
        main_artist_lower = main_artist.lower()
        
        for track in tracks:
            try:
                if not track.get('name') or not track.get('artists'):
                    continue
                    
                track_name = track['name']
                track_artists = track['artists']
                
                # Clean track name using utility tools
                track_name_clean = self.utility_tools.normalize_title_for_comparison(track_name)
                
                
                # Check artist match
                artist_match = False
                artist_names = [artist['name'].lower() for artist in track_artists]
                
                for artist_name in artist_names:
                    if (main_artist_lower in artist_name or 
                        artist_name in main_artist_lower or
                        self.utility_tools.fuzzy_artist_match(main_artist, artist_name)):
                        artist_match = True
                        break
                
                if not artist_match:
                    continue
                
                # Title matching using utility tools
                if (search_title_clean == track_name_clean or  # Exact match
                    search_title_clean in track_name_clean or   # Partial match
                    track_name_clean in search_title_clean or   # Reverse partial match
                    self.utility_tools.fuzzy_match_title_for_query(   # Fuzzy match
                        search_title_clean, track_name_clean, threshold=70)):
                    filtered.append(track)
                    
            except Exception as e:
                continue
        
        return filtered

    def is_unwanted_album(self, album):
        """Enhanced method to handle genre-specific album filtering.
        Live albums are no longer strictly rejected here for non-dancehall,
        they will be penalized in the scoring phase.
        """
        try:
            album_name = album['name'].lower()
            album_type = album.get('album_type', '').lower()
            
            is_dancehall = (
                self.current_genre and 
                any(genre in self.current_genre for genre in ['dancehall', 'reggae', 'soca'])
            )
            
            if is_dancehall:
                unwanted_indicators = [
                    ' live ', 'in concert', 'concert', 'tour', 
                    'recorded live', 'live at', 'live from',
                    'live in', '(live)', '[live]', '- live',
                    ' live)', ' live]', 'live at',
                    'remix', 'dj mix', 'dubstep'
                ]
                clean_name = album_name
                feature_patterns = ['with', 'feat', 'featuring', 'ft.', '&', 'presents', 'x', 'vs']
                for pattern in feature_patterns:
                    clean_name = re.sub(rf'\s*[\(\[].*{pattern}.*[\)\]]', '', clean_name)
                
                if any(indicator in clean_name for indicator in unwanted_indicators):
                    return True
                return False
            
            # For non-dancehall tracks:
            if album_type in ['single', 'album']:
                # Indicators for definite rejection (non-live related)
                hard_unwanted_indicators = [
                    'karaoke', 'sped up', 'tribute',
                    'now that\'s what i call music' 
                    # Add other terms that should always lead to rejection
                ]
                
                clean_name = album_name
                feature_patterns = ['with', 'feat', 'featuring', 'ft.', '&', 'presents', 'x', 'vs']
                for pattern in feature_patterns:
                    clean_name = re.sub(rf'\s*[\(\[].*{pattern}.*[\)\]]', '', clean_name)

                if any(indicator in clean_name for indicator in hard_unwanted_indicators):
                    return True

                # Contextual unwanted indicators (might be compilations or non-original versions)
                # These are kept for now, but could also be moved to penalties for more flexibility.
                contextual_unwanted_indicators = [
                    # 'remix', # Remixes in track name are penalized/rejected in find_best_match_track
                    'special edition', 'reissue', 'release special', 
                    # 'remaster', # Remasters are often okay
                    'essential', 'the essential', 'expanded', 'and friends' 
                ]
                if any(indicator in clean_name for indicator in contextual_unwanted_indicators):
                    return True
                
                # No longer rejecting based on 'live_indicators' here.
                return False
            
            if album_type == 'compilation':
                if is_dancehall:
                    return False 
                else:
                    # Compilations for non-dancehall are generally less preferred unless they score well.
                    # Let's allow them to be scored, but they already get penalized in find_best_match_track.
                    # For consistency, if find_best_match_track penalizes/rejects compilations, this can be 'False' too.
                    # The provided find_best_match_track has:
                    # if 'album' in track and any(indicator in track['album']['name'].lower() for indicator in ['greatest hits', 'best of', 'collection']): continue
                    # So, this function could return False here, and let find_best_match_track handle it.
                    # However, if this `is_unwanted_album` is a pre-filter, then returning True for non-dancehall compilations is consistent.
                    return True 
            
            return True
            
        except Exception as e:
            return True

    def find_best_match_track(self, tracks, artist_name, track_title, mb_preferred_year=None, mb_preferred_album_title_norm=None):
        """
        Find the best matching track with an even stronger preference for original album releases
        by heavily penalizing compilations and significantly boosting matches to MusicBrainz preferred year/album.
        """
        try:
            best_match_candidate = None
            highest_score = -float('inf')
            

            def normalize_text_for_comparison(text):
                if not text: return ""
                text = text.lower()
                text = re.sub(r'\s*[\(\[][^)]*[\)\]]', '', text) # Remove content in brackets
                text = re.sub(r'[^\w\s]', '', text) # Remove special chars
                text = ' '.join(text.split()) # Normalize spaces
                return text

            search_title_norm = normalize_text_for_comparison(self.utility_tools.clean_track_title(track_title))
            
            live_album_indicators_penalty_list = [
                'live at', 'live from', 'live in', '(live)', '[live]', '- live', ' recorded live', 'in concert'
            ]
            
            compilation_album_name_indicators_penalty_list = [
                'greatest hits', 'best of', 'collection', 'anthology', 'essential', 
                'definitive', 'the very best of', 'story of', 'complete', 
                'ultimate', 'hits', 'the hits', 'sound of', 'a man and a half', 'presents',
                'remastered', 'expanded edition', 'deluxe edition', # Often re-issues or compilations
                'various artists' 
            ]

            for _, track_item in enumerate(tracks):

                if not track_item.get('name') or not track_item.get('artists'):
                    continue

                current_eval_score = 0
                score_breakdown = []

                # 1. Artist Match (Essential)
                track_artists = track_item['artists']
                artist_match_val = 0
                if track_artists:
                    # Simplified: taking the max score from any artist. Refine if main artist needed.
                    artist_match_val = max(self.artist_normalizer.fuzzy_match_artists(artist_name, art['name']) for art in track_artists)
                
                if artist_match_val < 85: # Strict threshold
                    continue
                current_eval_score += artist_match_val * 1.5 # Slightly reduced direct weight
                score_breakdown.append(f"ArtM: {artist_match_val * 1.5:.0f}")

                # 2. Title Match (Essential)
                spotify_track_title_norm = normalize_text_for_comparison(track_item['name'])
                title_match_val = self.utility_tools.fuzzy_match_title_for_query(
                    search_title_norm, 
                    spotify_track_title_norm, 
                    threshold=70 # Slightly lower threshold, but good match still gets high score
                )

                if title_match_val < 75: # Still need a decent match
                    continue
                current_eval_score += title_match_val * 2.0 # Strong weight
                score_breakdown.append(f"TitleM: {title_match_val * 2.0:.0f}")

                # Penalties for track name variants
                if 'live' in spotify_track_title_norm:
                    current_eval_score -= 150
                    score_breakdown.append("TrackLive: -150")
                if any(rem_ind in spotify_track_title_norm for rem_ind in ['remix', 'edit', 'radio edit', 'club mix']):
                    continue # Strict rejection for these track versions

                # Album related scoring
                spotify_album_data = track_item.get('album')
                spotify_album_year = None
                is_likely_compilation_spotify = False

                if spotify_album_data:
                    spotify_album_name_orig = spotify_album_data.get('name', '')
                    spotify_album_name_norm = normalize_text_for_comparison(spotify_album_name_orig)
                    spotify_album_type = spotify_album_data.get('album_type', '').lower()

                    # Check for live album by name
                    if any(live_ind in spotify_album_name_norm for live_ind in live_album_indicators_penalty_list):
                        current_eval_score -= 100
                        score_breakdown.append("AlbumLive: -100")
                    
                    # Check for compilation by name
                    if any(comp_ind in spotify_album_name_norm for comp_ind in compilation_album_name_indicators_penalty_list):
                        current_eval_score -= 350 # Heavy penalty
                        score_breakdown.append(f"AlbumCompName: -350 ('{spotify_album_name_orig}')")
                        is_likely_compilation_spotify = True
                    
                    if spotify_album_type == 'compilation': # If Spotify itself calls it a compilation
                        current_eval_score -= 150
                        score_breakdown.append("AlbumTypeComp: -150")
                        is_likely_compilation_spotify = True
                    elif spotify_album_type == 'album':
                        current_eval_score += 50 # Small bonus for being a full album
                        score_breakdown.append("AlbumTypeAlbum: +50")
                    elif spotify_album_type == 'single':
                        current_eval_score += 25
                        score_breakdown.append("AlbumTypeSingle: +25")

                    # Year processing and bonus for matching MB preferred year
                    album_release_date_str = spotify_album_data.get('release_date', '')
                    if album_release_date_str and len(album_release_date_str) >= 4:
                        try:
                            spotify_album_year = int(album_release_date_str[:4])
                            if spotify_album_year > 1900: # Sanity check
                                # General preference for older original releases
                                year_bonus = max(0, (1990 - spotify_album_year)) * 2 # Bonus for pre-1990, up to (e.g. 1970 = 20*2=40)
                                if spotify_album_year < 1970 : year_bonus += (1970-spotify_album_year) * 3 # Stronger bonus for very old
                                current_eval_score += year_bonus
                                score_breakdown.append(f"YearGenBonus({spotify_album_year}): +{year_bonus}")

                                if mb_preferred_year and spotify_album_year == mb_preferred_year:
                                    if not is_likely_compilation_spotify:
                                        current_eval_score += 400 # VERY strong bonus if year matches MB & not a compilation
                                        score_breakdown.append(f"MBYearMatch: +400")
                                    else:
                                        current_eval_score += 50 # Smaller bonus if it's a compilation but matches year
                                        score_breakdown.append(f"MBYearMatchComp: +50")
                                elif mb_preferred_year and abs(spotify_album_year - mb_preferred_year) <= 2 and not is_likely_compilation_spotify :
                                    current_eval_score += 150 # Bonus if year is close to MB preferred & not compilation
                                    score_breakdown.append(f"MBYearClose: +150")


                        except ValueError:
                            pass
                    
                    # Bonus if album title also matches a normalized MB preferred album title
                    if mb_preferred_album_title_norm and spotify_album_name_norm == mb_preferred_album_title_norm:
                        if not is_likely_compilation_spotify:
                             current_eval_score += 200
                             score_breakdown.append(f"MBAlbumNameMatch: +200")
                        else:
                             current_eval_score += 50
                             score_breakdown.append(f"MBAlbumNameMatchComp: +50")


                # 3. Popularity (less weight than structural features)
                popularity = track_item.get('popularity', 0)
                current_eval_score += popularity * 0.25 # Reduced weight
                score_breakdown.append(f"Pop: {popularity * 0.25:.0f}")
                

                if current_eval_score > highest_score:
                    highest_score = current_eval_score
                    best_match_candidate = track_item

            if best_match_candidate:
                pass
            else:
                pass
            
            return best_match_candidate
            
        except Exception as e:
            return None

    def process_track_result(self, track, file_metadata, feature_string=None):
        """Process track result with enhanced featured artist handling and genre fallback."""
        try:
            if not track:
                return None

            # Get all artists from track
            spotify_artists = [artist for artist in track['artists'] if artist.get('name')]
            if not spotify_artists:
                return None

            # Get the main artist name from file metadata
            original_artist_full = file_metadata.get('artist', '').strip()
            _ = self.utility_tools.get_main_artist_name(original_artist_full)
            

            # Get Spotify's main artist and features
            main_spotify_artist = spotify_artists[0]['name']
            featuring_spotify_artists = [artist['name'] for artist in spotify_artists[1:]]
            

            # Initialize metadata with ALL available fields
            metadata = {
                'title': track.get('name', file_metadata.get('title', '')),
                'album': track['album']['name'] if track.get('album') else '',
                'year': track['album']['release_date'].split("-")[0] if track.get('album') and 'release_date' in track['album'] else '',
                'genre': '',
                'comments': '',
                'artist': main_spotify_artist,  # Start with main artist
                'artist_id': spotify_artists[0].get('id', ''),  # Preserve artist ID
                'spotify_id': track.get('id', ''),  # Add track ID
                'album_id': track['album'].get('id', '') if track.get('album') else ''
            }


            # Handle featuring artists if present
            if featuring_spotify_artists:
                if self.dialog_handler.show_features_dialog(
                    featuring_spotify_artists,
                    main_spotify_artist
                ):
                    
                    # Format with standardized featuring format
                    if len(featuring_spotify_artists) == 1:
                        metadata['artist'] = f"{main_spotify_artist} feat. {featuring_spotify_artists[0]}"
                    else:
                        features_str = ", ".join(featuring_spotify_artists[:-1]) + " & " + featuring_spotify_artists[-1]
                        metadata['artist'] = f"{main_spotify_artist} feat. {features_str}"
                else:
                    metadata['artist'] = main_spotify_artist

            # Genre information will be handled by separate genre detection system
            metadata['genre'] = "No Genre"
            metadata['comments'] = ""

            # Add year from release date if available
            if track.get('album', {}).get('release_date'):
                try:
                    metadata['year'] = track['album']['release_date'].split('-')[0]
                except Exception as e:
                    print(f"Error parsing release date: {e}")


            # Verify metadata has required fields
            required_fields = ['artist', 'album', 'year', 'genre']
            missing_fields = [field for field in required_fields if not metadata.get(field)]
            if missing_fields:
                return metadata

            return metadata

        except Exception as e:
            pass
            return None

    def get_api_call_count(self):
        return self.api_call_count