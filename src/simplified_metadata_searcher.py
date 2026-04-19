from typing import Optional, Dict
import logging
from simplified_mb_integration import SimplifiedMusicBrainzIntegration
from simplified_spotify_integration import SimplifiedSpotifyIntegration
from artist_normalizer import ArtistNormalizer
from title_normalizer import TitleNormalizer
from enhanced_genre_detector import EnhancedGenreDetector
from constants import OPENROUTER_API_KEY
from riddim_scraper import get_riddim_scraper

# Get the search logger (created in metadata_updater_webview)
SEARCH_LOGGER = logging.getLogger('search_debug')

class SimplifiedMetadataSearcher:
    """
    Simple coordinator that tries sources in order and intelligently merges results.
    
    Strategy:
    1. Try MusicBrainz first (more reliable for metadata, especially genres)
    2. Try Spotify for additional info (modern catalog coverage)
    3. Use AI for genre detection when MusicBrainz doesn't have genre info
    4. Merge results intelligently (MusicBrainz takes precedence for accuracy)
    """
    
    def __init__(self, parent=None, status_update_callback=None, cache_manager=None):
        self.cache_manager = cache_manager

        self.musicbrainz = SimplifiedMusicBrainzIntegration(
            parent=parent,
            status_update_callback=status_update_callback,
            cache_manager=cache_manager,
            debug_logger=SEARCH_LOGGER
        )

        self.spotify = SimplifiedSpotifyIntegration(
            cache_manager=cache_manager,
            status_update_callback=status_update_callback,
            debug_logger=SEARCH_LOGGER
        )

        self.artist_normalizer = ArtistNormalizer()
        self.title_normalizer = TitleNormalizer()

        # Initialize AI genre detector for fallback genre detection
        try:
            self.ai_genre_detector = EnhancedGenreDetector(api_key=OPENROUTER_API_KEY)
        except Exception as e:
            print(f"Warning: AI genre detector not initialized: {e}")
            self.ai_genre_detector = None

        # Store last search results for candidate review
        self.last_mb_result = None
        self.last_spotify_result = None

        print("Simplified metadata searcher initialized")

    def _should_prefer_spotify_album(self, mb_album: str, sp_album: str) -> bool:
        """
        Intelligently determine if Spotify's album is more canonical/correct than MusicBrainz's.

        Strategy:
        - Only keep MB if it looks MORE reliable than Spotify
        - Otherwise prefer Spotify (has more comprehensive/current catalog)

        Returns: True if Spotify should be preferred, False to keep MB
        """
        mb_lower = mb_album.lower()
        sp_lower = sp_album.lower()

        # Keywords that indicate compilations/bootlegs/unreliable sources
        # These are "red flags" that make MB look unreliable
        mb_red_flags = ['house of blues', 'bootleg', 'greatest hits', 'best of', 'collection', 'the essential']

        # Keywords that might indicate more reliable Spotify data
        sp_confidence_markers = ["cosmo's factory", "seal", "signed"]

        mb_has_red_flag = any(flag in mb_lower for flag in mb_red_flags)
        sp_has_confidence_marker = any(marker in sp_lower for marker in sp_confidence_markers)

        # Rule 1: If MB looks like a bootleg/compilation, definitely prefer Spotify
        if mb_has_red_flag:
            print(f"  → MB album looks unreliable ('{mb_album}'), using Spotify")
            return True

        # Rule 2: Spotify has specific album name that sounds more "canonical", use it
        if sp_has_confidence_marker:
            print(f"  → Spotify has recognizable album ('{sp_album}')")
            return True

        # Rule 3: By default, prefer Spotify because:
        # - Spotify has more comprehensive/current catalog coverage
        # - MusicBrainz sometimes has incomplete or incorrect album associations
        # - Spotify's metadata is kept up-to-date by millions of users
        print(f"  → Defaulting to Spotify for better catalog coverage")
        return True

    def search_metadata(self, artist_name: str, track_title: str, riddim_mode: Dict = None) -> Optional[Dict]:
        """
        Main search method that coordinates between services.

        Args:
            artist_name: Name of the artist
            track_title: Title of the track
            riddim_mode: Dict with riddim mode flags (isDancehall, isReggae).
                        When enabled, ONLY uses RiddimGuide scraper, skips other sources.
        """
        try:
            print(f"\n=== SEARCHING METADATA ===")
            print(f"Artist: {artist_name}")
            print(f"Title: {track_title}")

            # Normalize riddim_mode parameter
            if riddim_mode is None:
                riddim_mode = {'isDancehall': False, 'isReggae': False}

            is_riddim_mode = riddim_mode.get('isDancehall', False) or riddim_mode.get('isReggae', False)

            if is_riddim_mode:
                riddim_type = "Dancehall" if riddim_mode.get('isDancehall') else "Reggae"
                print(f"🎵 RIDDIM MODE ACTIVE: {riddim_type}")
                print("--- Trying RiddimGuide Scraper First ---")
                riddim_result = self._search_riddim_metadata(artist_name, track_title, riddim_type)

                if riddim_result:
                    # Found on RiddimGuide, return it
                    print("✅ RiddimGuide found the song")
                    return riddim_result
                else:
                    # Not found on RiddimGuide, fall back to regular search
                    print("⚠️  Song not found on RiddimGuide, falling back to regular search (MusicBrainz/Spotify)")
                    # Continue with normal search flow below
                    pass

            normalized_artist = self.artist_normalizer.clean_artist_name(artist_name)
            print(f"Normalized Artist: {normalized_artist}")

            # Normalize title to handle special characters and leetspeak
            # e.g., "$ave Dat Money" → "Save Dat Money", "Café" → "Cafe"
            # IMPORTANT: Keep original title to search Spotify with special chars intact
            original_title = track_title
            normalized_title = self.title_normalizer.normalize_title(track_title)
            if normalized_title != track_title:
                print(f"Normalized Title: {normalized_title}")

            # Remove version qualifiers for better search matching
            # Keeps remixes like (SheMix) but removes (Clean), (Dirty), etc.
            search_title = self.title_normalizer.remove_version_qualifiers(normalized_title)
            if search_title != normalized_title:
                print(f"Search Title (version qualifiers removed): {search_title}")

            mb_result = None
            spotify_result = None

            # 1. Try MusicBrainz first (more reliable for metadata)
            print("\n--- Trying MusicBrainz ---")
            SEARCH_LOGGER.info(f"\n🎵 MUSICBRAINZ SEARCH")
            SEARCH_LOGGER.info(f"  Query: Artist='{normalized_artist}' | Title='{search_title}'")
            try:
                mb_result = self.musicbrainz.search_metadata(normalized_artist, search_title)
                if mb_result:
                    print(f"MusicBrainz found: {mb_result}")
                    SEARCH_LOGGER.info(f"  ✅ FOUND:")
                    SEARCH_LOGGER.info(f"    Title: {mb_result.get('title', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Artist: {mb_result.get('artist', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Album: {mb_result.get('album', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Year: {mb_result.get('year', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Genre: {mb_result.get('genre', 'N/A')}")
                else:
                    print("MusicBrainz: No results")
                    SEARCH_LOGGER.info(f"  ❌ NO RESULTS")
            except Exception as e:
                print(f"MusicBrainz search error: {e}")
                SEARCH_LOGGER.info(f"  ❌ ERROR: {e}")

            # Store MB result for candidate review
            self.last_mb_result = mb_result

            # 2. Try Spotify (for additional coverage)
            print("\n--- Trying Spotify ---")
            SEARCH_LOGGER.info(f"\n🎵 SPOTIFY SEARCH")
            SEARCH_LOGGER.info(f"  Query: Artist='{normalized_artist}' | Title='{search_title}'")
            try:
                # Pass original title to Spotify so it can search with special chars intact (e.g., "$ave Dat Money")
                spotify_result = self.spotify.search_metadata(normalized_artist, search_title, original_track_title=original_title)
                if spotify_result:
                    print(f"Spotify found: {spotify_result}")
                    SEARCH_LOGGER.info(f"  ✅ FOUND:")
                    SEARCH_LOGGER.info(f"    Title: {spotify_result.get('title', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Artist: {spotify_result.get('artist', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Album: {spotify_result.get('album', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Year: {spotify_result.get('year', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Genre: {spotify_result.get('genre', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Spotify ID: {spotify_result.get('spotify_id', 'N/A')}")
                    SEARCH_LOGGER.info(f"    Rating: {spotify_result.get('rating', 'N/A')}")
                else:
                    print("Spotify: No results")
                    SEARCH_LOGGER.info(f"  ❌ NO RESULTS")
            except Exception as e:
                print(f"Spotify search error: {e}")
                SEARCH_LOGGER.info(f"  ❌ ERROR: {e}")

            # Store Spotify result for candidate review
            self.last_spotify_result = spotify_result

            # 3. Merge results intelligently
            print("\n--- Merging Results ---")
            SEARCH_LOGGER.info(f"\n📊 MERGE RESULTS")
            SEARCH_LOGGER.info(f"  MusicBrainz result: {'✅ FOUND' if mb_result else '❌ NOT FOUND'}")
            SEARCH_LOGGER.info(f"  Spotify result: {'✅ FOUND' if spotify_result else '❌ NOT FOUND'}")

            # If we're in riddim mode but didn't find on RiddimGuide, preserve album field
            preserve_album = is_riddim_mode
            merged = self._merge_metadata(mb_result, spotify_result, normalized_artist, artist_name, track_title, preserve_album=preserve_album)

            if merged:
                print(f"Final merged result: {merged}")
                SEARCH_LOGGER.info(f"\n✅ FINAL MERGED RESULT:")
                SEARCH_LOGGER.info(f"  Title: {merged.get('title', 'N/A')}")
                SEARCH_LOGGER.info(f"  Artist: {merged.get('artist', 'N/A')}")
                SEARCH_LOGGER.info(f"  Album: {merged.get('album', 'N/A')}")
                SEARCH_LOGGER.info(f"  Year: {merged.get('year', 'N/A')}")
                SEARCH_LOGGER.info(f"  Genre: {merged.get('genre', 'N/A')}")
                SEARCH_LOGGER.info(f"  Rating: {merged.get('rating', 'N/A')}")
                # Cache the COMPLETE result (with genre populated) after merging
                # IMPORTANT: Cache with normalized/search values, not original filename values
                # This ensures cache lookups match between search and cache operations
                if self.cache_manager:
                    try:
                        self.cache_manager.set_metadata(normalized_artist, search_title, merged)
                    except Exception as e:
                        print(f"Error caching merged metadata: {e}")
            else:
                print("No metadata found from any source")
                SEARCH_LOGGER.info(f"\n❌ NO METADATA FOUND FROM ANY SOURCE")

            return merged

        except Exception as e:
            print(f"Error in search_metadata: {e}")
            return None

    def _merge_metadata(self, mb_data: Optional[Dict], spotify_data: Optional[Dict], normalized_artist: str, original_artist: str, track_title: str, preserve_album: bool = False) -> Optional[Dict]:
        """
        Intelligently combine data from both sources.
        MusicBrainz takes precedence for accuracy, Spotify fills gaps.
        Falls back to AI genre detection when needed.

        Args:
            preserve_album: If True, don't override album field (used for riddim fallback mode)
        """
        try:
            if not mb_data and not spotify_data:
                return None
                
            # Start with the better source
            if mb_data and spotify_data:
                print("Merging MusicBrainz + Spotify data")
                result = mb_data.copy()  # Start with MusicBrainz (more accurate)
            elif mb_data:
                print("Using MusicBrainz data only")
                result = mb_data.copy()
            else:
                print("Using Spotify data only")
                result = spotify_data.copy()
            
            # Fill in missing fields with Spotify data
            if spotify_data:
                for key in ['album', 'title']:
                    # Skip album if preserve_album is True (riddim fallback mode)
                    if preserve_album and key == 'album':
                        continue
                    if not result.get(key) and spotify_data.get(key):
                        result[key] = spotify_data[key]
                        print(f"Filled {key} from Spotify: {spotify_data[key]}")

                # Check for album discrepancy between sources
                mb_album = result.get('album', '').lower().strip()
                sp_album = spotify_data.get('album', '').lower().strip()
                if mb_album and sp_album and mb_album != sp_album:
                    # Only flag if they're genuinely different (not just case differences)
                    # and both are not empty/placeholder values
                    if mb_album not in sp_album and sp_album not in mb_album:
                        # Try intelligent matching before flagging for review
                        should_prefer_spotify = self._should_prefer_spotify_album(result.get('album', ''), spotify_data.get('album', ''))

                        if should_prefer_spotify:
                            # Spotify album is more canonical, use it instead of MB
                            result['album'] = spotify_data['album']
                            print(f"✅ Album intelligent match: using Spotify '{spotify_data.get('album')}' over MB '{result.get('album')}'")
                            SEARCH_LOGGER.info(f"  ✅ Album intelligent match: using Spotify '{spotify_data.get('album')}' (MB was '{mb_album}')")
                        else:
                            # Albums differ and we can't determine which is better - flag for review
                            print(f"⚠️  Album discrepancy detected: MB='{result.get('album')}' vs Spotify='{spotify_data.get('album')}'")
                            SEARCH_LOGGER.info(f"  ⚠️  Album mismatch: MB='{result.get('album')}' vs Spotify='{spotify_data.get('album')}' - flagging for review")
                            result['needs_review'] = True

                # Special handling for artist: prefer the one with MORE information (featured artists)
                mb_artist = result.get('artist', '')
                sp_artist = spotify_data.get('artist', '')
                if mb_artist and sp_artist:
                    # Count commas to determine artist completeness (more artists = more commas)
                    mb_count = mb_artist.count(',') + 1  # +1 because "artist1, artist2" has 1 comma but 2 artists
                    sp_count = sp_artist.count(',') + 1
                    if sp_count > mb_count:
                        result['artist'] = sp_artist
                        print(f"Using Spotify artist (more complete with {sp_count} artists): {sp_artist}")
                elif not mb_artist and sp_artist:
                    result['artist'] = sp_artist
                    print(f"Filled artist from Spotify: {sp_artist}")

                # Special handling for year: prefer the EARLIER year (more likely the original)
                if spotify_data.get('year'):
                    mb_year = result.get('year')
                    sp_year = spotify_data.get('year')
                    if mb_year and sp_year:
                        try:
                            mb_year_int = int(mb_year)
                            sp_year_int = int(sp_year)

                            # Check for year discrepancy (>5 years) - flag for manual review
                            year_diff = abs(mb_year_int - sp_year_int)
                            if year_diff > 5:
                                print(f"⚠️  Year discrepancy detected: MB={mb_year} vs Spotify={sp_year} ({year_diff} year gap)")
                                SEARCH_LOGGER.info(f"  ⚠️  Year mismatch: MB={mb_year} vs Spotify={sp_year} ({year_diff} year gap) - flagging for review")
                                result['needs_review'] = True

                            if sp_year_int < mb_year_int:
                                result['year'] = sp_year
                                print(f"Using Spotify year {sp_year} (earlier than MB year {mb_year})")
                        except (ValueError, TypeError):
                            pass
                    elif not result.get('year') and spotify_data.get('year'):
                        result['year'] = spotify_data['year']
                        print(f"Filled year from Spotify: {spotify_data['year']}")

                # Always preserve Spotify ID if available
                if spotify_data.get('spotify_id'):
                    result['spotify_id'] = spotify_data['spotify_id']

                # Use Spotify popularity as rating if available and not already present
                if not result.get('rating') and spotify_data.get('rating'):
                    result['rating'] = spotify_data['rating']
                    print(f"Filled rating from Spotify popularity: {spotify_data['rating']}")
            
            # Get genre information if missing
            if not result.get('genre'):
                print("No genre found, trying MusicBrainz artist lookup")
                try:
                    # Use the artist from the metadata result for better accuracy
                    lookup_artist = result.get('artist', normalized_artist)
                    print(f"Looking up genres for artist: {lookup_artist}")
                    artist_genres = self.musicbrainz.get_artist_genres_from_mb(lookup_artist)
                    if artist_genres and artist_genres[0]:
                        result['genre'] = artist_genres[0] or ''
                        result['subgenres'] = artist_genres[1] or ''
                        result['comments'] = artist_genres[1] or ''  # Also populate comments for backward compatibility
                        print(f"Added genres from MusicBrainz: {artist_genres}")
                        
                        # Check if MB returned only 1 genre - suggests limited data
                        if result['genre'] and not result['subgenres']:
                            print(f"Single genre from MB (limited data): {result['genre']} - using AI fallback")
                            try:
                                self._use_ai_genre_fallback(result, lookup_artist, track_title)
                            except Exception as ai_err:
                                print(f"AI fallback failed: {ai_err}")
                    else:
                        print(f"No genres found for artist: {lookup_artist}, trying AI genre detection")
                        # Fall back to AI genre detection
                        self._use_ai_genre_fallback(result, lookup_artist, track_title)
                except Exception as e:
                    print(f"Error getting artist genres: {e}")
                    # Try AI fallback if MusicBrainz lookup fails
                    try:
                        lookup_artist = result.get('artist', normalized_artist)
                        self._use_ai_genre_fallback(result, lookup_artist, track_title)
                    except Exception as ai_error:
                        print(f"AI fallback also failed: {ai_error}")
            
            # Ensure all required fields exist
            required_fields = ['title', 'artist', 'album', 'year', 'genre', 'comments', 'subgenres', 'rating']
            for field in required_fields:
                if field not in result:
                    result[field] = ''
            
            # Clean up the data
            result = self._clean_metadata(result)
            
            return result
            
        except Exception as e:
            print(f"Error merging metadata: {e}")
            return mb_data or spotify_data

    def _use_ai_genre_fallback(self, result: Dict, artist_name: str, track_title: str) -> None:
        """
        Use AI genre detection as fallback when MusicBrainz doesn't have genre info.
        Updates the result dict in-place with detected genre and subgenres.
        """
        try:
            if not self.ai_genre_detector:
                print("AI genre detector not available, skipping fallback")
                return
            
            print(f"Using AI genre detection for {artist_name} - {track_title}")
            
            # Get album name if available (useful for hints like "Get Soca 2017" which indicates Soca genre)
            album_name = result.get('album', '')
            if album_name:
                print(f"Including album context for genre detection: {album_name}")
            
            # Detect genre using AI with album context
            detected_genre, confidence = self.ai_genre_detector.detect_genre(artist_name, track_title, album_name=album_name)
            
            if detected_genre and confidence > 0.3:  # Only use if confidence is reasonable
                # Format the genre properly
                formatted_genre = self._format_genre(detected_genre)
                result['genre'] = formatted_genre
                
                # For subgenres, use the detected genre as is
                result['subgenres'] = detected_genre
                result['comments'] = detected_genre  # Also populate comments for backward compatibility
                
                print(f"AI detected genre: {formatted_genre} (confidence: {confidence:.2f})")
            else:
                print(f"AI genre detection confidence too low: {confidence:.2f}")
        except Exception as e:
            print(f"Error in AI genre fallback: {e}")

    def _clean_metadata(self, metadata: Dict) -> Dict:
        """Clean and normalize metadata."""
        try:
            cleaned = {}
            
            for key, value in metadata.items():
                if isinstance(value, str):
                    # Strip whitespace and normalize
                    cleaned_value = value.strip()
                    
                    # Special handling for year
                    if key == 'year' and cleaned_value:
                        try:
                            # Extract just the year part
                            year_str = cleaned_value.split('-')[0]  # Handle YYYY-MM-DD format
                            year = int(year_str)
                            if 1900 <= year <= 2030:  # Reasonable year range
                                cleaned_value = str(year)
                            else:
                                cleaned_value = ''
                        except (ValueError, IndexError):
                            cleaned_value = ''
                    
                    # Special handling for genre
                    elif key == 'genre' and cleaned_value:
                        cleaned_value = self._format_genre(cleaned_value)
                    
                    cleaned[key] = cleaned_value
                else:
                    cleaned[key] = value
            
            return cleaned
            
        except Exception as e:
            print(f"Error cleaning metadata: {e}")
            return metadata

    def _format_genre(self, genre: str) -> str:
        """Format genre with proper capitalization."""
        try:
            if not genre:
                return ""
                
            # Special cases for common genres
            special_cases = {
                'r&b': 'R&B',
                'rnb': 'R&B', 
                'rap': 'Hip-Hop',
                'hip hop': 'Hip-Hop',
                'hip-hop': 'Hip-Hop'
            }
            
            genre_lower = genre.lower().strip()
            if genre_lower in special_cases:
                return special_cases[genre_lower]
                
            # Standard capitalization
            return ' '.join(word.capitalize() for word in genre_lower.split())
            
        except Exception as e:
            print(f"Error formatting genre: {e}")
            return genre

    def search_musicbrainz_only(self, artist_name: str, track_title: str) -> Optional[Dict]:
        """Search using only MusicBrainz (for testing/comparison)."""
        try:
            result = self.musicbrainz.search_metadata(artist_name, track_title)
            
            # Add artist genres if not present
            if result and not result.get('genre'):
                try:
                    # Use the artist from the metadata result for better accuracy
                    lookup_artist = result.get('artist', artist_name)
                    print(f"Looking up genres for artist: {lookup_artist}")
                    artist_genres = self.musicbrainz.get_artist_genres_from_mb(lookup_artist)
                    if artist_genres:
                        result['genre'] = artist_genres[0] or ''
                        result['comments'] = artist_genres[1] or ''
                        print(f"Added genres from MusicBrainz: {artist_genres}")
                    else:
                        print(f"No genres found for artist: {lookup_artist}")
                except Exception as e:
                    print(f"Error getting artist genres: {e}")
            
            return result
            
        except Exception as e:
            print(f"Error in MusicBrainz-only search: {e}")
            return None

    def search_spotify_only(self, artist_name: str, track_title: str) -> Optional[Dict]:
        """Search using only Spotify (for testing/comparison)."""
        try:
            return self.spotify.search_metadata(artist_name, track_title)
        except Exception as e:
            print(f"Error in Spotify-only search: {e}")
            return None

    def _search_riddim_metadata(self, artist_name: str, track_title: str, riddim_type: str) -> Optional[Dict]:
        """
        Search for metadata using only RiddimGuide scraper (Dancehall/Reggae mode).
        Other search methods are disabled when this is active.

        Args:
            artist_name: Name of the artist (may contain multiple artists)
            track_title: Title of the track
            riddim_type: "Dancehall" or "Reggae"

        Returns:
            Dict with metadata from RiddimGuide or None if not found
        """
        try:
            scraper = get_riddim_scraper()

            # Clean up artist name - handle "Artist1, Artist2" format
            # For RiddimGuide, we want to search primarily by track title
            # with primary artist as context
            primary_artist = artist_name.split(',')[0].strip() if ',' in artist_name else artist_name.strip()

            # Try searches in order of preference
            search_queries = [
                f"{primary_artist} {track_title}",  # Primary artist + title
                track_title,  # Just title (often most effective for riddimguide)
                f"{artist_name} {track_title}",  # Full artist list + title
            ]

            songs = []
            search_query = ""

            for query in search_queries:
                print(f"Searching RiddimGuide for: {query}")
                songs = scraper.search(query)
                search_query = query

                if songs:
                    print(f"✅ RiddimGuide: Found {len(songs)} results")
                    break

            if not songs:
                print(f"❌ RiddimGuide: No results found with any query")
                return None

            # Take the first (best) result
            best_match = songs[0]
            print(f"Selected: {best_match['artist']} - {best_match['title']}")

            # Format metadata from RiddimGuide result
            riddim_name = best_match.get('riddim', '')
            album_value = f"Riddim: {riddim_name}" if riddim_name else ''

            result = {
                'title': best_match.get('title', track_title),
                'artist': best_match.get('artist', artist_name),
                'album': album_value,  # Album shows: "Riddim: [Name]"
                'year': best_match.get('year', ''),
                'genre': riddim_type,  # Set genre to Dancehall or Reggae
                'subgenres': f"{riddim_name} (Producer: {best_match.get('producer', 'Unknown')})".strip(),
                'comments': f"Riddim: {riddim_name} | Label: {best_match.get('label', 'Unknown')}",
                'rating': '',  # RiddimGuide doesn't provide ratings
                'source': 'riddimguide'
            }

            # Ensure all required fields exist
            required_fields = ['title', 'artist', 'album', 'year', 'genre', 'comments', 'subgenres', 'rating']
            for field in required_fields:
                if field not in result:
                    result[field] = ''

            print(f"RiddimGuide result: {result}")
            return result

        except Exception as e:
            print(f"❌ Error in RiddimGuide search: {e}")
            import traceback
            traceback.print_exc()
            return None

    def test_connections(self) -> Dict[str, bool]:
        """Test both service connections."""
        results = {}

        try:
            # Test MusicBrainz (simple search)
            mb_test = self.musicbrainz.search_metadata("The Beatles", "Yesterday")
            results['musicbrainz'] = mb_test is not None
        except:
            results['musicbrainz'] = False

        try:
            # Test Spotify
            results['spotify'] = self.spotify.test_connection()
        except:
            results['spotify'] = False

        return results

    def clear_all_caches(self):
        """Clear caches for both services."""
        try:
            self.musicbrainz.clear_cache()
            self.spotify.clear_cache()
            print("All caches cleared")
        except Exception as e:
            print(f"Error clearing caches: {e}")

    def get_service_stats(self) -> Dict:
        """Get statistics about service usage."""
        return {
            'musicbrainz_api_calls': getattr(self.musicbrainz, 'api_call_count', 0),
            'spotify_connected': hasattr(self.spotify, 'access_token') and self.spotify.access_token is not None
        }
