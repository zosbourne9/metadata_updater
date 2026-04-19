import musicbrainzngs
import time
import re
import logging
import socket
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable
from urllib.error import URLError
from rate_limiter import UnifiedRateLimiter

# Suppress musicbrainzngs debug spam messages
logging.getLogger('musicbrainzngs').setLevel(logging.ERROR)

class SimplifiedMusicBrainzIntegration:
    """
    Clean, efficient MusicBrainz integration focused on getting original studio releases.
    
    Strategy:
    1. Search recordings with exact artist/title
    2. Filter to studio albums only (no live/remix/compilation)  
    3. Pick earliest studio release
    4. Fallback to fuzzy search only if needed
    """
    
    def __init__(self, parent=None, status_update_callback=None, cache_manager=None, debug_logger=None):
        self.parent = parent
        self.cache_manager = cache_manager
        self.status_update_callback = status_update_callback
        self.debug_logger = debug_logger  # Logger for detailed search debugging

        musicbrainzngs.set_useragent("MetadataUpdaterApp", "1.0", "info@djzrex.com")

        # Disable musicbrainzngs built-in rate limiting - we handle it ourselves
        musicbrainzngs.set_rate_limit(False)

        # Set socket timeout to prevent hanging on large responses (30 seconds)
        import socket as socket_module
        socket_module.setdefaulttimeout(30)

        # Initialize rate limiting
        self.rate_limiter = UnifiedRateLimiter()
        self.api_call_count = 0

        # Track connection errors separately for diagnostics
        self.connection_error_count = 0

        print("Simplified MusicBrainz integration initialized")

    def emit_status(self, message):
        """Emit status update through callback."""
        if self.status_update_callback:
            try:
                self.status_update_callback(message)
            except Exception as e:
                print(f"Error in status callback: {e}")
        else:
            print(message)

    def _api_call(self, method_name, *args, **kwargs):
        """Make MusicBrainz API calls with rate limiting and exponential backoff.

        Important: On retries, we skip the rate limiter and use exponential backoff instead.
        This prevents "double waiting" - i.e., waiting 4s for rate limit + 5s for retry.

        Retries are triggered by:
        - Connection reset/timeout (socket/network errors)
        - HTTP errors (5xx server errors)

        But NOT by:
        - Successful responses with empty results
        - 404 errors (not found)
        """
        max_retries = 3
        retries = 0

        while retries < max_retries:
            try:
                # Only use rate limiter on first attempt, not on retries
                if retries == 0:
                    self.rate_limiter.wait_if_needed('musicbrainz')

                # Get the method and make the call
                method = getattr(musicbrainzngs, method_name)
                response = method(*args, **kwargs)
                self.api_call_count += 1

                # Reset error count on success
                self.connection_error_count = 0
                return response

            except (socket.error, socket.timeout, URLError, ConnectionError, TimeoutError) as e:
                # Connection-level errors (network issues)
                retries += 1
                self.connection_error_count += 1
                error_type = type(e).__name__
                error_msg = f"Status: Connection error in MusicBrainz API call (attempt {retries}/{max_retries}): {error_type}: {e}"
                self.emit_status(error_msg)
                print(error_msg)

                if retries == max_retries:
                    print(f"Failed after {max_retries} connection attempts")
                    return None

                # Exponential backoff with jitter: base delay + random component
                base_delay = min(60, 5 * (2 ** (retries - 1)))
                jitter = random.uniform(0, base_delay * 0.1)  # Up to 10% jitter
                delay = base_delay + jitter

                print(f"Connection error (attempt {retries}/{max_retries}). Retrying in {delay:.1f}s...")
                time.sleep(delay)

            except Exception as e:
                # Other errors (API errors, parsing errors, etc.)
                retries += 1
                error_type = type(e).__name__
                error_msg = f"Status: Error in MusicBrainz API call (attempt {retries}/{max_retries}): {error_type}: {e}"
                self.emit_status(error_msg)
                print(error_msg)

                if retries == max_retries:
                    print(f"Failed after {max_retries} attempts")
                    return None

                # Exponential backoff with jitter for non-connection errors too
                base_delay = min(60, 5 * (2 ** (retries - 1)))
                jitter = random.uniform(0, base_delay * 0.1)
                delay = base_delay + jitter

                print(f"API error (attempt {retries}/{max_retries}). Retrying in {delay:.1f}s...")
                time.sleep(delay)

        return None

    def search_metadata(self, artist_name: str, track_title: str) -> Optional[Dict]:
        """Main search method."""
        try:
            print(f"\nSimplified MusicBrainz search: {artist_name} - {track_title}")
            
            # Check cache first
            if self.cache_manager:
                cached = self.cache_manager.get_metadata(artist_name, track_title)
                if cached:
                    print("Found cached metadata")
                    return cached

            # 1. Try exact search first
            metadata = self._exact_search(artist_name, track_title)
            if metadata:
                print("Found via exact search")
                # NOTE: Caching is now handled by SimplifiedMetadataSearcher after genre lookup
                return metadata
                
            # 2. Try with cleaned artist name (remove features)
            clean_artist = self._clean_artist_name(artist_name)
            if clean_artist != artist_name:
                print(f"Trying with clean artist name: {clean_artist}")
                metadata = self._exact_search(clean_artist, track_title)
                if metadata:
                    print("Found via clean artist search")
                    # NOTE: Caching is now handled by SimplifiedMetadataSearcher after genre lookup
                    return metadata

            # 3. Try with cleaned title (remove parenthetical content)
            clean_title = self._clean_title(track_title)
            if clean_title != track_title:
                print(f"Trying with clean title: {clean_title}")
                metadata = self._exact_search(artist_name, clean_title)
                if metadata:
                    print("Found via clean title search")
                    # NOTE: Caching is now handled by SimplifiedMetadataSearcher after genre lookup
                    return metadata

                # Also try with both clean artist and clean title
                if clean_artist != artist_name:
                    print(f"Trying with both clean artist and title: {clean_artist} - {clean_title}")
                    metadata = self._exact_search(clean_artist, clean_title)
                    if metadata:
                        print("Found via clean artist and title search")
                        # NOTE: Caching is now handled by SimplifiedMetadataSearcher after genre lookup
                        return metadata

            # 4. Try fuzzy search as last resort
            print("Falling back to fuzzy search")
            # Use cleaned artist and title for fuzzy search to ensure consistent results
            # regardless of version markers (Clean/Dirty/Explicit) or featuring artists
            fuzzy_artist = self._clean_artist_name(artist_name)
            fuzzy_title = self._clean_title(track_title)
            metadata = self._fuzzy_search(fuzzy_artist, fuzzy_title)
            # NOTE: Caching is now handled by SimplifiedMetadataSearcher after genre lookup

            return metadata
            
        except Exception as e:
            print(f"Error in search_metadata: {e}")
            return None

    def _exact_search(self, artist: str, title: str) -> Optional[Dict]:
        """Exact search with proper studio release filtering."""
        try:
            # Simple, targeted query
            query = f'artist:"{artist}" AND recording:"{title}"'
            print(f"Exact search query: {query}")
            
            response = self._api_call('search_recordings', query=query, limit=25)
            if not response or 'recording-list' not in response:
                return None

            recordings = response['recording-list']
            
            # Filter and rank candidates
            candidates = []
            for recording in recordings:
                if self._is_exact_match(recording, artist, title):
                    score = self._score_recording(recording, artist)
                    candidates.append((recording, score))
            
            # Return best candidate
            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                best_recording = candidates[0][0]
                return self._extract_metadata(best_recording)
                
            return None
            
        except Exception as e:
            print(f"Error in exact search: {e}")
            return None

    def _get_title_variations(self, title: str) -> list:
        """Generate title variations to handle plurals and minor variations.

        For example: "Ribbon In The Sky" -> ["Ribbon In The Sky", "Ribbons In The Sky"]
        Also tries modifications on first significant word: "Ribbon" -> "Ribbons"
        """
        variations = [title]
        words = title.split()

        if not words:
            return variations

        # Try plural modifications on each word
        for i, word in enumerate(words):
            # Skip small words
            if len(word) <= 2:
                continue

            # Try adding 's' if not present
            if not word.endswith('s'):
                new_words = words.copy()
                new_words[i] = word + 's'
                variations.append(' '.join(new_words))
            # Try removing 's' if present
            elif word.endswith('s') and len(word) > 2:
                new_words = words.copy()
                new_words[i] = word[:-1]
                variations.append(' '.join(new_words))

        return variations

    def _fuzzy_search(self, artist: str, title: str) -> Optional[Dict]:
        """Fuzzy search for cases where exact search fails.

        Strategy:
        1. Start with small limit (20) to avoid connection resets on large result sets
        2. Try title variations (plurals, etc.) if initial search yields only bad releases
        3. Use aggressive title cleaning for better matching
        4. If title-based search yields only bad releases, try artist-only search
        """
        try:
            # Broader search - start with small limit to reduce payload size
            query = f'artist:{artist} AND recording:{title}'
            print(f"Fuzzy search query: {query}")

            # First attempt: small limit (20) to reduce response size and connection issues
            response = self._api_call('search_recordings', query=query, limit=20)
            if not response or 'recording-list' not in response:
                return None

            recordings = response['recording-list']

            # More lenient matching and scoring
            candidates = []
            for recording in recordings:
                if self._is_fuzzy_match(recording, artist, title):
                    score = self._score_recording(recording, artist)

                    # BOOST: Prefer recordings where the search artist is the MAIN artist (not featuring)
                    # Extract recording's main artist
                    rec_main_artist = None
                    if 'artist-credit' in recording:
                        for credit in recording['artist-credit']:
                            if isinstance(credit, dict) and 'artist' in credit:
                                rec_main_artist = credit['artist']['name'].lower().strip()
                                break

                    # If the recording's main artist matches the search artist exactly, boost the score
                    search_artist_clean = artist.lower().strip()
                    if rec_main_artist and self._string_similarity(rec_main_artist, search_artist_clean) > 0.85:
                        score += 50  # Significant boost for exact main artist match

                    candidates.append((recording, score))

            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                best_recording = candidates[0][0]
                best_score = candidates[0][1]
                metadata = self._extract_metadata(best_recording)
                if metadata:
                    return metadata

                # If extract_metadata returned None AND we had a high-quality fuzzy match (>= 90),
                # it means MusicBrainz has the recording but only bootleg/low-quality releases.
                # Don't waste time on title variations - go straight to Spotify fallback.
                if best_score >= 90:
                    print(f"Found good recording match (score {best_score}) but only bootleg/low-quality releases. Falling back to Spotify...")
                    return None

                # If extract_metadata returned None but the fuzzy match score was weak (< 90),
                # try searching with different title variations first
                print(f"Best recording has weak match (score {best_score}). Trying title variations...")

                # Try title variations (e.g., singular/plural)
                for title_variation in self._get_title_variations(title)[1:]:  # Skip first one (original)
                    print(f"Trying title variation: {title_variation}")
                    query = f'artist:{artist} AND recording:{title_variation}'
                    var_response = self._api_call('search_recordings', query=query, limit=20)
                    if var_response and 'recording-list' in var_response:
                        var_recordings = var_response['recording-list']

                        for recording in var_recordings:
                            if self._is_fuzzy_match(recording, artist, title_variation):
                                score = self._score_recording(recording, artist)
                                metadata = self._extract_metadata(recording)
                                if metadata:
                                    print(f"Found acceptable metadata with title variation: {metadata.get('album')}")
                                    return metadata

            # Fallback: try with just the first/primary artist if we have multiple artists
            # Extract the first artist name (before comma or &)
            primary_artist = artist.split(',')[0].split('&')[0].strip()

            if primary_artist != artist and len(primary_artist) > 2:
                print(f"Multi-artist query failed. Trying primary artist only: {primary_artist}")
                primary_query = f'artist:{primary_artist} AND recording:{title}'
                primary_response = self._api_call('search_recordings', query=primary_query, limit=25)
                if primary_response and 'recording-list' in primary_response:
                    primary_recordings = primary_response['recording-list']

                    for recording in primary_recordings:
                        if self._is_fuzzy_match(recording, primary_artist, title):
                            score = self._score_recording(recording, primary_artist)
                            if score > 100:
                                metadata = self._extract_metadata(recording)
                                if metadata:
                                    print(f"Found acceptable release via primary artist search: {metadata.get('album')}")
                                    return metadata

            # Fallback: search by artist only, but FILTER for recordings that share words with the original title
            print(f"Falling back to full artist-only search with title filtering: {artist}")
            artist_query = f'artist:{artist}'
            artist_response = self._api_call('search_recordings', query=artist_query, limit=100)
            if artist_response and 'recording-list' in artist_response:
                artist_recordings = artist_response['recording-list']

                # Extract title words to filter results
                title_words = set(title.lower().split())
                title_words.discard('bonehead')  # Remove common noise words
                title_words = [w for w in title_words if len(w) > 2]  # Keep only meaningful words

                # Look for recordings that:
                # 1. Share words with the original title (fuzzy match)
                # 2. Have good releases (score > 100)
                for recording in artist_recordings:
                    rec_title = recording.get('title', '').lower()

                    # Check if recording title shares any words with the search title
                    rec_words = set(rec_title.split())
                    shared_words = rec_words.intersection(title_words)

                    if shared_words or self._is_fuzzy_match(recording, artist, title):
                        score = self._score_recording(recording, artist)
                        if score > 100:  # Only consider recordings with positive scores
                            metadata = self._extract_metadata(recording)
                            if metadata:
                                print(f"Found acceptable release via artist-only search: {metadata.get('album')}")
                                return metadata

            # Final fallback: try searching with just the first word of the title
            # This handles cases where title spelling is completely different but shares keywords
            title_words = title.split()
            if title_words and len(title_words[0]) > 3:
                first_word = title_words[0]
                print(f"Final fallback: searching for artist + first word only: {artist} + {first_word}")
                keyword_query = f'artist:{artist} AND recording:{first_word}'
                keyword_response = self._api_call('search_recordings', query=keyword_query, limit=30)
                if keyword_response and 'recording-list' in keyword_response:
                    keyword_recordings = keyword_response['recording-list']

                    for recording in keyword_recordings:
                        # Verify main artist matches
                        main_artist_match = False
                        if 'artist-credit' in recording:
                            for credit in recording['artist-credit']:
                                if isinstance(credit, dict) and 'artist' in credit:
                                    rec_artist = credit['artist']['name'].lower().strip()
                                    if self._string_similarity(rec_artist, artist.lower().strip()) > 0.80:
                                        main_artist_match = True
                                        break

                        if not main_artist_match:
                            continue

                        score = self._score_recording(recording, artist)
                        if score > 100:
                            metadata = self._extract_metadata(recording)
                            if metadata:
                                print(f"Found acceptable release via keyword search: {metadata.get('album')}")
                                return metadata

            return None

        except Exception as e:
            print(f"Error in fuzzy search: {e}")
            return None

    def _is_exact_match(self, recording: dict, target_artist: str, target_title: str) -> bool:
        """Check if recording is an exact match."""
        try:
            # Check title
            recording_title = recording.get('title', '').lower().strip()
            target_title_clean = target_title.lower().strip()
            
            if recording_title != target_title_clean:
                return False
            
            # Check artist
            if 'artist-credit' not in recording:
                return False
                
            target_artist_clean = target_artist.lower().strip()

            # Require target artist to be the FIRST (main) artist in artist-credit
            # This prevents matching recordings where target artist is only a featuring artist
            # Use substring/prefix matching to handle partial names (e.g., "tyler" → "tyler, the creator")
            for credit in recording['artist-credit']:
                if isinstance(credit, dict) and 'artist' in credit:
                    first_artist = credit['artist']['name'].lower().strip()
                    # Allow exact match or substring match (e.g., "tyler" in "tyler, the creator")
                    return (target_artist_clean == first_artist or
                            target_artist_clean in first_artist or
                            first_artist in target_artist_clean)

            return False
            
        except Exception as e:
            print(f"Error in exact match check: {e}")
            return False

    def _is_fuzzy_match(self, recording: dict, target_artist: str, target_title: str) -> bool:
        """Check if recording is a reasonable fuzzy match.

        Smarter fuzzy matching that handles:
        - Featured artist variations (feat., with, &)
        - Title variations (parentheses, brackets, dashes)
        - Multi-artist collaborations
        """
        try:
            # Title fuzzy match (allow some variation)
            recording_title = recording.get('title', '').lower().strip()
            target_title_clean = target_title.lower().strip()

            # Get recording artists for logging
            recording_artists = []
            for credit in recording.get('artist-credit', []):
                if isinstance(credit, dict) and 'artist' in credit:
                    recording_artists.append(credit['artist']['name'].lower().strip())

            recording_artists_str = ', '.join(recording_artists) if recording_artists else 'N/A'

            # Get album info if available (from first release)
            album_name = 'N/A'
            if recording.get('release-list'):
                album_name = recording['release-list'][0].get('title', 'N/A')

            title_similarity = self._string_similarity(recording_title, target_title_clean)

            # Improved threshold: be more lenient with title matches
            # since fuzzy matching already means exact didn't work
            if not title_similarity > 0.75:  # Relaxed from 0.8 to 0.75
                if self.debug_logger:
                    rejection_msg = f"    REJECTED: Title similarity {title_similarity:.2f} < 0.75 | Title: '{recording_title}' | Artist: '{recording_artists_str}' | Album: '{album_name}'"
                    self.debug_logger.info(rejection_msg)
                return False

            # Artist fuzzy match
            if 'artist-credit' not in recording:
                if self.debug_logger:
                    rejection_msg = f"    REJECTED: No artist-credit | Title: '{recording_title}' | Album: '{album_name}'"
                    self.debug_logger.info(rejection_msg)
                return False

            recording_artists = []
            for credit in recording['artist-credit']:
                if isinstance(credit, dict) and 'artist' in credit:
                    recording_artists.append(credit['artist']['name'].lower().strip())

            target_artist_clean = target_artist.lower().strip()

            # Check if any artist is similar enough
            # Use more lenient matching for very short artist names
            similarity_threshold = 0.70 if len(target_artist_clean) <= 5 else 0.80  # Slightly more lenient

            for artist in recording_artists:
                similarity = self._string_similarity(target_artist_clean, artist)
                if similarity > similarity_threshold:
                    return True
                # Also check for exact word match (useful for short names like "Total")
                if target_artist_clean.lower() in artist.lower() or artist.lower() in target_artist_clean.lower():
                    if len(target_artist_clean) <= 6:  # Only for short artist names
                        return True

            if self.debug_logger:
                recording_artists_str = ', '.join(recording_artists) if recording_artists else 'N/A'
                rejection_msg = f"    REJECTED: No artist similarity above threshold | Title: '{recording_title}' | Artist: '{recording_artists_str}' | Album: '{album_name}'"
                self.debug_logger.info(rejection_msg)
            return False

        except Exception as e:
            print(f"Error in fuzzy match check: {e}")
            return False

    def _string_similarity(self, str1: str, str2: str) -> float:
        """Calculate simple string similarity using longest common subsequence."""
        if not str1 or not str2:
            return 0.0
            
        if str1 == str2:
            return 1.0
            
        # Simple character-based similarity
        import difflib
        return difflib.SequenceMatcher(None, str1, str2).ratio()

    def _score_recording(self, recording: dict, target_artist: str = None) -> int:
        """Simple scoring: prefer studio albums, penalize live/remix.

        Added: penalize releases that are not by the recording's main artist
        (e.g. various-artist compilations) so we don't pick wrong albums like
        compilation inclusions.

        CRITICAL: This scoring also boosts recordings that have access to very
        early original releases (e.g. 1980s originals), since different recordings
        of the same song may have different release lists.
        """
        try:
            score = 100

            if 'release-list' not in recording:
                return score

            # Determine the recording's main artist (first artist-credit)
            main_artist = None
            if 'artist-credit' in recording:
                for credit in recording['artist-credit']:
                    if isinstance(credit, dict) and 'artist' in credit:
                        main_artist = credit['artist']['name'].lower().strip()
                        break

            best_release_score = 0
            earliest_year = None

            for release in recording['release-list']:
                release_score = 100
                release_title = release.get('title', '').lower()

                # CRITICAL: Check if recording's first artist (main artist) matches search artist
                # This prevents selecting recordings featuring the target artist instead of recordings by the target artist
                # Use fuzzy matching + substring check to handle partial names (e.g., "tyler" → "tyler, the creator")
                if target_artist and main_artist:
                    target_clean = target_artist.lower().strip()
                    similarity = self._string_similarity(target_clean, main_artist)
                    is_substring = target_clean in main_artist or main_artist in target_clean
                    if similarity < 0.5 and not is_substring:
                        release_score -= 100  # Heavy penalty for genuinely wrong main artist

                # Heavy penalties for non-studio releases
                penalties = [
                    ('live', -60),
                    ('remix', -50),
                    ('compilation', -60),
                    ('greatest', -60),
                    ('best of', -60),
                    ('collection', -60),  # Added for "CD-Collection"
                    ('oldies', -60),      # Added for "Oldies"
                    ('hits', -60),        # Added for hits collections
                    ('anthology', -60),   # Added for anthologies
                    ('mixtape', -30),
                    ('karaoke', -50),
                    ('instrumental', -20),
                    ('cover', -30),
                    ('volume', -40),      # Added for multi-volume sets
                    ('vol.', -40),        # Added for "Vol."
                    ('disc', -30),        # Added for multi-disc sets
                ]

                for keyword, penalty in penalties:
                    if keyword in release_title:
                        release_score += penalty
                        break  # Only apply one major penalty

                # Bonuses for studio indicators
                release_group = release.get('release-group', {})
                primary_type = release_group.get('primary-type', '').lower()

                if primary_type == 'album':
                    release_score += 40
                elif primary_type == 'single':
                    release_score += 20
                elif primary_type == 'ep':
                    release_score += 10

                # Check for secondary types (compilation, mixtape, etc.)
                secondary_types = release_group.get('secondary-type-list', [])
                compilation_secondary_types = ['compilation', 'soundtrack', 'remix', 'mixtape']
                for sec_type in secondary_types:
                    if sec_type.lower() in compilation_secondary_types:
                        # Mixtapes should be penalized similar to compilations
                        if sec_type.lower() == 'mixtape':
                            release_score -= 80
                        else:
                            release_score -= 70  # Heavy penalty for compilation secondary types
                        break  # Only apply one secondary type penalty

                # Prefer older releases (original vs reissue)
                try:
                    date_str = release.get('date', '')
                    if date_str and len(date_str) >= 4:
                        year = int(date_str[:4])
                        # Track the earliest year we find across all releases
                        if earliest_year is None or year < earliest_year:
                            earliest_year = year

                        if 1950 <= year <= 1990:
                            release_score += 30  # Classic era
                        elif 1990 < year <= 2000:
                            release_score += 20  # 90s
                        elif 2000 < year <= 2010:
                            release_score += 10  # 2000s
                        elif year > 2020:
                            release_score -= 10  # Very recent (likely reissue/live)
                except (ValueError, TypeError):
                    pass

                # Check release status
                if release.get('status') == 'Official':
                    release_score += 10

                # Penalize releases that are not primarily by the recording's main artist
                try:
                    release_artist_names = []
                    if 'artist-credit' in release:
                        for credit in release['artist-credit']:
                            if isinstance(credit, dict) and 'artist' in credit:
                                release_artist_names.append(credit['artist']['name'].lower().strip())
                    elif 'artist' in release and isinstance(release['artist'], dict):
                        release_artist_names.append(release['artist'].get('name', '').lower().strip())

                    if main_artist and release_artist_names:
                        # If main artist not credited on the release, heavy penalty
                        if main_artist not in release_artist_names:
                            release_score -= 80
                            # Extra penalty for Various Artists style releases
                            if any('various' in name for name in release_artist_names):
                                release_score -= 20
                except Exception:
                    pass

                best_release_score = max(best_release_score, release_score)

            # CRITICAL BONUS: If this recording has access to very early original releases,
            # boost the recording score significantly. This ensures we pick the recording
            # that can lead us to the original 1982 release, not just compilations.
            if earliest_year:
                try:
                    if 1975 <= earliest_year <= 1985:
                        # This recording has a genuine 1980s original - huge bonus!
                        best_release_score += 50
                        print(f"  Recording has earliest release from {earliest_year} - adding +50 bonus")
                    elif 1960 <= earliest_year < 1975:
                        # Even older original
                        best_release_score += 60
                        print(f"  Recording has earliest release from {earliest_year} - adding +60 bonus")
                except (ValueError, TypeError):
                    pass

            return score + best_release_score
            
        except Exception as e:
            print(f"Error scoring recording: {e}")
            return 50  # Neutral score

    def _extract_metadata(self, recording: dict) -> Optional[Dict]:
        """Extract metadata from the best recording."""
        try:
            # Find the best release for this recording
            best_release = self._find_best_release(recording)
            if not best_release:
                return None
                
            # Handle featured artists
            main_artist = None
            featuring_artists = []
            
            if 'artist-credit' in recording:
                for i, credit in enumerate(recording['artist-credit']):
                    if isinstance(credit, dict) and 'artist' in credit:
                        artist_name = credit['artist']['name']
                        if i == 0:
                            main_artist = artist_name
                        else:
                            featuring_artists.append(artist_name)

            # Handle featuring artists - include them in the artist name
            final_artist = main_artist or ''
            if featuring_artists:
                print(f"Found featuring artists: {featuring_artists}")
                # In webview context, always include featuring artists
                if len(featuring_artists) == 1:
                    final_artist = f"{main_artist} feat. {featuring_artists[0]}"
                else:
                    features_str = ", ".join(featuring_artists[:-1]) + " & " + featuring_artists[-1]
                    final_artist = f"{main_artist} feat. {features_str}"

            # Extract year from release date
            year = ''
            if best_release.get('date'):
                try:
                    date_str = best_release['date']
                    if len(date_str) >= 4:
                        year_val = int(date_str[:4])
                        # Validate year is reasonable (1900-current year + 2)
                        import datetime
                        current_year = datetime.datetime.now().year
                        if 1900 <= year_val <= current_year + 2:
                            year = str(year_val)
                except (ValueError, TypeError):
                    pass

            # Fallback: if no year found, try to get from any other release
            if not year and 'release-list' in recording:
                for release in recording['release-list']:
                    if release.get('date'):
                        try:
                            date_str = release['date']
                            if len(date_str) >= 4:
                                year_val = int(date_str[:4])
                                import datetime
                                current_year = datetime.datetime.now().year
                                if 1900 <= year_val <= current_year + 2:
                                    year = str(year_val)
                                    print(f"Using fallback year {year} from alternate release")
                                    break
                        except (ValueError, TypeError):
                            continue

            metadata = {
                'title': recording.get('title', ''),
                'artist': final_artist,
                'album': best_release.get('title', ''),
                'year': year,
                'genre': '',  # Will be filled by genre detection
                'comments': '',
                'rating': ''  # MusicBrainz doesn't provide track ratings
            }

            print(f"Extracted metadata: {metadata}")
            return metadata
            
        except Exception as e:
            print(f"Error extracting metadata: {e}")
            return None

    def _find_best_release(self, recording: dict) -> Optional[Dict]:
        """Find the best release for this recording.

        Use the recording's main artist when scoring releases so we avoid
        selecting various-artist compilations or releases that don't credit
        the recording's artist.
        """
        try:
            if 'release-list' not in recording:
                return None
            
            releases = recording['release-list']
            if not releases:
                return None

            # Determine recording's main artist (first artist-credit)
            main_artist = None
            if 'artist-credit' in recording:
                for credit in recording['artist-credit']:
                    if isinstance(credit, dict) and 'artist' in credit:
                        main_artist = credit['artist']['name'].lower().strip()
                        break

            # Get the recording's track title for release scoring
            track_title = recording.get('title', '')

            # Group releases by release-group ID to avoid duplicate fetches
            print(f"Found {len(releases)} total releases")
            release_groups_seen = {}
            release_group_data = {}
            release_dates = {}  # Store dates from enriched releases

            # First pass: group by release-group and pick one rep per group
            for release in releases:
                rg = release.get('release-group', {})
                rg_id = rg.get('id') if rg else None

                if rg_id and rg_id not in release_groups_seen:
                    release_groups_seen[rg_id] = release

            # Second pass: enrich only unique release-groups (not every single release!)
            print(f"Deduped to {len(release_groups_seen)} unique release-groups (fetching details for these only)")
            for rg_id, representative_release in release_groups_seen.items():
                rg = representative_release.get('release-group', {}) or {}
                sec_types = rg.get('secondary-type-list', [])

                # If secondary types not present, fetch full release details ONCE per group
                if (not sec_types or sec_types == []) and representative_release.get('id'):
                    try:
                        enriched = self._api_call('get_release_by_id', representative_release.get('id'), includes=['release-groups'])
                        if enriched and 'release' in enriched:
                            enriched_release = enriched['release']

                            # Store enriched release-group info for this group
                            enriched_rg = enriched_release.get('release-group')
                            if enriched_rg:
                                release_group_data[rg_id] = enriched_rg

                            # CRITICAL: Fetch the full release-group to get ALL releases (original + reissues)
                            # This lets us find the earliest date across all editions
                            earliest_date = None
                            if enriched_release.get('date'):
                                earliest_date = enriched_release['date']

                            # Try to fetch the full release-group with all releases
                            try:
                                rg_enriched = self._api_call('get_release_group_by_id', rg_id, includes=['releases'])
                                if rg_enriched and 'release-group' in rg_enriched:
                                    rg_data = rg_enriched['release-group']
                                    if 'release-list' in rg_data:
                                        release_list = rg_data['release-list']
                                        print(f"  Found {len(release_list)} releases in release-group {rg_id}")
                                        for rel in release_list:
                                            rel_date = rel.get('date')
                                            if rel_date:
                                                try:
                                                    # Compare dates as strings (YYYY-MM-DD format compares correctly)
                                                    if earliest_date is None or rel_date < earliest_date:
                                                        earliest_date = rel_date
                                                        print(f"    New earliest: {rel_date}")
                                                except (TypeError, ValueError):
                                                    pass
                                    else:
                                        print(f"  Release-group {rg_id} has no release-list")
                                else:
                                    print(f"  Failed to fetch full release-group {rg_id}")
                            except Exception as rg_err:
                                print(f"  Could not fetch release-group {rg_id}: {rg_err}")
                                # Fallback: use what we have from the single release
                                print(f"  Falling back to single release date: {earliest_date}")

                            if earliest_date:
                                release_dates[rg_id] = earliest_date
                                # Log if we found a different (earlier) date than the initial capture
                                if enriched_release.get('date') and earliest_date != enriched_release.get('date'):
                                    print(f"  Found earlier date '{earliest_date}' (vs initial '{enriched_release['date']}') for release-group {rg_id}")
                                else:
                                    print(f"  Captured date '{earliest_date}' for release-group {rg_id}")
                    except Exception:
                        pass

            # Third pass: score all releases using the enriched data
            scored_releases = []
            for release in releases:
                # Apply enriched release-group data if available
                rg = release.get('release-group', {})
                rg_id = rg.get('id') if rg else None
                if rg_id and rg_id in release_group_data:
                    release['release-group'] = release_group_data[rg_id]

                # Apply enriched date if available
                if rg_id and rg_id in release_dates:
                    release['date'] = release_dates[rg_id]

                # Score using up-to-date release info
                score = self._score_release(release, main_artist, track_title)
                scored_releases.append((release, score))
            
            # Sort by score and return the best
            scored_releases.sort(key=lambda x: x[1], reverse=True)

            # CRITICAL: Reject releases below minimum acceptable score
            # A score < 100 indicates a compilation, mixtape, various-artist release, or other poor match
            # Using such a release is worse than returning None and letting Spotify handle it
            # Scores >= 100 indicate genuine studio albums with strong confidence
            MIN_ACCEPTABLE_SCORE = 100
            if scored_releases and scored_releases[0][1] >= MIN_ACCEPTABLE_SCORE:
                best_release = scored_releases[0][0]
                print(f"Best release: {best_release.get('title')} (score: {scored_releases[0][1]})")
                return best_release
            else:
                # No acceptable release found (best score below minimum)
                best_score = scored_releases[0][1] if scored_releases else 'N/A'
                print(f"No acceptable release found (best score: {best_score}, minimum required: {MIN_ACCEPTABLE_SCORE})")
                return None
            
        except Exception as e:
            print(f"Error finding best release: {e}")
            # Safe fallback: return first release if available
            try:
                return recording.get('release-list', [None])[0]
            except Exception:
                return None

    def _score_release(self, release: dict, main_artist: Optional[str]=None, track_title: Optional[str]=None) -> int:
        """Score a single release.

        Accepts optional `main_artist` (lowercased) so we can penalize releases
        that do not credit the recording's main artist (e.g. various-artist
        compilations).

        Accepts optional `track_title` so we can boost releases whose title
        matches the track (e.g. the "Nasty" single for the track "Nasty").
        """
        try:
            score = 100
            release_title = release.get('title', '').lower()
            
            # Penalties for non-studio releases
            penalties = [
                ('live', -60),
                ('remix', -50),
                ('compilation', -60),
                ('greatest', -60),
                ('best of', -60),
                ('collection', -60),  # Added for "CD-Collection"
                ('oldies', -60),      # Added for "Oldies"
                ('hits', -60),        # Added for hits collections
                ('anthology', -60),   # Added for anthologies
                ('now that\'s what i call', -80),  # Heavy penalty for "Now That's What I Call Music"
                ('now thats what i call', -80),    # Alternative spelling
                ('promo only', -70),   # Added for promo releases
                ('chart hits', -60),   # Added for chart compilation
                ('radio hits', -60),   # Added for radio compilation
                ('top hits', -60),     # Added for top hits compilation
                ('pop hits', -60),     # Added for pop hits compilation
                ('ultimate', -50),     # Added for ultimate collections
                ('essential', -50),    # Added for essential collections
                ('platinum', -40),     # Added for platinum collections (often compilations)
                ('gold', -40),         # Added for gold collections
                ('anniversary', -25),  # Penalty for anniversary editions (reissues, not originals)
                ('mixtape', -30),
                ('deluxe', -10),       # Minor penalty for deluxe
                ('remaster', -10),     # Minor penalty for remaster
                ('volume', -40),       # Added for multi-volume sets
                ('vol.', -40),         # Added for "Vol."
                ('disc', -30),         # Added for multi-disc sets
            ]
            
            for keyword, penalty in penalties:
                if keyword in release_title:
                    score += penalty
            
            # Bonuses
            release_group = release.get('release-group', {})
            primary_type = release_group.get('primary-type', '').lower()
            secondary_types = release_group.get('secondary-type-list', [])

            if primary_type == 'album':
                score += 50  # Increased bonus for albums
            elif primary_type == 'single':
                score += 20  # Increased bonus for singles

            # Check for compilation / mixtape indicators in secondary types
            compilation_secondary_types = ['compilation', 'soundtrack', 'remix', 'mixtape']
            for sec_type in secondary_types:
                if sec_type.lower() in compilation_secondary_types:
                    # Mixtapes should be penalized similar to compilations
                    if sec_type.lower() == 'mixtape':
                        score -= 80
                    else:
                        score -= 70  # Heavy penalty for compilation secondary types

            # Prefer official releases
            if release.get('status') == 'Official':
                score += 10

            # Strong preference for original studio albums (no secondary types)
            # BUT only if the title doesn't contain compilation keywords
            # (MusicBrainz doesn't always flag compilations in secondary types)
            compilation_title_keywords = [
                'hits', 'greatest', 'best of', 'collection', 'oldies',
                'anthology', 'compilation', 'now that', 'chart',
                'ultimate', 'essential', 'platinum', 'gold',
                'promo only', 'volume', 'vol.',
            ]
            title_looks_like_compilation = any(kw in release_title for kw in compilation_title_keywords)
            if primary_type == 'album' and not secondary_types and not title_looks_like_compilation:
                score += 30  # Extra bonus for pure studio albums
                
            # Prefer releases with dates (crucial for metadata extraction!)
            date_str = release.get('date', '')
            has_date = bool(date_str and len(date_str) >= 4)

            if has_date:
                score += 20  # Bonus for having a date at all
                try:
                    year = int(date_str[:4])
                    # Validate year is reasonable (1900-current year + 2)
                    import datetime
                    current_year = datetime.datetime.now().year
                    if 1900 <= year <= current_year + 2:
                        # Prefer original releases (earlier years get bonuses)
                        # Penalize later releases (likely reissues/anniversary editions)
                        if 1950 <= year <= 1975:
                            score += 30  # Classic era originals (highest preference)
                        elif 1975 < year <= 1990:
                            score += 25  # Later originals
                        elif 1990 < year <= 2005:
                            score += 15  # Modern originals
                        elif 2005 < year <= 2010:
                            score += 5   # Late 2000s originals
                        elif year > 2010:
                            # Penalize 2010+ releases (likely reissues, compilations, anniversary editions)
                            score -= 10  # Penalty for recent releases
                except (ValueError, TypeError):
                    pass
            else:
                # Penalize releases without dates (can't extract year!)
                score -= 15

            # Penalize or reward based on release-group / release artist credits to prefer true album releases
            try:
                if main_artist:
                    # Try release-level artist-credit first
                    release_artist_names = []
                    if 'artist-credit' in release:
                        for credit in release['artist-credit']:
                            if isinstance(credit, dict) and 'artist' in credit:
                                release_artist_names.append(credit['artist']['name'].lower().strip())

                    # If release-group provides artist-credit, prefer that as it's more authoritative
                    rg = release.get('release-group') or {}
                    rg_artist_names = []
                    if rg and isinstance(rg, dict) and 'artist-credit' in rg:
                        for credit in rg['artist-credit']:
                            if isinstance(credit, dict) and 'artist' in credit:
                                rg_artist_names.append(credit['artist']['name'].lower().strip())

                    # Choose the best source of artist names
                    artist_names_to_check = rg_artist_names or release_artist_names

                    # If we have artist names, apply rewards/penalties
                    if artist_names_to_check:
                        # If the first credited artist equals main artist -> strong bonus
                        if artist_names_to_check[0] == main_artist:
                            score += 60
                        # If main artist appears anywhere in the release/group -> moderate bonus
                        elif main_artist in artist_names_to_check:
                            score += 20
                        else:
                            # If main artist not credited on the release/group, heavy penalty
                            score -= 80
                            if any('various' in name for name in artist_names_to_check):
                                score -= 20
            except Exception:
                pass
                
            # Bonus when release title matches the track title (e.g. "Nasty" single for track "Nasty")
            # This strongly favors the actual single/EP release over compilation albums containing the track
            if track_title:
                track_title_clean = track_title.lower().strip()
                if release_title.strip() == track_title_clean:
                    score += 40  # Strong bonus for exact title match
                elif track_title_clean in release_title or release_title in track_title_clean:
                    score += 15  # Moderate bonus for partial match

            # Log release-level debug info to explain scoring decisions
            try:
                release_artist_names = []
                if 'artist-credit' in release:
                    for credit in release['artist-credit']:
                        if isinstance(credit, dict) and 'artist' in credit:
                            release_artist_names.append(credit['artist']['name'])
                elif 'artist' in release and isinstance(release['artist'], dict):
                    release_artist_names.append(release['artist'].get('name', ''))

                rg = release.get('release-group') or {}
                rg_artists = []
                if rg and isinstance(rg, dict) and 'artist-credit' in rg:
                    for credit in rg['artist-credit']:
                        if isinstance(credit, dict) and 'artist' in credit:
                            rg_artists.append(credit['artist']['name'])
            except Exception:
                release_artist_names = []
                rg_artists = []

            print(f"    Release debug: title='{release.get('title','')}', primary_type='{primary_type}', secondary={secondary_types}, status='{release.get('status')}', date='{release.get('date')}', release_artists={release_artist_names}, release_group_artists={rg_artists}, final_score={score}")

            return score
            
        except Exception as e:
            print(f"Error scoring release: {e}")
            return 50

    def _clean_artist_name(self, artist_name: str) -> str:
        """Remove featuring artists and clean up artist name."""
        try:
            # Simple cleanup - remove everything after "feat", "featuring", "ft.", etc.
            import re
            patterns = [
                r'\s+feat\.?\s+.*',
                r'\s+featuring\s+.*',
                r'\s+ft\.?\s+.*',
                r'\s+f\.?\s+.*',  # Added: "f." and "f" as featuring
                r'\s+with\s+.*',
                r'\s*\([^)]*feat[^)]*\)',
                r'\s*\([^)]*f\.?[^)]*\)',  # Added: parenthetical "f."
            ]

            cleaned = artist_name
            for pattern in patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

            return cleaned.strip()

        except Exception as e:
            print(f"Error cleaning artist name: {e}")
            return artist_name

    def _clean_title(self, title: str) -> str:
        """
        Remove version qualifiers from title for better search matching.

        Removes markers like (Clean), (Dirty), (Explicit), (Radio Edit) but
        KEEPS remix versions like (SheMix), (Artist Remix) because these
        represent substantively different recordings.
        """
        try:
            import re

            # Only remove version markers, NOT remix designations
            # Version markers to remove: Clean, Dirty, Explicit, Radio Edit, Album Version, etc.
            version_markers = [
                r'\s*\(\s*clean\s*\)',
                r'\s*\(\s*dirty\s*\)',
                r'\s*\(\s*explicit\s*\)',
                r'\s*\(\s*radio\s+edit\s*\)',
                r'\s*\(\s*album\s+version\s*\)',
                r'\s*\(\s*extended\s+mix\s*\)',
                r'\s*\(\s*intro\s+clean\s*\)',
                r'\s*\(\s*intro\s+dirty\s*\)',
                r'\s*\(\s*version\s*\)',
                r'\s*\(\s*remaster(?:ed)?\s*\)',
                r'\s*\[\s*clean\s*\]',
                r'\s*\[\s*dirty\s*\]',
                r'\s*\[\s*explicit\s*\]',
                r'\s*\[\s*radio\s+edit\s*\]',
                r'\s*\[\s*album\s+version\s*\]',
                # Only remove "-remix", "-remaster" style suffixes at end of title
                r'\s*-\s*(?:remaster(?:ed)?|dub).*$',
            ]

            cleaned = title
            for pattern in version_markers:
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

            # Clean up extra whitespace
            cleaned = ' '.join(cleaned.split())
            return cleaned.strip()

        except Exception as e:
            print(f"Error cleaning title: {e}")
            return title

    def get_artist_genres_from_mb(self, artist_name: str) -> Optional[tuple]:
        """Get artist genres from MusicBrainz."""
        try:
            print(f"Getting artist genres for: {artist_name}")
            
            # Search for artist
            response = self._api_call('search_artists', query=f'artist:"{artist_name}"', limit=10)
            if not response or 'artist-list' not in response:
                return None
            
            # Find best matching artist
            best_artist = None
            best_score = 0
            
            for artist in response['artist-list']:
                artist_name_mb = artist.get('name', '').lower()
                target_name = artist_name.lower()
                
                similarity = self._string_similarity(artist_name_mb, target_name)
                if similarity > best_score:
                    best_score = similarity
                    best_artist = artist
            
            if not best_artist or best_score < 0.8:
                print(f"No good artist match found (best score: {best_score})")
                return None
            
            # Get detailed artist info with tags
            artist_id = best_artist['id']
            artist_detail = self._api_call('get_artist_by_id', artist_id, includes=['tags'])
            
            if not artist_detail or 'artist' not in artist_detail:
                return None
            
            # Process tags
            artist_data = artist_detail['artist']
            if 'tag-list' not in artist_data:
                return None
            
            genre_tags = []
            for tag in artist_data['tag-list']:
                if tag.get('name'):
                    tag_name = tag['name'].lower()
                    count = int(tag.get('count', 0))
                    if count > 0:
                        genre_tags.append((tag_name, count))
            
            if not genre_tags:
                return None
            
            # Sort by popularity and process
            genre_tags.sort(key=lambda x: x[1], reverse=True)
            primary_genre, subgenres = self._process_genre_tags(genre_tags)
            
            if primary_genre:
                return primary_genre, ', '.join(subgenres) if subgenres else ''
            
            return None
            
        except Exception as e:
            print(f"Error getting artist genres: {e}")
            return None

    def _process_genre_tags(self, genre_tags: list) -> tuple:
        """Process genre tags to determine primary genre and subgenres.
        
        Uses tag count (popularity/frequency) to determine which genres are most significant.
        The highest-count tag becomes primary, remaining tags become subgenres.
        """
        try:
            # Genre mapping - Dancehall is its own primary genre (not under Reggae)
            genre_mappings = {
                'hip hop': 'Hip-Hop',
                'hip-hop': 'Hip-Hop',
                'rap': 'Hip-Hop',
                'r&b': 'R&B',
                'rnb': 'R&B',
                'soul': 'Soul',
                'pop': 'Pop',
                'rock': 'Rock',
                'reggae': 'Reggae',
                'dancehall': 'Dancehall',  # Dancehall is a distinct primary genre
                'dub': 'Dub',  # Dub is its own genre
                'roots reggae': 'Reggae',
                'ragga': 'Ragga',  # Ragga is distinct from Reggae/Dancehall
                'funk': 'Funk',
                'jazz': 'Jazz',
                'blues': 'Blues',
                'electronic': 'Electronic',
                'dance': 'Electronic',
                'house': 'Electronic',
                'soca': 'Soca',
                'afrobeats': 'Afrobeats'
            }
            
            # Filter to only tags that have genre mappings
            mapped_tags = []
            for tag_name, count in genre_tags:
                if tag_name in genre_mappings:
                    mapped_genre = genre_mappings[tag_name]
                    mapped_tags.append((tag_name, count, mapped_genre))
            
            if not mapped_tags:
                return '', []
            
            # Sort by count (popularity) in descending order - most popular first
            mapped_tags.sort(key=lambda x: x[1], reverse=True)
            
            # First mapped tag (highest count) becomes primary
            primary_genre = mapped_tags[0][2]
            
            # Collect remaining genres as subgenres, avoiding duplicates and the primary
            subgenres = set()
            for tag_name, count, mapped_genre in mapped_tags[1:]:
                if mapped_genre != primary_genre:
                    subgenres.add(mapped_genre)
            
            return primary_genre, sorted(list(subgenres))[:3]  # Limit subgenres
            
        except Exception as e:
            print(f"Error processing genre tags: {e}")
            return '', []
    def clear_cache(self):
        """Clear MusicBrainz cache."""
        if self.cache_manager:
            self.cache_manager.clear('musicbrainz')

    def health_check(self) -> bool:
        """Check if MusicBrainz API is accessible.

        Returns:
            True if API is accessible, False otherwise
        """
        try:
            # Try a simple artist search - MusicBrainz's simplest endpoint
            response = self._api_call('search_artists', query='artist:beatles', limit=1)
            if response and 'artist-list' in response:
                return True
            else:
                return False
        except Exception as e:
            print(f"✗ MusicBrainz API health check failed: {e}")
