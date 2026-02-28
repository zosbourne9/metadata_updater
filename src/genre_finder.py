import time
import json
import logging
from openai import OpenAI
from constants import OPENROUTER_API_KEY
from typing import Dict, List
from enhanced_genre_detector import EnhancedGenreDetector

# Import RAG knowledge base
try:
    from genre_knowledge_base import get_knowledge_base
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    get_knowledge_base = None

logger = logging.getLogger(__name__)

class GenreFinder:
    def __init__(self, spotify_integration, musicbrainz_integration, utility_tools, artist_normalizer=None, cache_manager=None):
        try:
            # Import the resource path helper
            from resource_path import get_resource_path
            from genre_patterns import ADDITIONAL_PATTERNS  # Import the patterns directly
            
            self.spotify = spotify_integration
            self.musicbrainz = musicbrainz_integration
            self.utility_tools = utility_tools
            self.max_retries = 3
            self.retry_delay = 2
            
            # Configure OpenRouter with Gemini 2.5 Flash
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
            )
            
            self.artist_normalizer = artist_normalizer or spotify_integration.artist_normalizer
            self.cache_manager = cache_manager  # Store cache manager reference
            
            # Initialize the enhanced genre detector with OpenRouter
            self.enhanced_detector = EnhancedGenreDetector(api_key=OPENROUTER_API_KEY)
            
            # Load JSON files using resource path
            characteristics_path = get_resource_path('config/genre_characteristics.json')
            print(f"Loading genre characteristics from: {characteristics_path}")
            
            # Update genre patterns directly
            if self.enhanced_detector and hasattr(self.enhanced_detector, 'genre_patterns'):
                for genre, patterns in ADDITIONAL_PATTERNS.items():
                    if genre in self.enhanced_detector.genre_patterns:
                        self.enhanced_detector.genre_patterns[genre].update(patterns)
                    else:
                        self.enhanced_detector.genre_patterns[genre] = patterns
                        
            # Clear the cache if we have a cache manager
            if self.cache_manager:
                self.cache_manager.clear('genre')

            # Initialize RAG knowledge base for lazy loading (will be loaded only when needed)
            self.knowledge_base = None
            self._knowledge_base_loaded = False

        except Exception as e:
            print(f"Error initializing GenreFinder: {e}")
            self.enhanced_detector = None
            self.cache_manager = None
            self.knowledge_base = None

    def _ensure_knowledge_base_loaded(self):
        """Lazy-load knowledge base only when actually needed."""
        if self._knowledge_base_loaded:
            return self.knowledge_base

        self._knowledge_base_loaded = True
        if RAG_AVAILABLE and get_knowledge_base:
            try:
                self.knowledge_base = get_knowledge_base()
                if self.knowledge_base and self.knowledge_base.is_initialized():
                    print("✓ RAG genre knowledge base lazily loaded in GenreFinder")
                else:
                    print("⚠ RAG knowledge base not available in GenreFinder, will use standard detection")
                    self.knowledge_base = None
            except Exception as e:
                logger.warning(f"Failed to initialize RAG in GenreFinder: {e}")
                self.knowledge_base = None
        else:
            if not RAG_AVAILABLE:
                logger.debug("LangChain/RAG not available in GenreFinder")

        return self.knowledge_base

    def get_artist_genre_from_ai(self, artist_name, song_title):
        """
        Enhanced AI genre detection with strategic prompting and RAG knowledge base.

        Uses Retrieval-Augmented Generation (RAG) to provide the AI with curated genre
        knowledge from config/genre_characteristics.json for more accurate classifications.
        """
        try:
            print(f"Getting genre from AI for: {artist_name} - {song_title}")
            print(f"API client configured: {self.client is not None}")

            if not self.client:
                print("No AI client configured, returning No Genre")
                return {
                    "genre": "No Genre",
                    "subs": [],
                    "conf": 0
                }

            # Retrieve relevant genre context from RAG if available (lazy loaded)
            genre_context = ""
            kb = self._ensure_knowledge_base_loaded()
            if kb and kb.is_initialized():
                try:
                    genre_context = kb.get_relevant_genres(
                        artist_name=artist_name,
                        track_title=song_title,
                        k=3  # Get top 3 most relevant genres
                    )
                    if genre_context:
                        logger.debug(f"Retrieved RAG context for {artist_name} - {song_title}")
                        print(f"Using RAG genre knowledge for better context")
                except Exception as rag_error:
                    logger.debug(f"RAG retrieval failed in GenreFinder: {rag_error}")
                    genre_context = ""

            # Create a more strategic prompt with optional RAG context
            prompt = f"""You are a professional music curator and genre expert. Analyze this artist and song to determine the most accurate primary genre and 2-3 relevant subgenres.

ARTIST: {artist_name}
SONG: {song_title}
"""

            # Include RAG context if available
            if genre_context:
                prompt += f"\n{genre_context}\n"

            prompt += """
ANALYSIS INSTRUCTIONS:
1. Focus on the artist's established musical style and era
2. Consider the song title for contextual clues about style/tempo
3. Think about what record stores and streaming services would classify this as
4. Use standard music industry genre categories
5. For Caribbean artists: Pay special attention to reggae variants (dancehall, dub, roots reggae, ragga) and soca

PREFERRED PRIMARY GENRES (choose the most appropriate):
- Hip-Hop (for rap, trap, drill, etc.)
- R&B (for soul, neo-soul, urban contemporary)
- Pop (for mainstream pop, dance-pop, etc.)
- Electronic (for EDM, house, techno, etc.)
- Rock (for all rock subgenres)
- Funk (for funk, P-funk, etc.)
- Reggae (for reggae, dancehall, dub, roots reggae, ragga)
- Soul (for classic soul, northern soul, etc.)
- Jazz (for all jazz styles)
- Blues (for blues and blues derivatives)
- Alternative (for indie, alternative rock, etc.)
- Soca (for soca, calypso-based Caribbean music)
- Afrobeats (for Afrobeats, Afro-pop, Nigerian/Ghanaian pop)
- World Music (for international/ethnic styles)

SUBGENRES should be specific and accurate (e.g., "alternative r&b", "neo soul", "trap", "deep house", "conscious hip hop", "dancehall", "roots reggae", etc.)

For Reggae artists: Consider if the subgenres should include "dancehall", "roots reggae", "dub", or "ragga" based on the artist's style.

Respond with ONLY valid JSON in this exact format:
{{"genre": "Primary Genre", "subs": ["specific subgenre1", "specific subgenre2"], "conf": 85}}

The confidence should be 70-95 based on how certain you are about the classification."""

            print("Making AI API call...")
            response = self.client.chat.completions.create(
                model="google/gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": "You are a professional music curator and genre expert. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            print("AI API call completed successfully")
            
            # Extract JSON from response
            response_text = response.choices[0].message.content.strip()
            print(f"Raw AI response: {response_text}")
            
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                print(f"Extracted JSON: {json_str}")
                result = json.loads(json_str)
            else:
                print("No JSON found in response, using fallback")
                # Fallback if no JSON found
                result = {"genre": "No Genre", "subs": [], "conf": 0}
            
            # Ensure we have valid data or default to "No Genre"
            if not result or not result.get("genre") or result.get("conf", 0) < 50:
                return {
                    "genre": "No Genre",
                    "subs": [],
                    "conf": 0
                }

            # Process the LLM result through our categorized genres system
            processed_result = self.process_llm_genre_result(result)
            
            print(f"AI Genre Analysis (processed): {processed_result}")
            return processed_result

        except Exception as e:
            print(f"Error in AI genre detection: {e}")
            return {
                "genre": "No Genre",
                "subs": [],
                "conf": 0
            }
    
    def process_llm_genre_result(self, llm_result):
        """Process LLM genre results through categorized_genres.json for consistency."""
        try:
            from resource_path import get_resource_path
            
            # Load categorized genres
            categorized_path = get_resource_path('config/categorized_genres.json')
            with open(categorized_path, 'r') as json_file:
                categorized_genres = json.load(json_file)
            
            # Extract LLM data
            llm_genre = llm_result.get("genre", "").strip()
            llm_subgenres = llm_result.get("subs", [])
            confidence = llm_result.get("conf", 0)
            
            print(f"Processing LLM result - Genre: {llm_genre}, Subs: {llm_subgenres}")
            
            # Step 1: Map the primary genre to our categorized system
            final_genre = self.map_genre_to_categories(llm_genre, categorized_genres)
            
            # Step 2: Process subgenres and validate them against our system
            final_subgenres = self.map_subgenres_to_categories(llm_subgenres, final_genre, categorized_genres)
            
            # Step 3: If we couldn't map the genre properly, try to infer from subgenres
            if final_genre == "No Genre" and final_subgenres:
                final_genre = self.infer_genre_from_subgenres(final_subgenres, categorized_genres)
            
            result = {
                "genre": final_genre,
                "subs": final_subgenres[:3],  # Limit to 3 subgenres
                "conf": confidence
            }
            
            print(f"Processed genre result: {result}")
            return result
            
        except Exception as e:
            print(f"Error processing LLM genre result: {e}")
            return llm_result  # Return original if processing fails
    
    def map_genre_to_categories(self, llm_genre, categorized_genres):
        """Map LLM genre to our categorized genres system."""
        if not llm_genre or llm_genre.lower() == "no genre":
            return "No Genre"
        
        llm_genre_lower = llm_genre.lower().strip()
        
        # Direct match with main categories
        for main_genre in categorized_genres.keys():
            if llm_genre_lower == main_genre.lower():
                return main_genre
        
        # Fuzzy matching with common variations
        genre_mappings = {
            "hip-hop": "Hip-Hop",
            "hip hop": "Hip-Hop", 
            "rap": "Hip-Hop",
            "r&b": "R&B",
            "rnb": "R&B",
            "rhythm and blues": "R&B",
            "electronic": "Electronic",
            "edm": "Electronic",
            "dance": "Electronic",
            "pop": "Pop",
            "rock": "Rock",
            "funk": "Funk",
            "reggae": "Reggae",
            "soul": "Soul",
            "jazz": "Jazz",
            "blues": "Blues",
            "alternative": "Alternative",
            "world": "World Music",
            "world music": "World Music",
            "afrobeats": "Afrobeats",
            "afrobeat": "Afrobeats"
        }
        
        if llm_genre_lower in genre_mappings:
            return genre_mappings[llm_genre_lower]
        
        # Check if the LLM genre appears as a subgenre in our system
        for main_genre, subgenres_list in categorized_genres.items():
            for subgenres_str in subgenres_list:
                subgenres = [s.strip().lower() for s in subgenres_str.split(',')]
                if llm_genre_lower in subgenres:
                    return main_genre
        
        return "No Genre"
    
    def map_subgenres_to_categories(self, llm_subgenres, mapped_genre, categorized_genres):
        """Map LLM subgenres to valid subgenres in our system."""
        if not llm_subgenres or mapped_genre == "No Genre":
            return []
        
        valid_subgenres = []
        
        # Get the valid subgenres for this main genre
        genre_subgenres = []
        if mapped_genre in categorized_genres:
            for subgenres_str in categorized_genres[mapped_genre]:
                genre_subgenres.extend([s.strip().lower() for s in subgenres_str.split(',')])
        
        # Check each LLM subgenre against our valid list
        for sub in llm_subgenres:
            sub_lower = sub.lower().strip()
            
            # Direct match
            if sub_lower in genre_subgenres:
                valid_subgenres.append(sub_lower)
                continue
            
            # Fuzzy matching for common variations
            for valid_sub in genre_subgenres:
                if (sub_lower in valid_sub or valid_sub in sub_lower) and len(sub_lower) > 3:
                    valid_subgenres.append(valid_sub)
                    break
        
        return list(dict.fromkeys(valid_subgenres))  # Remove duplicates while preserving order
    
    def infer_genre_from_subgenres(self, subgenres, categorized_genres):
        """Try to infer the main genre from valid subgenres."""
        for main_genre, subgenres_list in categorized_genres.items():
            genre_subs = []
            for subgenres_str in subgenres_list:
                genre_subs.extend([s.strip().lower() for s in subgenres_str.split(',')])
            
            # If any of our subgenres match this main genre's subgenres
            if any(sub in genre_subs for sub in subgenres):
                return main_genre
        
        return "No Genre"

    def standardize_genre(self, genre):
        """Standardize genre names using categorized_genres.json."""
        try:
            # Import the resource path helper
            from resource_path import get_resource_path
            
            # Load both JSON files using the helper
            categorized_path = get_resource_path('config/categorized_genres.json')
            print(f"Loading categorized genres from: {categorized_path}")

            # Load categorized genres
            with open(categorized_path, 'r') as json_file:
                categorized_genres = json.load(json_file)

            # Convert input genre to lowercase for matching
            genre_lower = genre.lower() if genre else ''

            # First check if it's already a main genre
            for main_genre in categorized_genres.keys():
                if genre_lower == main_genre.lower():
                    return ' '.join(word.capitalize() for word in main_genre.split())

            # Then check subgenres
            for main_genre, subgenres in categorized_genres.items():
                # Normalize subgenres for matching
                normalized_subgenres = [subgenre.lower() for subgenre in subgenres]
                
                # Check for exact matches first
                if genre_lower in normalized_subgenres:
                    return ' '.join(word.capitalize() for word in main_genre.split())
                
                # Check for partial matches
                for subgenre in normalized_subgenres:
                    # Handle special cases
                    if genre_lower in ['afrobeat', 'afrobeats']:
                        return 'Afrobeats'
                    if genre_lower in ['reggae', 'dancehall']:
                        return 'Reggae/Dancehall'
                    if genre_lower in ['rnb', 'r&b']:
                        return 'R&B'
                        
                    # Check if subgenre contains our genre or vice versa
                    if genre_lower in subgenre or subgenre in genre_lower:
                        return ' '.join(word.capitalize() for word in main_genre.split())

            # If no match found, return the original genre with proper capitalization
            return ' '.join(word.capitalize() for word in genre.split()) if genre else genre

        except Exception as e:
            print(f"Error standardizing genre: {e}")
            return genre

    def get_cached_artist_genres(self, artist_name):
        """Get cached genres for artist with strict matching."""
        try:
            print(f"Looking up cached genres for artist: {artist_name}")
            
            # Clean the artist name for comparison
            clean_name = self.clean_string(artist_name).lower()
            
            # Look for exact artist match only
            for key, entry in self.metadata_cache.cache.items():
                if not key.startswith('artist_genres_'):
                    continue
                    
                if not isinstance(entry, dict) or 'value' not in entry:
                    continue
                    
                value = entry.get('value', {})
                if not isinstance(value, dict):
                    continue
                
                # Get the cached artist name and Spotify ID
                cached_name = value.get('artist_name', '').lower()
                cached_id = value.get('artist_id', '')
                
                if not cached_name:  # Skip invalid entries
                    continue
                
                # Only match if we have an exact name match or ID match
                if (clean_name == self.clean_string(cached_name) or 
                    (cached_id and cached_id == value.get('artist_id'))):
                    if value.get('genre') and value.get('subgenres'):
                        print(f"Found exact genre match for {artist_name} with cached artist: {cached_name}")
                        return value.get('genre'), value.get('subgenres')
                
            print(f"No cached genres found for {artist_name}")
            return None, None
                    
        except Exception as e:
            print(f"Error checking artist cache: {e}")
            return None, None

    def _cache_and_save_results(self, cleaned_artist, query_title, genre, subgenres, audio_file):
        """Store results in cache and save to file."""
        try:
            # Create cache key and data
            cache_key = self.metadata_cache.generate_cache_key(cleaned_artist, query_title)
            cache_data = {
                'genre': genre,
                'subgenres': subgenres,
                'source': 'ai' if genre != "No Genre" else 'musicbrainz',
                'timestamp': time.time()
            }
            
            print(f"Caching metadata: {cache_data}")
            self.metadata_cache.set(cache_key, cache_data)
            
            # Create metadata for file
            metadata = {
                'genre': genre,
                'subgenres': subgenres
            }
            
            # Write to file
            success = self.utility_tools.set_metadata(audio_file, metadata)
            if success:
                print(f"Genre information written to file: {genre} | {subgenres}")
                return True
            return False
                
        except Exception as e:
            print(f"Error in cache_and_save_results: {e}")
            return False

    def cache_artist_genres(self, artist_name, artist_id, genre, subgenres):
        """Cache artist genres with proper artist information."""
        try:
            # Create a specific cache key
            cache_key = f"artist_genres_{self.clean_string(artist_name)}"
            
            # Create cache data with full artist info
            cache_data = {
                'artist_name': artist_name,
                'artist_id': artist_id,
                'genre': genre,
                'subgenres': subgenres,
                'source': 'musicbrainz',
                'timestamp': time.time()
            }
            
            print(f"Caching genres for {artist_name} (ID: {artist_id}): {cache_data}")
            self.metadata_cache.set(cache_key, cache_data)
            
        except Exception as e:
            print(f"Error caching artist genres: {e}")

    def _write_genres_to_file(self, audio_file, genre, subgenres):
        """Write genre information to audio file."""
        try:
            metadata = {
                'genre': genre,
                'subgenres': subgenres
            }
            self.utility_tools.set_metadata(audio_file, metadata)
            print(f"Genre information written to file: {genre} | {subgenres}")
        except Exception as e:
            print(f"Error writing genres to file: {e}")

    def clear_cache(self):
        """Clear the genre cache."""
        try:
            self.metadata_cache.clear()
            print("Genre cache cleared successfully")
        except Exception as e:
            print(f"Error clearing genre cache: {e}")