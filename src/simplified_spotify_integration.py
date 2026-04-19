import requests
import base64
import time
from typing import Optional, Dict

class SimplifiedSpotifyIntegration:
    """
    Lightweight Spotify integration using only available endpoints.
    
    Available endpoints we can use:
    - Search (track, artist, album)  
    - Get Track/Album/Artist (basic info only)
    - No audio features, recommendations, or algorithmic playlists
    """
    
    def __init__(self, client_id=None, client_secret=None, cache_manager=None, status_update_callback=None, debug_logger=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache_manager = cache_manager
        self.access_token = None
        self.token_expires_at = 0

        # Store callback for status updates
        self.status_update_callback = status_update_callback

        # Logger for detailed search debugging
        self.debug_logger = debug_logger

        # Load credentials
        self._load_credentials()

        print("Simplified Spotify integration initialized")

    def emit_status(self, message):
        """Emit status update through callback."""
        if self.status_update_callback:
            self.status_update_callback(message)
        else:
            print(message)

    def _load_credentials(self):
        """Load Spotify credentials from file if it exists."""
        try:
            import json
            import os
            from resource_path import get_resource_path
            
            # Try to find credentials file
            creds_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config',
                'spotify_credentials.json'
            )
            
            # If file doesn't exist, that's ok - Spotify integration is optional
            if not os.path.exists(creds_path):
                return
            
            with open(creds_path, 'r') as f:
                creds = json.load(f)
                
            self.client_id = creds.get('client_id')
            self.client_secret = creds.get('client_secret')
            
            if self.client_id and self.client_secret:
                print("Spotify credentials loaded successfully")
            else:
                print("Warning: Spotify credentials file found but incomplete")
                
        except Exception as e:
            print(f"Warning: Could not load Spotify credentials: {e}")

    def _get_access_token(self):
        """Get access token using client credentials flow."""
        try:
            current_time = time.time()
            
            # Check if we have a valid token
            if self.access_token and current_time < self.token_expires_at:
                return self.access_token
            
            if not self.client_id or not self.client_secret:
                return None
            
            # Request new token
            auth_url = 'https://accounts.spotify.com/api/token'
            
            # Encode client credentials
            client_creds = f"{self.client_id}:{self.client_secret}"
            client_creds_b64 = base64.b64encode(client_creds.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {client_creds_b64}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'grant_type': 'client_credentials'
            }
            
            response = requests.post(auth_url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = current_time + expires_in - 60  # 60s buffer
            
            print("Spotify access token obtained")
            return self.access_token
            
        except Exception as e:
            print(f"Error getting Spotify access token: {e}")
            return None

    def _make_request(self, endpoint, params=None):
        """Make authenticated request to Spotify API."""
        try:
            token = self._get_access_token()
            if not token:
                return None
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f'https://api.spotify.com/v1/{endpoint}'
            response = requests.get(url, headers=headers, params=params or {}, timeout=10)
            
            if response.status_code == 401:
                # Token expired, try to refresh
                self.access_token = None
                token = self._get_access_token()
                if token:
                    headers['Authorization'] = f'Bearer {token}'
                    response = requests.get(url, headers=headers, params=params or {}, timeout=10)
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            print(f"Error making Spotify request to {endpoint}: {e}")
            return None

    def _simplify_track_title(self, title: str) -> str:
        """Remove version qualifiers like (Clean), [Remix], etc. from track title."""
        import re
        # Match patterns like (Clean), [Remix], - Remaster, etc.
        simplified = re.sub(r'\s*[\(\[].*?[\)\]]\s*', ' ', title)
        # Remove extra spaces and dashes
        simplified = re.sub(r'\s*-\s*(.*?(remix|remaster|version|mix|edit|cover).*?)$', '', simplified, flags=re.IGNORECASE)
        return simplified.strip()

    def search_metadata(self, artist_name: str, track_title: str, original_track_title: str = None) -> Optional[Dict]:
        """Search for track metadata using Spotify's search endpoint.

        Args:
            artist_name: Artist name (will be normalized for search)
            track_title: Track title (already normalized, may have had special chars converted)
            original_track_title: Original track title with special chars intact (e.g., "$ave Dat Money")
        """
        if not self.client_id or not self.client_secret:
            return None

        try:
            print(f"Spotify search: {artist_name} - {track_title}")

            # Check cache first
            if self.cache_manager:
                cached = self.cache_manager.get_metadata(artist_name, track_title)
                if cached and cached.get('spotify_id'):
                    print("Found cached Spotify metadata")
                    return cached

            # Build query list - try original title with special chars FIRST if available
            queries = []

            # If we have the original title with special characters (e.g., "$ave Dat Money"),
            # try that first since Spotify preserves special chars in track names
            if original_track_title and original_track_title != track_title:
                # Try original title with version markers (e.g., "$ave Dat Money (Clean)")
                queries.append(f'artist:"{artist_name}" track:"{original_track_title}"')
                queries.append(f'track:"{original_track_title}"')
                # Also try original title WITH special chars but simplified (no version markers)
                simplified_original = self._simplify_track_title(original_track_title)
                if simplified_original != original_track_title:
                    queries.append(f'artist:"{artist_name}" track:"{simplified_original}"')
                    queries.append(f'track:"{simplified_original}"')

            # Then try normalized versions
            queries.extend([
                f'artist:"{artist_name}" track:"{track_title}"',  # Exact match with normalized
                f'artist:"{artist_name}" track:"{self._simplify_track_title(track_title)}"',  # Simplified title
                f'artist:"{artist_name}" {self._simplify_track_title(track_title)}',  # Less strict
                f'track:"{self._simplify_track_title(track_title)}"'  # Title-only search (for collaborative tracks)
            ])
            
            for query_idx, query in enumerate(queries):
                print(f"Trying Spotify query: {query}")
                params = {
                    'q': query,
                    'type': 'track',
                    'limit': 20  # Get multiple results to find best match
                }

                results = self._make_request('search', params)
                if not results or 'tracks' not in results:
                    continue

                tracks = results['tracks']['items']
                print(f"Found {len(tracks)} Spotify tracks")

                if not tracks:
                    continue

                # Filter to exact matches
                for track in tracks:
                    if self._is_exact_match(track, artist_name, track_title):
                        album_name = track['album']['name']
                        # Reject if album looks like a compilation
                        if self._is_likely_compilation(album_name):
                            print(f"  Skipping compilation album: {album_name}")
                            continue
                        metadata = self._extract_track_metadata(track)
                        print(f"Exact Spotify match: {metadata}")

                        # NOTE: Caching is now handled by SimplifiedMetadataSearcher after genre lookup
                        return metadata

                # If no exact match, try fuzzy matching on the first few results
                print("No exact match, trying fuzzy matching")
                # For title-only searches (last query), be more lenient with artist matching
                is_title_only_search = (query_idx == len(queries) - 1)
                if is_title_only_search:
                    print(f"  Title-only search mode: will use 0.70 artist threshold")
                for idx, track in enumerate(tracks[:5]):  # Only check top 5
                    track_artists_str = ', '.join([a['name'] for a in track.get('artists', [])])
                    track_title_str = track.get('name', '')
                    album_name = track['album']['name']
                    if is_title_only_search:
                        print(f"  Track {idx+1}: '{track_title_str}' by {track_artists_str} | Album: {album_name}")
                    if self._is_fuzzy_match(track, artist_name, track_title, is_title_only_search):
                        # Reject if album looks like a compilation
                        if self._is_likely_compilation(album_name):
                            print(f"  Skipping compilation album: {album_name}")
                            continue
                        metadata = self._extract_track_metadata(track)
                        print(f"Fuzzy Spotify match: {metadata}")

                        # NOTE: Caching is now handled by SimplifiedMetadataSearcher after genre lookup
                        return metadata

                if is_title_only_search:
                    print(f"  All {len(tracks[:5])} tracks rejected by fuzzy matching")
                    
            return None
            
        except Exception as e:
            print(f"Error in Spotify search: {e}")
            return None

    def _is_exact_match(self, track: dict, target_artist: str, target_title: str) -> bool:
        """Check if track is an exact match."""
        try:
            # Check track title
            track_title = track['name'].lower().strip()
            target_title_clean = target_title.lower().strip()
            
            if track_title != target_title_clean:
                return False
            
            # Check if target artist is in the track's artists
            track_artists = [artist['name'].lower().strip() for artist in track['artists']]
            target_artist_clean = target_artist.lower().strip()
            
            # Handle featuring artists - check if main artist matches
            main_artist = track_artists[0] if track_artists else ''
            
            # Exact match on main artist or any artist
            return target_artist_clean == main_artist or target_artist_clean in track_artists
            
        except Exception as e:
            print(f"Error checking exact match: {e}")
            return False

    def _is_fuzzy_match(self, track: dict, target_artist: str, target_title: str, is_title_only_search: bool = False) -> bool:
        """Check if track is a reasonable fuzzy match.

        Thresholds:
        - Title: 0.75 (75%) - allows for version markers like (Clean), (Dirty), (Radio Edit)
        - Artist: 0.85 (85%) - allows for minor variations in artist names (0.70 for title-only searches)

        For title-only searches (when artist filter fails), we're more lenient with artist matching
        since the title match is our primary signal.
        """
        try:
            import re

            # Get track details for logging
            track_title_str = track.get('name', '')
            track_artists_str = ', '.join([a['name'] for a in track.get('artists', [])])
            album_name = track.get('album', {}).get('name', '')

            # Title similarity
            track_title = track['name'].lower().strip()
            target_title_clean = target_title.lower().strip()

            # Remove all version markers and featured artist info from both titles for comparison
            def clean_title_for_matching(title):
                """Remove version markers, featured artists, etc. for fuzzy matching."""
                # Remove featured artist info in parentheses: (feat. ...), (with ...), etc.
                title = re.sub(r'\s*[\(\[].*?(feat|with|ft\.?|&).*?[\)\]]\s*', ' ', title, flags=re.IGNORECASE)
                # Remove common version markers: (Clean), [Remix], - Remaster, etc.
                title = re.sub(r'\s*[\(\[].*?[\)\]]\s*', ' ', title)
                title = re.sub(r'\s*-\s*(.*?(remix|remaster|version|mix|edit|cover).*?)$', '', title, flags=re.IGNORECASE)
                return re.sub(r'\s+', ' ', title).strip()

            # Clean both titles for matching
            track_title_clean = clean_title_for_matching(track_title)
            target_title_clean_base = clean_title_for_matching(target_title_clean)

            # Try matching with cleaned titles first
            title_similarity = self._string_similarity(track_title_clean, target_title_clean_base)

            # If still not matching, try against original target
            if title_similarity < 0.75:
                title_similarity = self._string_similarity(track_title, target_title_clean)

            # Final attempt with simplified target
            if title_similarity < 0.75:
                simplified_target = re.sub(r'\s*[\(\[].*?[\)\]]\s*', ' ', target_title_clean)
                simplified_target = re.sub(r'\s*-\s*(.*?(remix|remaster|version|mix|edit|cover).*?)$', '', simplified_target, flags=re.IGNORECASE)
                simplified_target = simplified_target.strip()
                if simplified_target != target_title_clean:
                    title_similarity = self._string_similarity(track_title, simplified_target)

            if title_similarity < 0.75:
                if is_title_only_search:
                    rejection_msg = f"      Rejected: title similarity {title_similarity:.2f} < 0.75 | Title: '{track_title_str}' | Artist: '{track_artists_str}' | Album: '{album_name}'"
                    print(rejection_msg)
                    if self.debug_logger:
                        self.debug_logger.info(rejection_msg)
                return False

            # Artist similarity
            track_artists = [artist['name'].lower().strip() for artist in track['artists']]
            target_artist_clean = target_artist.lower().strip()

            # For title-only searches, be more lenient with artist matching
            # If title is a perfect match (1.00), lower the threshold further since title is the primary signal
            if is_title_only_search and title_similarity >= 0.99:
                artist_threshold = 0.40  # Very lenient for perfect title matches (collaborative tracks)
            elif is_title_only_search:
                artist_threshold = 0.70  # Lenient for title-only searches
            else:
                artist_threshold = 0.85  # Strict for artist+title searches

            # Check similarity with any of the track artists
            best_artist_similarity = 0
            for artist in track_artists:
                artist_similarity = self._string_similarity(target_artist_clean, artist)
                best_artist_similarity = max(best_artist_similarity, artist_similarity)
                if artist_similarity > artist_threshold:
                    if is_title_only_search:
                        threshold_reason = ""
                        if title_similarity >= 0.99:
                            threshold_reason = " (perfect title → relaxed threshold)"
                        print(f"      ✓ Title-only match: title sim {title_similarity:.2f}, artist '{artist}' sim {artist_similarity:.2f} > {artist_threshold}{threshold_reason}")
                    return True

            if is_title_only_search:
                threshold_reason = ""
                if title_similarity >= 0.99:
                    threshold_reason = " (perfect title match → relaxed threshold)"
                rejection_msg = f"      Rejected: title sim {title_similarity:.2f}, best artist sim {best_artist_similarity:.2f} <= {artist_threshold}{threshold_reason} | Title: '{track_title_str}' | Artist: '{track_artists_str}' | Album: '{album_name}'"
                print(rejection_msg)
                if self.debug_logger:
                    self.debug_logger.info(rejection_msg)
            return False

        except Exception as e:
            print(f"Error checking fuzzy match: {e}")
            return False

    def _is_likely_compilation(self, album_name: str) -> bool:
        """Detect if album is likely a compilation or various-artists album.

        Heuristics:
        - Album contains keywords: 'compilation', 'various', 'mixtape', 'vol', 'volume', 'collection'
        - Album name suggests multi-artist: 'Hits', 'Best of', 'Greatest', 'Collection'
        """
        album_lower = album_name.lower()
        compilation_keywords = [
            'compilation', 'various', 'mixtape', 'vol', 'volume', 'collection',
            'hits', 'best of', 'greatest', 'anthology', 'greatest hits'
        ]

        for keyword in compilation_keywords:
            if keyword in album_lower:
                print(f"  Likely compilation: '{album_name}' contains keyword '{keyword}'")
                return True

        return False

    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity."""
        if not str1 or not str2:
            return 0.0

        if str1 == str2:
            return 1.0

        import difflib
        return difflib.SequenceMatcher(None, str1, str2).ratio()

    def _extract_track_metadata(self, track: dict) -> Dict:
        """Extract metadata from Spotify track object."""
        try:
            # Get basic track info
            metadata = {
                'title': track['name'],
                'artist': ', '.join(artist['name'] for artist in track['artists']),
                'album': track['album']['name'],
                'year': '',
                'spotify_id': track['id'],
                'genre': '',  # Not available in basic track info
                'comments': '',
                'rating': ''  # Will be populated from popularity if available
            }

            # Extract year from release date
            release_date = track['album'].get('release_date', '')
            if release_date:
                try:
                    metadata['year'] = release_date.split('-')[0]  # Get year part
                except:
                    pass

            # Extract Spotify popularity (0-100 scale) and convert to Serato 0-5 star rating
            if 'popularity' in track:
                try:
                    # Spotify popularity is 0-100, convert to 0-5 stars, then to Serato POPM values
                    # Serato DJ 4.0 only allows full star ratings with specific POPM values:
                    # 0 stars = 0, 1 star = 1, 2 stars = 64, 3 stars = 128, 4 stars = 196, 5 stars = 255
                    popularity = int(track['popularity'])

                    # Convert to stars (0-5) using proper rounding
                    stars = round(popularity / 100.0 * 5)

                    # Map stars to Serato POPM rating values
                    star_to_rating = {0: 0, 1: 1, 2: 64, 3: 128, 4: 196, 5: 255}
                    serato_rating = star_to_rating.get(stars, 0)

                    metadata['rating'] = str(serato_rating)
                    print(f"Converted Spotify popularity {popularity} to {stars} stars (Serato rating {serato_rating})")
                except Exception as e:
                    print(f"Error converting popularity: {e}")

            return metadata

        except Exception as e:
            print(f"Error extracting track metadata: {e}")
            return {}

    def get_track_info(self, spotify_id: str) -> Optional[Dict]:
        """Get detailed track information by Spotify ID."""
        try:
            if not spotify_id:
                return None
                
            track = self._make_request(f'tracks/{spotify_id}')
            if track:
                return self._extract_track_metadata(track)
                
            return None
            
        except Exception as e:
            print(f"Error getting track info: {e}")
            return None

    def get_album_info(self, album_id: str) -> Optional[Dict]:
        """Get album information by Spotify ID."""
        try:
            if not album_id:
                return None
                
            album = self._make_request(f'albums/{album_id}')
            if not album:
                return None
                
            # Extract basic album info
            info = {
                'name': album['name'],
                'artist': ', '.join(artist['name'] for artist in album['artists']),
                'release_date': album.get('release_date', ''),
                'total_tracks': album.get('total_tracks', 0),
                'spotify_id': album['id']
            }
            
            return info
            
        except Exception as e:
            print(f"Error getting album info: {e}")
            return None

    def test_connection(self) -> bool:
        """Test if Spotify API connection is working."""
        try:
            # Try to get an access token
            token = self._get_access_token()
            if not token:
                return False
                
            # Try a simple search
            params = {
                'q': 'test',
                'type': 'track',
                'limit': 1
            }
            
            result = self._make_request('search', params)
            return result is not None
            
        except Exception as e:
            print(f"Spotify connection test failed: {e}")
            return False

    def clear_cache(self):
        """Clear Spotify cache."""
        if self.cache_manager:
            self.cache_manager.clear('spotify')