import json
import os
import time
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from ollama import Client


class LLMUtilities:
    """
    LLM-powered utilities to replace complex regex-based text processing.
    Uses Gemma-3-270m via Ollama for intelligent text processing.
    """
    
    def __init__(self, parent=None, update_status_callback=None):
        self.parent = parent
        self.client = Client()
        self.model_name = "gemma3:270m"
        
        # Store callback for status updates
        self.status_update_callback = update_status_callback
        
        # Cache for LLM responses
        self.cache_file = "llm_cache.json"
        self.cache = self.load_cache()
        
        # Initialize model
        self._ensure_model_available()
        
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

    def _ensure_model_available(self):
        """Ensure Gemma 3 270M model is available in Ollama."""
        try:
            # Check if model exists
            models = self.client.list()
            model_names = [model['name'] for model in models['models']]
            
            if self.model_name not in model_names:
                self.emit_status("Downloading Gemma 3 270M model... This may take a few minutes.")
                self.client.pull(self.model_name)
                self.emit_status("Model downloaded successfully.")
            else:
                self.emit_status("Gemma 3 270M model ready.")
                
        except Exception as e:
            error_msg = f"Error setting up LLM model: {e}"
            self.emit_status(error_msg)
            self.show_error_dialog(error_msg)

    def _get_cache_key(self, prompt: str, function_name: str) -> str:
        """Generate cache key for prompt."""
        content = f"{function_name}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()

    def load_cache(self) -> Dict:
        """Load cached LLM responses."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading cache: {e}")
        return {}

    def save_cache(self):
        """Save cached LLM responses."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def _query_llm(self, prompt: str, function_name: str, max_retries: int = 3) -> str:
        """Query LLM with caching and error handling."""
        cache_key = self._get_cache_key(prompt, function_name)
        
        # Check cache first
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat(
                    model=self.model_name,
                    messages=[{
                        'role': 'user',
                        'content': prompt
                    }],
                    options={
                        'temperature': 0.1,  # Low temperature for consistent results
                        'top_p': 0.9,
                        'num_predict': 256
                    }
                )
                
                result = response['message']['content'].strip()
                
                # Cache the result
                self.cache[cache_key] = result
                self.save_cache()
                
                return result
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"LLM query failed (attempt {attempt + 1}), retrying: {e}")
                    time.sleep(1)
                else:
                    print(f"LLM query failed after {max_retries} attempts: {e}")
                    return ""
        
        return ""

    def clean_artist_name(self, artist_name: str) -> str:
        """
        Clean artist name using LLM intelligence instead of complex regex.
        Handles featuring artists, group names, and various formatting issues.
        """
        if not artist_name:
            return ""
            
        prompt = f"""Clean this artist name by removing featuring artists and extra information, but preserve actual group names:

Artist: "{artist_name}"

Rules:
1. Remove featuring artists (feat., ft., featuring, x, etc.)
2. Preserve legitimate group names like "Hall & Oates", "Earth Wind & Fire", "Simon & Garfunkel"
3. Remove parenthetical information unless it's part of the group name
4. Keep the main/primary artist only
5. Maintain proper capitalization

Return ONLY the cleaned artist name, nothing else."""

        result = self._query_llm(prompt, "clean_artist_name")
        return result if result else artist_name

    def clean_track_title(self, title: str) -> str:
        """
        Clean track title using LLM to remove video-related suffixes and extra information.
        """
        if not title:
            return ""
            
        prompt = f"""Clean this song title by removing video-related content and extra information:

Title: "{title}"

Rules:
1. Remove video-related text: "Official Music Video", "Music Video", "Audio", "HD", "4K", etc.
2. Remove version indicators: "Clean", "Explicit", "Radio Edit", etc. UNLESS they're part of the actual song title
3. Remove website references and promotional text
4. Keep featuring artists if they're part of the official title
5. Preserve actual song title content like numbers if they're meaningful (e.g., "3 AM", "21 Questions")
6. Maintain proper capitalization

Return ONLY the cleaned title, nothing else."""

        result = self._query_llm(prompt, "clean_track_title")
        return result if result else title


    def match_artists(self, artist1: str, artist2: str, threshold: int = 70) -> bool:
        """
        Compare artist names using LLM understanding of variations and aliases.
        """
        if not artist1 or not artist2:
            return False
            
        prompt = f"""Compare these two artist names and determine if they refer to the same artist:

Artist 1: "{artist1}"
Artist 2: "{artist2}"

Consider:
1. Common name variations (Bobby Valentino vs Bobby V)
2. Featuring artist differences (Artist vs Artist feat. Someone)
3. Spelling variations and typos
4. Different formatting of the same name
5. Group name variations

Respond with only "YES" if they're the same artist, "NO" if they're different artists."""

        result = self._query_llm(prompt, "match_artists")
        return result.upper().startswith("YES")

    def match_titles(self, title1: str, title2: str, threshold: int = 75) -> bool:
        """
        Compare song titles using LLM understanding of variations.
        """
        if not title1 or not title2:
            return False
            
        prompt = f"""Compare these two song titles and determine if they're the same song:

Title 1: "{title1}"
Title 2: "{title2}"

Consider:
1. Different version indicators (Clean vs Explicit vs Radio Edit)
2. Time format variations (3:AM vs 3 AM vs 3AM)
3. Extra words that don't change the core title
4. Different formatting of the same title
5. Remix/version variations of the same base song

Respond with only "YES" if they're the same song, "NO" if they're different songs."""

        result = self._query_llm(prompt, "match_titles")
        return result.upper().startswith("YES")

    def extract_main_artist(self, artist_string: str) -> str:
        """
        Extract the main/primary artist from a string that may contain featuring artists.
        """
        if not artist_string:
            return ""
            
        prompt = f"""Extract the main/primary artist from this artist string:

Artist String: "{artist_string}"

Rules:
1. Return only the primary/main artist name
2. Remove all featuring artists (feat., ft., featuring, x, etc.)
3. Preserve group names if the whole string is a group (like "Hall & Oates")
4. If it's clearly a collaboration with no main artist, return the first mentioned artist

Return ONLY the main artist name, nothing else."""

        result = self._query_llm(prompt, "extract_main_artist")
        return result if result else artist_string

    def format_artist_with_features(self, artists: List[str]) -> str:
        """
        Format multiple artists with proper featuring syntax using LLM.
        """
        if not artists:
            return ""
        if len(artists) == 1:
            return artists[0]
            
        artists_str = ", ".join(artists)
        
        prompt = f"""Format these artists with proper featuring syntax:

Artists: {artists_str}

Rules:
1. First artist is the main artist
2. Others are featuring artists
3. Use "feat." for featuring
4. Use "&" to connect multiple featuring artists
5. Format as "Main Artist feat. Feature1 & Feature2" etc.

Return ONLY the formatted artist string, nothing else."""

        result = self._query_llm(prompt, "format_artist_with_features")
        return result if result else artists[0]

    def handle_featured_artists(self, artist_string: str) -> str:
        """
        Enhanced featuring artist handling with LLM intelligence.
        """
        try:
            # Use LLM to detect if there are featuring artists
            prompt = f"""Analyze this artist string for featuring artists:

Artist String: "{artist_string}"

Determine:
1. Is there a main artist and featuring artists?
2. If yes, list them separately

Format your response as:
Main: [main artist name]
Features: [comma-separated featuring artists, or "None" if no features]

If there are no featuring artists, just respond with:
Main: [artist name]
Features: None"""

            result = self._query_llm(prompt, "analyze_features")
            
            if "Features: None" in result or not result:
                return artist_string
                
            # Parse the LLM response
            lines = result.split('\n')
            main_artist = ""
            features = []
            
            for line in lines:
                if line.startswith("Main:"):
                    main_artist = line.replace("Main:", "").strip()
                elif line.startswith("Features:"):
                    features_str = line.replace("Features:", "").strip()
                    if features_str and features_str != "None":
                        features = [f.strip() for f in features_str.split(',')]
            
            if features:
                # For now, always include features in formatted string
                # In a GUI context, this would be handled by a callback to ask the user
                return self.format_artist_with_features([main_artist] + features)
                    
            return artist_string
            
        except Exception as e:
            print(f"Error handling featured artists: {e}")
            return artist_string

    # Metadata and file operations (keep from original)
    def load_audio_file(self, file_path, retries=3, delay=1):
        """Keep original implementation for file operations."""
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.id3 import ID3
        
        for attempt in range(retries):
            try:
                if not file_path or not isinstance(file_path, str):
                    error_msg = f"Invalid file path: {file_path}"
                    self.emit_status(error_msg)
                    return None
                
                if not os.path.exists(file_path):
                    error_msg = f"File does not exist: {file_path}"
                    self.emit_status(error_msg)
                    return None
                    
                if not os.access(file_path, os.R_OK):
                    error_msg = f"File is not readable: {file_path}"
                    self.emit_status(error_msg)
                    return None
                
                file_extension = os.path.splitext(file_path)[1].lower()
                
                if file_extension == ".mp3":
                    audio = MP3(file_path, ID3=ID3)
                    return audio
                elif file_extension == ".m4a":
                    audio = MP4(file_path)
                    return audio
                else:
                    error_msg = f"Unsupported file format: {file_extension}"
                    self.emit_status(error_msg)
                    return None
                    
            except Exception as e:
                error_msg = f"Error loading file (attempt {attempt + 1}/{retries}): {str(e)}"
                print(error_msg)
                
                if attempt < retries - 1:
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    self.show_error_dialog(error_msg)
                    return None
                    
        return None

    def get_metadata(self, audio):
        """Keep original metadata extraction logic."""
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        
        metadata = {}
        try:
            if isinstance(audio, MP3):
                if 'TIT2' in audio:
                    metadata['title'] = audio['TIT2'].text[0]
                if 'TPE1' in audio:
                    metadata['artist'] = audio['TPE1'].text[0]
                if 'TALB' in audio:
                    metadata['album'] = audio['TALB'].text[0]
                if 'TCON' in audio:
                    metadata['genre'] = audio['TCON'].text[0]
                if 'TDRC' in audio:
                    metadata['year'] = str(audio['TDRC'].text[0])
                try:
                    metadata['composer'] = audio.get('TCOM', [''])[0]
                except Exception:
                    pass
                for key in audio.keys():
                    if key.startswith("COMM"):
                        metadata['subgenres'] = audio[key].text[0]
                        break

            elif isinstance(audio, MP4):
                metadata = {
                    'title': audio.get('\xa9nam', [""])[0],
                    'artist': audio.get('\xa9ART', [""])[0],
                    'album': audio.get('\xa9alb', [""])[0],
                    'genre': audio.get('\xa9gen', [""])[0],
                    'year': str(audio.get('\xa9day', [""])[0]) if '\xa9day' in audio else "",
                    'composer': audio.get('\xa9wrt', [""])[0],
                    'subgenres': audio.get('----:com.apple.iTunes:subgenres', [""])[0] if '----:com.apple.iTunes:subgenres' in audio else audio.get('\xa9cmt', [""])[0],
                }
                for field in ['title', 'artist', 'album', 'genre', 'year', 'composer', 'subgenres']:
                    if field not in metadata:
                        metadata[field] = ""
            return metadata

        except Exception as e:
            error_message = f"Error getting metadata: {e}"
            print(error_message)
            self.emit_status(error_message)
            return {}

    def set_metadata(self, audio, metadata):
        """Keep original metadata setting logic."""
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.id3 import TPE1, TCON, COMM, TALB, TYER, TCOM
        
        try:
            print(f"Setting metadata: {metadata}")
            if isinstance(audio, MP3):
                for key, value in metadata.items():
                    if not value:
                        continue

                    try:
                        if key == 'composer':
                            try:
                                audio.tags.delall('TCOM')
                            except Exception:
                                pass
                            audio.tags.add(TCOM(encoding=3, text=value))
                        elif key == 'artist':
                            audio['TPE1'] = TPE1(encoding=3, text=value)
                        elif key == 'album':
                            audio['TALB'] = TALB(encoding=3, text=value)
                        elif key == 'genre':
                            audio['TCON'] = TCON(encoding=3, text=value)
                        elif key == 'year':
                            audio['TYER'] = TYER(encoding=3, text=str(value))
                        elif key == 'subgenres':
                            audio.tags.delall('COMM')
                            audio['COMM'] = COMM(encoding=3, lang='eng', desc='subgenres', text=value)
                    except Exception as field_error:
                        print(f"Warning: Error setting MP3 field '{key}': {field_error}")
                        continue

            elif isinstance(audio, MP4):
                for key, value in metadata.items():
                    if not value:
                        continue

                    try:
                        if key == 'composer':
                            audio['\xa9wrt'] = [value]
                        elif key == 'title':
                            audio['\xa9nam'] = [value]
                        elif key == 'artist':
                            audio['\xa9ART'] = [value]
                        elif key == 'album':
                            audio['\xa9alb'] = [value]
                        elif key == 'genre':
                            audio['\xa9gen'] = [value]
                        elif key == 'year':
                            audio['\xa9day'] = [str(value)]
                        elif key == 'subgenres':
                            audio['\xa9cmt'] = [value]
                    except Exception as field_error:
                        print(f"Warning: Error setting MP4 field '{key}': {field_error}")
                        continue

            audio.save()
            return True

        except Exception as e:
            error_message = f"Error setting metadata: {e}"
            print(error_message)
            self.emit_status(error_message)
            return False

    def get_artist_and_title_from_audio(self, audio, filename):
        """Get artist and title using LLM-enhanced parsing."""
        try:
            metadata = self.get_metadata(audio)
            artist_name = metadata.get('artist', '')
            original_title = metadata.get('title', '')

            # Use LLM to clean the extracted metadata
            if artist_name:
                artist_name = self.clean_artist_name(artist_name)
            if original_title:
                original_title = self.clean_track_title(original_title)

            # Only parse filename if we don't have BOTH artist and title from metadata
            if not artist_name or not original_title:
                print("Missing metadata, attempting to parse from filename...")
                parsed_artist, parsed_title = self.parse_filename_for_metadata(filename)
                artist_name = artist_name or parsed_artist
                original_title = original_title or parsed_title

            # Set defaults if we still don't have values
            if not artist_name:
                artist_name = "Unknown Artist"
            if not original_title:
                original_title = "Unknown Title"

            return artist_name, original_title

        except Exception as e:
            error_message = f"Error getting artist and title from audio object: {e}"
            print(error_message)
            return '', ''

    def parse_filename_for_metadata(self, filename):
        """Parse filename with LLM assistance."""
        try:
            base = os.path.basename(filename)
            name_without_extension = os.path.splitext(base)[0]
            
            # Use LLM to intelligently parse the filename
            prompt = f"""Parse this filename to extract artist and title:

Filename: "{name_without_extension}"

Common patterns:
- "Artist - Title"
- "Artist_Title"
- "Track Number - Artist - Title"
- "Artist feat. Someone - Title"

Return the result in this exact format:
Artist: [artist name]
Title: [title name]

If you can't determine both, return what you can identify."""

            result = self._query_llm(prompt, "parse_filename")
            
            artist = ""
            title = ""
            
            for line in result.split('\n'):
                if line.startswith("Artist:"):
                    artist = line.replace("Artist:", "").strip()
                elif line.startswith("Title:"):
                    title = line.replace("Title:", "").strip()
            
            return artist, title
            
        except Exception as e:
            print(f"Error parsing filename for metadata: {e}")
            return "", ""

    # Keep utility methods that don't need LLM
    def sanitize_filename(self, name):
        """Keep original filename sanitization."""
        import string
        valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
        sanitized_name = ''.join(c for c in name if c in valid_chars)
        return sanitized_name.strip()

    def clear_cache(self):
        """Clear LLM cache."""
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        print("LLM cache cleared.")