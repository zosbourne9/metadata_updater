import os
import json
import time
import re
import sys
from datetime import datetime
import shutil
from typing import Any, Dict, Optional, Tuple
from fuzzywuzzy import fuzz

class UnifiedCacheManager:
    """Centralized cache manager for the metadata updater application."""
    
    CACHE_TYPES = {
        'spotify': 'spotify_cache.json',
        'musicbrainz': 'musicbrainz_cache.json',
        'metadata': 'metadata_cache.json',
        'genre': 'genre_cache.json'
    }

    def __init__(self):
        # Get cache directory from environment or use default
        self.cache_dir = os.environ.get('CACHE_DIR', os.path.expanduser('~/Library/Application Support/Metadata Updater'))
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.caches: Dict[str, Dict] = {}
        self.last_backup = time.time()
        self.backup_frequency = 12 * 60 * 60  # 12 hours
        self.max_cache_age = 24 * 60 * 60  # 24 hours
        self.max_cache_size = 10000  # entries per cache type
        
        # Load all caches
        for cache_type in self.CACHE_TYPES:
            self.caches[cache_type] = self._load_cache(cache_type)
    
    def _get_cache_path(self, cache_type: str) -> str:
        """Get the full path for a specific cache file."""
        if cache_type not in self.CACHE_TYPES:
            raise ValueError(f"Invalid cache type: {cache_type}")
        return os.path.join(self.cache_dir, self.CACHE_TYPES[cache_type])

    def _load_cache(self, cache_type: str) -> Dict:
        """Load a specific cache from disk."""
        try:
            cache_path = self._get_cache_path(cache_type)
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                # Clean expired entries
                current_time = time.time()
                cache_data = {
                    k: v for k, v in cache_data.items()
                    if v.get('timestamp', 0) + self.max_cache_age > current_time
                }
                
                # Limit cache size
                if len(cache_data) > self.max_cache_size:
                    sorted_items = sorted(
                        cache_data.items(),
                        key=lambda x: x[1].get('timestamp', 0),
                        reverse=True
                    )
                    cache_data = dict(sorted_items[:self.max_cache_size])
                
                return cache_data
        except Exception as e:
            print(f"Error loading {cache_type} cache: {e}")
        return {}

    def _save_cache(self, cache_type: str) -> None:
        """Save a specific cache to disk."""
        try:
            cache_path = self._get_cache_path(cache_type)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.caches[cache_type], f, ensure_ascii=False, indent=2)
                
            # Create backup if needed
            current_time = time.time()
            if current_time - self.last_backup >= self.backup_frequency:
                self._create_backup(cache_type)
                self.last_backup = current_time
        except Exception as e:
            print(f"Error saving {cache_type} cache: {e}")

    def _create_backup(self, cache_type: str) -> None:
        """Create a backup of a specific cache file."""
        try:
            source_path = self._get_cache_path(cache_type)
            if os.path.exists(source_path):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = f"{source_path}.{timestamp}.bak"
                shutil.copy2(source_path, backup_path)
                
                # Clean old backups (keep last 5)
                backup_files = [
                    f for f in os.listdir(self.cache_dir)
                    if f.startswith(os.path.basename(source_path)) and f.endswith('.bak')
                ]
                if len(backup_files) > 5:
                    backup_files.sort()
                    for old_backup in backup_files[:-5]:
                        try:
                            os.remove(os.path.join(self.cache_dir, old_backup))
                        except Exception:
                            pass
        except Exception as e:
            print(f"Error creating backup for {cache_type}: {e}")

    # Metadata-specific methods
    def generate_metadata_key(self, artist_name: str, title: str) -> str:
        """Generate cache key using primary artist (first artist only) and cleaned title.

        This is much simpler and more reliable:
        - "Artist1, Artist2, Artist3" → "artist1"
        - "YAYA (SheMix) (Clean)" → "yaya"
        - Result: "artist1_yaya"
        """
        print(f"\nGenerating cache key:")
        print(f"Input artist: {artist_name}")
        print(f"Input title: {title}")

        # Extract PRIMARY ARTIST ONLY (first artist before any separator)
        # Handles: "Artist1, Artist2", "Artist1 & Artist2", "Artist1 feat Artist2", etc.
        primary_artist = artist_name.lower()

        # Split by common separators and take the first part
        for separator in [',', '&', '|', '/']:
            if separator in primary_artist:
                primary_artist = primary_artist.split(separator)[0].strip()
                break

        # Remove featuring/feat keywords and everything after
        primary_artist = re.sub(r'\s+(feat|ft|featuring|f\.?)\s+.*$', '', primary_artist)

        # Clean special characters
        primary_artist = re.sub(r"[^a-z0-9\s\-']", '', primary_artist)
        primary_artist = re.sub(r'\s+', ' ', primary_artist).strip()

        print(f"Primary artist: {primary_artist}")

        # CLEAN TITLE: Remove all version indicators and extra info
        base_title = title.lower()

        # Remove ALL version indicators and extra info (comprehensive pattern)
        # Handles: (Clean), (Dirty), (Intro Clean), (Intro Dirty), (Radio Edit), (Album Version), (SheMix), etc.
        version_keywords = r'(intro|clean|dirty|explicit|radio\s+edit|album\s+version|mix|remix|version|edit|audio|video|hd|4k|remaster)'
        base_title = re.sub(rf'\s*[\(\[].*?{version_keywords}.*?[\)\]]', '', base_title, flags=re.IGNORECASE)

        # Also remove standalone version indicators that might not be in parentheses
        base_title = re.sub(r'\s*-\s*(clean|dirty|explicit|remix|remaster|version|mix|edit).*$', '', base_title, flags=re.IGNORECASE)

        # Clean special characters from title
        normalized_title = re.sub(r'[^\w\s\-]', '', base_title)
        normalized_title = re.sub(r'\s+', ' ', normalized_title).strip()

        # Create simple title key (just use the cleaned title as-is)
        title_key = normalized_title if normalized_title else 'unknown'

        print(f"Cleaned title: {base_title}")
        print(f"Title key: {title_key}")

        # Combine for final key: "artist_title"
        key = f"{primary_artist}_{title_key}"
        print(f"Generated cache key: {key}")
        return key

    def get_metadata(self, artist_name: str, title: str) -> Optional[Dict]:
        """Get metadata for artist/title pair with enhanced validation and flexible matching."""
        key = self.generate_metadata_key(artist_name, title)
        data = self.get('metadata', key, fuzzy_match=True)
        
        # If we got data from cache, validate it
        if data:
            print("\n=== Cache Metadata Validation ===")
            # Must be a dictionary
            if not isinstance(data, dict):
                print(f"Invalid data type: {type(data)}")
                return None
                
            # Check required fields (relaxed requirements)
            required_fields = ['artist', 'album', 'year', 'genre']
            missing = [field for field in required_fields if field not in data or not data[field]]
            
            if missing:
                print(f"Missing required fields: {missing}")
                # Only return None if critical fields are missing
                critical_fields = ['artist', 'title']
                critical_missing = [field for field in critical_fields if field in missing]
                if critical_missing:
                    print(f"Critical fields missing: {critical_missing}")
                    return None
                # For non-critical fields, we'll add defaults
                
            # Ensure all required metadata fields are present
            validated_data = data.copy()

            # Add missing optional fields with defaults
            if 'comments' not in validated_data:
                validated_data['comments'] = ''
            if 'rating' not in validated_data:
                validated_data['rating'] = ''
            if 'title' not in validated_data:
                validated_data['title'] = title  # Use the requested title
            if 'original_title' not in validated_data:
                validated_data['original_title'] = validated_data.get('title', title)

            # Fill in any missing required fields with sensible defaults
            if 'album' not in validated_data or not validated_data['album']:
                validated_data['album'] = 'Unknown Album'
            if 'year' not in validated_data or not validated_data['year']:
                validated_data['year'] = ''
            if 'genre' not in validated_data or not validated_data['genre']:
                validated_data['genre'] = 'No Genre'

            print("Cache metadata validated and enhanced successfully")
            time.sleep(1)
            return validated_data
        
        return None
    
    def set_metadata(self, artist_name: str, title: str, metadata: Dict) -> None:
        """Set metadata using improved cache key with enhanced validation."""
        print(f"\nAttempting to set metadata in cache for: {artist_name} - {title}")
        if not isinstance(metadata, dict):
            print(f"Warning: Expected dict for metadata, got {type(metadata)}")
            return

        # Enhanced metadata validation - allow partial metadata
        validated_metadata = metadata.copy()
        
        # Ensure essential fields exist (but allow empty values for some)
        if 'artist' not in validated_metadata:
            validated_metadata['artist'] = artist_name
        if 'title' not in validated_metadata:
            validated_metadata['title'] = title
            
        # Fill in missing fields with defaults if needed
        if 'album' not in validated_metadata:
            validated_metadata['album'] = ''
        if 'year' not in validated_metadata:
            validated_metadata['year'] = ''
        if 'genre' not in validated_metadata:
            validated_metadata['genre'] = 'No Genre'
        if 'comments' not in validated_metadata:
            validated_metadata['comments'] = ''

        print(f"Validated metadata keys: {list(validated_metadata.keys())}")
        # Use the artist from the metadata dict for cache key generation to ensure consistency
        # This is especially important when the metadata contains a full artist name (e.g., "Cardi B feat. Tyla")
        # but we're searching with a normalized name (e.g., "cardi b")
        cache_artist = validated_metadata.get('artist', artist_name)
        key = self.generate_metadata_key(cache_artist, title)
        self.set('metadata', key, validated_metadata, preserve_existing=True)
        time.sleep(1)

    # General cache methods
    def get(self, cache_type: str, key: str, fuzzy_match: bool = False) -> Optional[Dict]:
        """Get a value from a specific cache."""
        start_time = time.time()
        print(f"\n=== Cache GET Operation ===")
        print(f"Cache Type: {cache_type}")
        print(f"Key: {key}")
        print(f"Fuzzy Match Enabled: {fuzzy_match}")
        
        try:
            if cache_type not in self.caches:
                print(f"Cache type '{cache_type}' not found in available caches: {list(self.caches.keys())}")
                return None
                
            cache = self.caches[cache_type]
            print(f"Cache size: {len(cache)} entries")
            
            # Try exact match first
            if key in cache:
                print(f"Found exact key match: {key}")
                data = cache[key]
                current_time = time.time()
                cache_age = current_time - data.get('timestamp', 0)
                
                print(f"Cache entry age: {cache_age:.2f} seconds")
                print(f"Max allowed age: {self.max_cache_age} seconds")
                
                if cache_age <= self.max_cache_age:
                    value = data.get('value')
                    print(f"Cache entry valid - Returning value type: {type(value)}")
                    if isinstance(value, dict):
                        print("Found cached dictionary data:")
                        for k, v in value.items():
                            print(f"  {k}: {v}")
                    return value
                else:
                    print("Cache entry expired")
                    
            # Try fuzzy matching if enabled
            if fuzzy_match:
                print("\nAttempting fuzzy matching...")
                best_match = None
                best_score = 0
                
                for cached_key, data in cache.items():
                    # Check age first
                    if data.get('timestamp', 0) + self.max_cache_age <= time.time():
                        print(f"Skipping expired entry: {cached_key}")
                        continue

                    # Split keys into artist and title components when possible
                    try:
                        if '_' in cached_key:
                            cached_artist, cached_title = cached_key.split('_', 1)
                        else:
                            cached_artist, cached_title = cached_key, ''
                    except Exception:
                        cached_artist, cached_title = cached_key, ''

                    try:
                        if '_' in key:
                            target_artist, target_title = key.split('_', 1)
                        else:
                            target_artist, target_title = key, ''
                    except Exception:
                        target_artist, target_title = key, ''

                    # Prefer to use the cached entry's reported artist (more reliable)
                    cached_value = data.get('value') if isinstance(data, dict) else None
                    cached_artist_field = ''
                    if isinstance(cached_value, dict):
                        cached_artist_field = cached_value.get('artist', '')

                    # Normalize artist/title tokens (remove punctuation/spaces for robust matching)
                    def _normalize_key_part(s: str) -> str:
                        import re
                        if not s:
                            return ''
                        ns = re.sub(r'[^a-z0-9]', '', s.lower())
                        return ns

                    # Compute artist/title specific similarity to avoid cross-artist matches
                    # Use cached artist field if present, otherwise fall back to key-parsed artist
                    artist_to_compare = cached_artist_field if cached_artist_field else cached_artist
                    
                    # Normalize for comparison (keep spaces to check for featuring relationships)
                    def _normalize_artist_for_featuring(s: str) -> str:
                        """Normalize artist string while preserving word boundaries for featuring check."""
                        import re
                        # Convert to lowercase and remove special chars but keep spaces
                        normalized = re.sub(r'[^a-z0-9\s]', '', s.lower())
                        # Normalize 'feat' variations to a standard token
                        normalized = re.sub(r'\b(ft|feat|featuring|f\.?)\b', 'feat', normalized)
                        # Clean up extra spaces
                        normalized = re.sub(r'\s+', ' ', normalized).strip()
                        return normalized
                    
                    normalized_target = _normalize_artist_for_featuring(target_artist)
                    normalized_cached = _normalize_artist_for_featuring(artist_to_compare)
                    
                    # Special handling for featuring artists: if target artist appears as a word in cached artist,
                    # treat it as a match (e.g., "cardi b" matches "cardi b feat tyla")
                    target_words = set(normalized_target.split())
                    cached_words = set(normalized_cached.split())
                    
                    # If target words are a subset of cached words (featuring case), boost the score
                    if target_words and target_words.issubset(cached_words) and target_words != {'feat'}:
                        # Main artist matches, just has additional features - strong match
                        artist_score = 90
                        print(f"  Featuring relationship detected: '{target_artist}' is core of '{artist_to_compare}'")
                    else:
                        # Use token set ratio for other cases
                        artist_score = fuzz.token_set_ratio(_normalize_key_part(target_artist), _normalize_key_part(artist_to_compare))
                    
                    title_score = fuzz.token_set_ratio(_normalize_key_part(target_title), _normalize_key_part(cached_title))

                    # Multiple scoring methods for overall matching (use normalized forms)
                    score = fuzz.ratio(key.lower(), cached_key.lower())
                    partial_score = fuzz.partial_ratio(key.lower(), cached_key.lower())
                    token_score = fuzz.token_set_ratio(key.lower(), cached_key.lower())
                    
                    # Use the highest score among the three methods
                    max_score = max(score, partial_score, token_score)
                    
                    print(f"Fuzzy match scores for '{cached_key}':")
                    print(f"  Overall - Ratio: {score}, Partial: {partial_score}, Token: {token_score}, Max: {max_score}")
                    print(f"  Artist score: {artist_score}, Title score: {title_score}")

                    # Require a stronger artist similarity to consider cross-artist fuzzy matches
                    # (prevents selecting entries for different artists that happen to share similar titles)
                    if artist_score < 75:
                        print(f"  Skipping '{cached_key}' due to low artist match: {artist_score}")
                        continue

                    # Enhanced matching logic for entries passing artist check
                    is_good_match = False

                    # Case 1: Very high overall similarity (80%+) AND good artist match
                    if max_score >= 80 and artist_score >= 75:
                        is_good_match = True
                    # Case 2: Good partial match for shortened/extended titles (75%+)
                    # Require decent artist similarity as well
                    elif partial_score >= 75 and (len(key) < len(cached_key) or len(cached_key) < len(key)) and artist_score >= 78:
                        is_good_match = True
                        max_score = partial_score  # Use partial score for this case
                    # Case 3: Excellent token match (85%+) for reordered words; require moderate artist similarity
                    elif token_score >= 85 and artist_score >= 72:
                        is_good_match = True
                        max_score = token_score
                    # Case 4: If artist is an excellent match and title token match is reasonable
                    elif artist_score >= 85 and title_score >= 65:
                        is_good_match = True
                        max_score = (artist_score + title_score) // 2

                    if is_good_match and max_score > best_score:

                        best_score = max_score
                        best_match = data.get('value')
                        print(f"New best match found - Score: {max_score}")
                        if isinstance(best_match, dict):
                            print("Best match data:")
                            for k, v in best_match.items():
                                print(f"  {k}: {v}")
                        
                if best_match:
                    print(f"Returning best fuzzy match (score: {best_score})")
                    return best_match
                else:
                    print("No suitable fuzzy matches found")
                    
            print("No matching cache entry found")
            return None
            
        except Exception as e:
            print(f"Error retrieving from {cache_type} cache: {e}")
            import traceback
            traceback.print_exc()
            return None
            
        finally:
            elapsed_time = time.time() - start_time
            print(f"Cache GET operation completed in {elapsed_time:.3f} seconds")

    def set(self, cache_type: str, key: str, value: Any, preserve_existing: bool = True) -> None:
        """Set a value in a specific cache."""
        start_time = time.time()
        print(f"\n=== Cache SET Operation ===")
        print(f"Cache Type: {cache_type}")
        print(f"Key: {key}")
        print(f"Value Type: {type(value)}")
        print(f"Preserve Existing: {preserve_existing}")
        
        try:
            if cache_type not in self.caches:
                print(f"Invalid cache type '{cache_type}'. Available types: {list(self.caches.keys())}")
                return
                    
            # If preserving existing and we have existing data
            if preserve_existing and key in self.caches[cache_type]:
                print("Found existing cache entry - attempting merge")
                
                existing_data = self.caches[cache_type][key].get('value', {})
                print(f"Existing data type: {type(existing_data)}")
                
                if isinstance(existing_data, dict) and isinstance(value, dict):
                    print("Both existing and new values are dictionaries - performing merge")
                    print(f"Existing keys: {list(existing_data.keys())}")
                    print(f"New keys: {list(value.keys())}")
                    
                    # Merge new data with existing data
                    merged_value = existing_data.copy()
                    merged_value.update(value)
                    value = merged_value
                    
                    print("Merge completed")
                    print(f"Final merged keys: {list(value.keys())}")
                else:
                    print(f"Skipping merge - incompatible types: existing={type(existing_data)}, new={type(value)}")

            # Create cache entry
            current_time = time.time()
            cache_entry = {
                'value': value,
                'timestamp': current_time,
                'last_accessed': current_time
            }
            
            print("\nCreating new cache entry:")
            print(f"Timestamp: {current_time}")
            print(f"Entry size: {sys.getsizeof(cache_entry)} bytes")

            self.caches[cache_type][key] = cache_entry
            
            # Save to disk
            print("\nSaving cache to disk...")
            save_start = time.time()
            self._save_cache(cache_type)
            save_time = time.time() - save_start
            print(f"Cache saved to disk in {save_time:.3f} seconds")
                
        except Exception as e:
            print(f"Error setting {cache_type} cache: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            elapsed_time = time.time() - start_time
            print(f"Cache SET operation completed in {elapsed_time:.3f} seconds")


    def get_cache_stats(self) -> Dict[str, Dict]:
        """Get statistics about cache usage and performance."""
        stats = {}
        for cache_type, cache in self.caches.items():
            stats[cache_type] = {
                'total_entries': len(cache),
                'size_bytes': sum(len(str(v).encode('utf-8')) for v in cache.values()),
                'oldest_entry': min((v.get('timestamp', 0) for v in cache.values()), default=0),
                'newest_entry': max((v.get('timestamp', 0) for v in cache.values()), default=0),
            }
            
            # Calculate age distribution
            current_time = time.time()
            ages = [(current_time - v.get('timestamp', 0)) / 3600 for v in cache.values()]  # Hours
            if ages:
                stats[cache_type]['avg_age_hours'] = sum(ages) / len(ages)
                stats[cache_type]['expired_entries'] = sum(1 for age in ages if age * 3600 > self.max_cache_age)
        
        return stats

    def clear(self, cache_type: Optional[str] = None) -> None:
        """Clear specific or all caches."""
        try:
            if cache_type:
                if cache_type in self.caches:
                    self.caches[cache_type] = {}
                    cache_path = self._get_cache_path(cache_type)
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
            else:
                # Clear all caches
                for cache_type in self.CACHE_TYPES:
                    self.caches[cache_type] = {}
                    cache_path = self._get_cache_path(cache_type)
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                        
            print(f"Cleared {'all caches' if cache_type is None else f'{cache_type} cache'}")
            
        except Exception as e:
            print(f"Error clearing cache: {e}")