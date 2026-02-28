import os
import time
from typing import Dict, Optional, Tuple

class AudioUtilities:
    """Lightweight audio file utilities for MP3/M4A metadata handling."""
    
    def __init__(self, status_update_callback=None):
        self.status_update_callback = status_update_callback
    
    def emit_status(self, message):
        """Emit status update through callback."""
        if self.status_update_callback:
            self.status_update_callback(message)
        else:
            print(message)
    
    def load_audio_file(self, file_path, retries=3, delay=1):
        """Load MP3 or M4A audio file."""
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.id3 import ID3
        
        for attempt in range(retries):
            try:
                if not file_path or not isinstance(file_path, str):
                    self.emit_status(f"Invalid file path: {file_path}")
                    return None
                
                if not os.path.exists(file_path):
                    self.emit_status(f"File does not exist: {file_path}")
                    return None
                    
                if not os.access(file_path, os.R_OK):
                    self.emit_status(f"File is not readable: {file_path}")
                    return None
                
                file_extension = os.path.splitext(file_path)[1].lower()
                
                if file_extension == ".mp3":
                    audio = MP3(file_path, ID3=ID3)
                    return audio
                elif file_extension == ".m4a":
                    audio = MP4(file_path)
                    return audio
                else:
                    self.emit_status(f"Unsupported file format: {file_extension}")
                    return None
                    
            except Exception as e:
                error_msg = f"Error loading file (attempt {attempt + 1}/{retries}): {str(e)}"
                print(error_msg)
                
                if attempt < retries - 1:
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    self.emit_status(error_msg)
                    return None
                    
        return None
    
    def get_metadata(self, audio) -> Dict:
        """Extract metadata from audio file."""
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4

        metadata = {}
        try:
            if isinstance(audio, MP3):
                if "TIT2" in audio:
                    metadata["title"] = audio["TIT2"].text[0]
                if "TPE1" in audio:
                    metadata["artist"] = audio["TPE1"].text[0]
                if "TALB" in audio:
                    metadata["album"] = audio["TALB"].text[0]
                if "TCON" in audio:
                    metadata["genre"] = audio["TCON"].text[0]
                if "TDRC" in audio:
                    metadata["year"] = str(audio["TDRC"].text[0])
                try:
                    metadata["composer"] = audio.get("TCOM", [""])[0]
                except Exception:
                    pass
                # Look for COMM frames - prefer empty description (standard) over others
                comm_frame = None
                for key in audio.keys():
                    if key.startswith("COMM"):
                        frame = audio[key]
                        # Prefer COMM frame with empty description for Serato compatibility
                        if frame.desc == "":
                            comm_frame = frame
                            break
                        elif comm_frame is None:
                            # Fallback to any COMM frame if no standard one found
                            comm_frame = frame
                if comm_frame:
                    metadata["comments"] = comm_frame.text[0]

                # Read rating from POPM frame (Serato DJ Pro 4.0 uses this for ratings)
                metadata["rating"] = self._read_popm_rating(audio)

            elif isinstance(audio, MP4):
                metadata = {
                    "title": audio.get("©nam", [""])[0],
                    "artist": audio.get("©ART", [""])[0],
                    "album": audio.get("©alb", [""])[0],
                    "genre": audio.get("©gen", [""])[0],
                    "year": str(audio.get("©day", [""])[0]) if "©day" in audio else "",
                    "composer": audio.get("©wrt", [""])[0],
                    "comments": audio.get("----:com.apple.iTunes:subgenres", [""])[0] if "----:com.apple.iTunes:subgenres" in audio else audio.get("©cmt", [""])[0],
                    "rating": audio.get("----:com.apple.iTunes:RATING", [""])[0],
                }
                for field in ["title", "artist", "album", "genre", "year", "composer", "comments", "rating"]:
                    if field not in metadata:
                        metadata[field] = ""
            return metadata

        except Exception as e:
            error_message = f"Error getting metadata: {e}"
            print(error_message)
            self.emit_status(error_message)
            return {}
    
    def set_metadata(self, audio, metadata: Dict, file_path=None) -> bool:
        """Set metadata on audio file."""
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.id3 import TPE1, TCON, COMM, TALB, TYER, TDRC, TCOM

        try:
            print(f"set_metadata called with metadata keys: {list(metadata.keys())}")
            print(f"Full metadata: {metadata}")
            print(f"File path: {file_path}")
            if 'rating' in metadata:
                print(f"!!! RATING FOUND IN METADATA: {metadata['rating']} !!!")

            if isinstance(audio, MP3):
                if audio.tags is None or hasattr(audio.tags, "__class__") and "ID3NoHeaderError" in str(type(audio.tags)):
                    print("Adding ID3 tags to MP3 file")
                    audio.add_tags()
                for key, value in metadata.items():
                    # Skip empty values, but allow '0' for ratings and numeric strings
                    if value == '' or value is None:
                        continue

                    try:
                        if key == "composer":
                            try:
                                audio.tags.delall("TCOM")
                            except Exception:
                                pass
                            audio.tags.add(TCOM(encoding=3, text=value))
                        elif key == "artist":
                            audio["TPE1"] = TPE1(encoding=3, text=value)
                        elif key == "album":
                            audio["TALB"] = TALB(encoding=3, text=value)
                        elif key == "genre":
                            # Clean up old genre tags and write fresh one for Serato DJ compatibility
                            try:
                                audio.tags.delall("TCON")
                            except Exception:
                                pass
                            audio["TCON"] = TCON(encoding=3, text=value)
                        elif key == "year":
                            # Clean up old year tags first
                            try:
                                audio.tags.delall("TYER")
                                audio.tags.delall("TDRC")
                            except Exception:
                                pass
                            # Write both TYER (for backward compatibility) and TDRC (ID3v2.4 standard)
                            year_str = str(value).strip()
                            audio["TYER"] = TYER(encoding=3, text=year_str)
                            # TDRC can be full date or just year, use year format for Serato DJ v4.0
                            audio["TDRC"] = TDRC(encoding=3, text=year_str)
                        elif key == "comments":
                            # Clean up all existing COMM frames
                            try:
                                audio.tags.delall("COMM")
                            except Exception:
                                pass
                            # Add new COMM frame using tags.add() for proper handling
                            # Use empty description for better Serato DJ v4.0 compatibility
                            audio.tags.add(COMM(encoding=3, lang="eng", desc="", text=value))
                        elif key == "rating":
                            # Write POPM rating for Serato DJ Pro 4.0 compatibility
                            print(f"Writing MP3 rating: {value}")
                            self._write_popm_rating(audio, value)
                    except Exception as field_error:
                        print(f"Warning: Error setting MP3 field {key}: {field_error}")
                        continue

            elif isinstance(audio, MP4):
                for key, value in metadata.items():
                    # Skip empty values, but allow '0' for ratings and numeric strings
                    if value == '' or value is None:
                        continue

                    try:
                        if key == "composer":
                            audio["©wrt"] = [value]
                        elif key == "title":
                            audio["©nam"] = [value]
                        elif key == "artist":
                            audio["©ART"] = [value]
                        elif key == "album":
                            audio["©alb"] = [value]
                        elif key == "genre":
                            # Clean up old genre atoms for Serato DJ compatibility
                            if "©gen" in audio:
                                del audio["©gen"]
                            audio["©gen"] = [value]
                        elif key == "year":
                            # Clean up old year atoms
                            if "©day" in audio:
                                del audio["©day"]
                            audio["©day"] = [str(value)]
                        elif key == "comments":
                            # Clean up old comment atoms
                            if "©cmt" in audio:
                                del audio["©cmt"]
                            audio["©cmt"] = [value]
                        elif key == "rating":
                            # Write rating to M4A iTunes atom
                            print(f"Writing M4A rating: {value}")
                            if "----:com.apple.iTunes:RATING" in audio:
                                del audio["----:com.apple.iTunes:RATING"]
                            audio["----:com.apple.iTunes:RATING"] = [value]
                    except Exception as field_error:
                        print(f"Warning: Error setting MP4 field {key}: {field_error}")
                        continue

            if file_path:
                audio.save(file_path)
                # Touch the file to update modification time
                # This helps Serato DJ recognize the file has been modified
                self._touch_file(file_path)
            else:
                audio.save()
            return True

        except Exception as e:
            error_message = f"Error setting metadata: {e}"
            print(error_message)
            self.emit_status(error_message)
            return False
    
    def get_artist_and_title(self, audio, filename) -> Tuple[str, str]:
        """Get artist and title from audio metadata or filename."""
        try:
            metadata = self.get_metadata(audio)
            artist_name = metadata.get("artist", "").strip()
            title = metadata.get("title", "").strip()

            # Parse filename if missing metadata
            if not artist_name or not title:
                print("Missing metadata, attempting to parse from filename...")
                parsed_artist, parsed_title = self._parse_filename(filename)
                artist_name = artist_name or parsed_artist
                title = title or parsed_title

            # Set defaults if still missing
            if not artist_name:
                artist_name = "Unknown Artist"
            if not title:
                title = "Unknown Title"

            return artist_name, title

        except Exception as e:
            error_message = f"Error getting artist and title: {e}"
            print(error_message)
            return "Unknown Artist", "Unknown Title"
    
    def _parse_filename(self, filename: str) -> Tuple[str, str]:
        """Parse filename to extract artist and title."""
        try:
            base = os.path.basename(filename)
            name_without_extension = os.path.splitext(base)[0]
            
            # Try common patterns: "Artist - Title"
            if " - " in name_without_extension:
                parts = name_without_extension.split(" - ", 1)
                artist = parts[0].strip()
                title = parts[1].strip()
                return artist, title
            
            # Try underscore separator
            if "_" in name_without_extension:
                parts = name_without_extension.split("_", 1)
                artist = parts[0].strip()
                title = parts[1].strip()
                return artist, title
            
            # Default: use filename as title
            return "", name_without_extension
            
        except Exception as e:
            print(f"Error parsing filename: {e}")
            return "", ""
    
    def sanitize_filename(self, name: str) -> str:
        """Sanitize filename for safety."""
        import string
        valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
        sanitized_name = "".join(c for c in name if c in valid_chars)
        return sanitized_name.strip()
    
    def format_genre(self, genre: str) -> str:
        """Format genre with proper capitalization."""
        if not genre:
            return ""

        special_cases = {
            "r&b": "R&B",
            "rnb": "R&B",
            "rap": "Hip-Hop",
            "hip hop": "Hip-Hop",
            "hip-hop": "Hip-Hop"
        }

        genre_lower = genre.lower().strip()
        if genre_lower in special_cases:
            return special_cases[genre_lower]

        return " ".join(word.capitalize() for word in genre_lower.split())

    def _read_popm_rating(self, audio) -> str:
        """Read POPM (Popularimeter) rating from MP3 ID3 tags.

        Returns rating as string (0-255 scale for Serato DJ Pro 4.0).
        Serato uses POPM frame with email='Serato' for ratings.
        """
        try:
            for key in audio.keys():
                if key.startswith("POPM"):
                    frame = audio[key]
                    # Check if this is Serato's POPM frame
                    if hasattr(frame, 'email') and frame.email == 'Serato':
                        # Rating is 0-255, convert to string
                        return str(frame.rating)
            # If no Serato POPM found, try generic POPM
            if "POPM:Serato" in audio:
                frame = audio["POPM:Serato"]
                return str(frame.rating)
            return ""
        except Exception as e:
            print(f"Error reading POPM rating: {e}")
            return ""

    def _write_popm_rating(self, audio, rating_value) -> bool:
        """Write POPM (Popularimeter) rating to MP3 ID3 tags.

        Args:
            audio: MP3 audio object
            rating_value: Rating as string or int (0-255 for Serato DJ Pro 4.0)

        Returns:
            True if successful, False otherwise
        """
        try:
            from mutagen.id3 import POPM

            # Convert rating to int if it's a string
            try:
                rating = int(rating_value) if isinstance(rating_value, str) else int(float(rating_value))
                # Clamp to valid range (0-255)
                rating = max(0, min(255, rating))
                print(f"POPM: Converting rating value {rating_value} to {rating}")
            except (ValueError, TypeError):
                print(f"Invalid rating value: {rating_value}, skipping")
                return False

            # Remove any existing POPM frames with Serato email
            frames_to_remove = []
            for key in list(audio.tags.keys()):
                if key.startswith("POPM"):
                    frame = audio.tags[key]
                    if hasattr(frame, 'email') and frame.email == 'Serato':
                        frames_to_remove.append(key)
                        print(f"Removing existing POPM frame: {key}")

            for key in frames_to_remove:
                del audio.tags[key]

            # Create new POPM frame with Serato email identifier
            # POPM frame format: email, rating (0-255), count (play counter)
            popm_frame = POPM(email='Serato', rating=rating, count=0)
            print(f"Created POPM frame: email='{popm_frame.email}', rating={popm_frame.rating}, count={popm_frame.count}")

            # Add using the proper key format for Serato
            audio.tags.add(popm_frame)
            print(f"Added POPM frame to audio.tags")

            # Verify it was added
            found = False
            for key in audio.tags.keys():
                if key.startswith("POPM"):
                    frame = audio.tags[key]
                    if hasattr(frame, 'email') and frame.email == 'Serato':
                        print(f"Verified POPM frame added: {key} with rating {frame.rating}")
                        found = True
                        break

            if not found:
                print("WARNING: POPM frame was added but cannot be verified!")

            return True

        except Exception as e:
            print(f"Error writing POPM rating: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _touch_file(self, file_path: str) -> None:
        """Update file's modification time to current time.

        This helps DJ software like Serato recognize that the file has been modified
        and needs to re-read metadata from the tags.

        Args:
            file_path: Path to the audio file
        """
        try:
            import os
            import time
            # Update file modification time to now
            os.utime(file_path, None)
            print(f"Updated file mtime: {file_path}")
        except Exception as e:
            print(f"Warning: Could not update file modification time: {e}")
