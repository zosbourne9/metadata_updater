from typing import Dict, List, Optional, Tuple
import re
import json
import os
import logging
from datetime import datetime
from openai import OpenAI

# Import RAG knowledge base
try:
    from genre_knowledge_base import get_knowledge_base
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    get_knowledge_base = None

logger = logging.getLogger(__name__)


class EnhancedGenreDetector:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize EnhancedGenreDetector with OpenRouter Gemini 2.5 Flash.

        Includes RAG (Retrieval-Augmented Generation) for enhanced genre knowledge.

        Args:
            api_key: OpenRouter API key
        """
        self.ai_client = None

        if api_key:
            self.ai_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )

        self.genre_cache = {}
        self.last_update = datetime.now()

        # Load genre characteristics
        try:
            # Import the resource path helper
            from resource_path import get_resource_path

            # Get the path to genre characteristics using the helper
            characteristics_path = get_resource_path('config/genre_characteristics.json')
            print(f"Loading genre characteristics in EnhancedGenreDetector from: {characteristics_path}")

            with open(characteristics_path, 'r') as f:
                self.genre_characteristics = json.load(f)
        except Exception as e:
            print(f"Error loading genre characteristics: {e}")
            self.genre_characteristics = {}

        # Initialize RAG knowledge base for lazy loading (will be loaded only when needed)
        self.knowledge_base = None
        self._knowledge_base_loaded = False

        # Enhanced patterns that strongly indicate genres
        self.genre_patterns = {
            'dancehall': {
                'musical_patterns': [
                    r'(?i)riddim',
                    r'(?i)bashment',
                    r'(?i)caribbean',
                    r'(?i)jamaica[n]?\b',
                    r'(?i)dance\s*hall',
                    r'(?i)big\s*tune',
                    r'(?i)pull\s*up',
                    r'(?i)selector',
                    r'(?i)sound\s*boy',
                    r'(?i)yard',
                    r'(?i)bless\s*up',
                    r'(?i)pon\s*di\s*corner',
                    r'(?i)gyal\s*dem',
                    r'(?i)badman'
                ],
                'production_patterns': [
                    r'(?i)dembow',
                    r'(?i)dancehall rhythm',
                    r'(?i)reggae fusion',
                    r'(?i)one\s*drop',
                    r'(?i)steppers'
                ],
                'artist_indicators': [
                    r'(?i)vybz\s*kartel',
                    r'(?i)popcaan',
                    r'(?i)shaggy',
                    r'(?i)sean\s*paul',
                    r'(?i)beenie\s*man',
                    r'(?i)bounty\s*killer'
                ]
            },
            'soca': {
                'musical_patterns': [
                    r'(?i)\bsoca\b',  # Direct soca mention (word boundary to avoid "asocial" etc)
                    r'(?i)carnival',
                    r'(?i)trinidad',
                    r'(?i)calypso',
                    r'(?i)groovy soca',
                    r'(?i)power soca',
                    r'(?i)fete',
                    r'(?i)mas',
                    r'(?i)bacchanal',
                    r'(?i)jumbie',
                    r'(?i)wine\s*down',
                    r'(?i)carnival\s*time',
                    r'(?i)jump\s*up',
                    r'(?i)wining'
                ],
                'production_patterns': [
                    r'(?i)jump and wave',
                    r'(?i)road march',
                    r'(?i)caribbean rhythm',
                    r'(?i)brass\s*section',
                    r'(?i)steel\s*pan'
                ],
                'artist_indicators': [
                    r'(?i)machel\s*montano',
                    r'(?i)kes',
                    r'(?i)bunji\s*garlin',
                    r'(?i)destra',
                    r'(?i)fay\-?ann\s*lyons'
                ]
            },
            'afrobeats': {
                'musical_patterns': [
                    r'(?i)afro\s*(?:beats|pop|wave|fusion)',
                    r'(?i)nigeria[n]?\b',
                    r'(?i)ghana[ian]?\b',
                    r'(?i)naija',
                    r'(?i)pon\s*pon',
                    r'(?i)zanku',
                    r'(?i)gwara\s*gwara',
                    r'(?i)azonto',
                    r'(?i)amapiano',
                    r'(?i)alte',
                    r'(?i)jollof'
                ],
                'production_patterns': [
                    r'(?i)afro rhythm',
                    r'(?i)african drums',
                    r'(?i)highlife fusion',
                    r'(?i)talking\s*drum',
                    r'(?i)log\s*drum',
                    r'(?i)percussion\s*heavy'
                ],
                'artist_indicators': [
                    r'(?i)wizkid',
                    r'(?i)burna\s*boy',
                    r'(?i)davido',
                    r'(?i)tems',
                    r'(?i)tiwa\s*savage',
                    r'(?i)yemi\s*alade',
                    r'(?i)mr\s*eazi'
                ]
            },
            'hip-hop': {
                'musical_patterns': [
                    r'(?i)rap',
                    r'(?i)hip\s*hop',
                    r'(?i)freestyle',
                    r'(?i)cypher',
                    r'(?i)bars',
                    r'(?i)spitting',
                    r'(?i)flow',
                    r'(?i)diss\s*track',
                    r'(?i)mixtape'
                ],
                'production_patterns': [
                    r'(?i)boom\s*bap',
                    r'(?i)trap\s*beat',
                    r'(?i)808',
                    r'(?i)sample\s*flip',
                    r'(?i)drum\s*break'
                ],
                'artist_indicators': [
                    r'(?i)lil\s*\w+',
                    r'(?i)young\s*\w+',
                    r'(?i)big\s*\w+'
                ]
            },
            'r&b': {
                'musical_patterns': [
                    r'(?i)r\&?b',
                    r'(?i)rhythm\s*and\s*blues',
                    r'(?i)smooth',
                    r'(?i)soulful',
                    r'(?i)crooning',
                    r'(?i)harmonies',
                    r'(?i)vocal\s*runs'
                ],
                'production_patterns': [
                    r'(?i)slow\s*jam',
                    r'(?i)ballad',
                    r'(?i)neo\s*soul',
                    r'(?i)contemporary\s*r\&?b'
                ]
            },
            'reggae': {
                'musical_patterns': [
                    r'(?i)reggae',
                    r'(?i)rasta',
                    r'(?i)jah',
                    r'(?i)babylon',
                    r'(?i)irie',
                    r'(?i)one\s*love'
                ],
                'production_patterns': [
                    r'(?i)one\s*drop',
                    r'(?i)skank',
                    r'(?i)off\s*beat',
                    r'(?i)dub'
                ],
                'artist_indicators': [
                    r'(?i)bob\s*marley',
                    r'(?i)damian\s*marley',
                    r'(?i)ziggy\s*marley'
                ]
            }
        }

    def _ensure_knowledge_base_loaded(self):
        """Lazy-load knowledge base only when actually needed."""
        if self._knowledge_base_loaded:
            return self.knowledge_base

        self._knowledge_base_loaded = True
        if RAG_AVAILABLE and get_knowledge_base:
            try:
                self.knowledge_base = get_knowledge_base()
                if self.knowledge_base and self.knowledge_base.is_initialized():
                    print("✓ RAG genre knowledge base lazily loaded")
                else:
                    print("⚠ RAG knowledge base not available, will use standard detection")
                    self.knowledge_base = None
            except Exception as e:
                logger.warning(f"Failed to initialize RAG knowledge base: {e}")
                self.knowledge_base = None
        else:
            if not RAG_AVAILABLE:
                logger.debug("LangChain/RAG not available, using standard detection only")

        return self.knowledge_base

    def detect_genre(self, artist: str, title: str, existing_genres: Optional[List[str]] = None, album_name: Optional[str] = None) -> Tuple[str, float]:
        """
        Multi-layered genre detection approach.
        Returns tuple of (detected_genre, confidence_score)
        """
        # Check cache first
        cache_key = f"{artist}_{title}".lower()
        if cache_key in self.genre_cache:
            return self.genre_cache[cache_key]

        confidence_scores = {
            'dancehall': 0.0,
            'soca': 0.0,
            'afrobeats': 0.0,
            'hip-hop': 0.0,
            'r&b': 0.0,
            'reggae': 0.0,
            'pop': 0.0,
            'rock': 0.0,
            'funk': 0.0,
            'disco': 0.0
        }

        # Layer 1: Enhanced Pattern Matching with weighted scoring
        search_text = f"{artist} {title}".lower()
        album_text = ""
        
        # Also include album name if provided (useful for hints like "Get Soca 2017")
        if album_name:
            album_text = f" {album_name}".lower()
            search_text += album_text
        
        for genre, patterns in self.genre_patterns.items():
            genre_score = 0.0
            for pattern_type, pattern_list in patterns.items():
                # Weight different pattern types
                weight = {
                    'musical_patterns': 0.4,
                    'production_patterns': 0.3,
                    'artist_indicators': 0.5
                }.get(pattern_type, 0.3)
                
                for pattern in pattern_list:
                    if re.search(pattern, search_text):
                        genre_score += weight
                        # Bonus points if pattern matches in album name (high confidence indicator)
                        if album_text and re.search(pattern, album_text):
                            genre_score += 0.6  # Strong signal from album context
                        
            confidence_scores[genre] = genre_score

        # Explicitly associate rap with hip-hop
        if 'rap' in confidence_scores:
            confidence_scores['hip-hop'] += confidence_scores['rap']
            confidence_scores.pop('rap')  # Remove rap as a separate genre

        # Layer 2: AI Analysis (if available)
        if self.ai_client:
            ai_genre, ai_confidence = self._analyze_with_ai(artist, title)
            if ai_genre and ai_genre in confidence_scores:
                confidence_scores[ai_genre] += ai_confidence

        # Layer 3: Contextual Analysis
        self._analyze_context(artist, title, confidence_scores)

        # Layer 4: Existing Genre Retention (from MusicBrainz or other sources)
        if existing_genres:
            for genre in existing_genres:
                # Add existing genre information to confidence scores
                confidence_scores[genre.lower()] = confidence_scores.get(genre.lower(), 0) + 1

        # Layer 5: Balanced tie-breaking logic
        def genre_priority(genre):
            """Defines priority for tie-breaking based on specificity and accuracy."""
            priority = {
                'dancehall': 1,     # High priority - very specific genre
                'soca': 2,          # High priority - very specific genre  
                'afrobeats': 3,     # High priority - specific and emerging
                'reggae': 4,        # Medium-high priority - specific
                'hip-hop': 5,       # Medium priority - broad but distinct
                'r&b': 6,           # Medium priority - no special bias
                'funk': 7,          # Medium priority
                'disco': 8,         # Medium priority
                'rock': 9,          # Lower priority - very broad
                'pop': 10,          # Lowest priority - most generic
            }
            return priority.get(genre, 100)  # Default low priority for unlisted genres

        # Sort by score, then by priority
        sorted_genres = sorted(
            confidence_scores.items(),
            key=lambda x: (-x[1], genre_priority(x[0]))
        )
        best_genre = sorted_genres[0]

        # Cache the result
        if best_genre[1] >= 0.6:  # Only cache if confidence is high enough
            self.genre_cache[cache_key] = best_genre

        return best_genre

    def validate_genre_tags(self, tags):
        """
        Validate and score genre tags using genre_characteristics.json data.
        Returns a sorted list of validated tags based on relevance scores.
        """
        try:
            # Initialize scoring for tags
            tag_scores = {}
            
            def genre_priority(genre):
                """Priority for tie-breaking based on specificity."""
                priority = {
                    'dancehall': 1,
                    'soca': 2,
                    'afrobeats': 3,
                    'reggae': 4,
                    'hip-hop': 5,
                    'r&b': 6,       # No special bias
                    'funk': 7,
                    'disco': 8,
                    'rock': 9,
                    'pop': 10       # Lowest priority - most generic
                }
                return priority.get(genre.lower(), 100)

            for tag in tags:
                tag_lower = tag.lower().strip()
                score = 0
                matches = []
                
                # Check against each genre's characteristics
                for genre, characteristics in self.genre_characteristics.items():
                    if tag_lower == genre.lower():
                        score += 10
                        matches.append((genre, 10))
                        continue
                    
                    # Related terms
                    if 'related_terms' in characteristics:
                        for term in characteristics['related_terms']:
                            if tag_lower == term.lower():
                                score += 5  # Equal scoring for all genres
                                matches.append((genre, 5))
                                break
                            elif term.lower() in tag_lower or tag_lower in term.lower():
                                score += 4  # Equal scoring for partial matches
                                matches.append((genre, 4))
                    
                    # Subgenres
                    if 'subgenres' in characteristics:
                        for subgenre in characteristics['subgenres']:
                            if tag_lower == subgenre.lower():
                                score += 7  # Equal scoring for all genres
                                matches.append((genre, 7))
                                break
                            elif subgenre.lower() in tag_lower:
                                score += 4  # Equal scoring for partial matches
                                matches.append((genre, 4))
                    
                    # BPM characteristics
                    if 'bpm_range' in characteristics and hasattr(self, 'bpm'):
                        bpm_range = characteristics['bpm_range']
                        if self.bpm and bpm_range[0] <= self.bpm <= bpm_range[1]:
                            score += 3  # Equal scoring for all genres
                            matches.append((genre, 3))
                
                # Special handling for compound genres
                compound_parts = tag_lower.split()
                if len(compound_parts) > 1:
                    for part in compound_parts:
                        for genre, chars in self.genre_characteristics.items():
                            if part in [term.lower() for term in chars.get('related_terms', [])]:
                                score += 2  # Equal scoring for all genres
                                matches.append((genre, 2))
                
                if score > 0:
                    tag_scores[tag] = {
                        'score': score,
                        'matches': matches
                    }
            
            # Sort tags by score and then by priority
            sorted_tags = sorted(
                tag_scores.keys(),
                key=lambda x: (-tag_scores[x]['score'], genre_priority(x))
            )
            
            return sorted_tags

        except Exception as e:
            print(f"Error in validate_genre_tags: {e}")
            return []

    def _analyze_with_ai(self, artist: str, title: str) -> Tuple[str, float]:
        """
        Use OpenRouter Gemini 2.5 Flash to analyze genre, enhanced with RAG knowledge.

        The system retrieves relevant genre characteristics from the knowledge base
        to provide better context for the AI model.
        """
        try:
            # Retrieve relevant genre context from RAG if available (lazy loaded)
            genre_context = ""
            kb = self._ensure_knowledge_base_loaded()
            if kb and kb.is_initialized():
                try:
                    genre_context = kb.get_relevant_genres(
                        artist_name=artist,
                        track_title=title,
                        k=3  # Get top 3 most relevant genres
                    )
                    if genre_context:
                        logger.debug(f"Retrieved RAG context for {artist} - {title}")
                except Exception as rag_error:
                    logger.debug(f"RAG retrieval failed: {rag_error}, continuing without context")
                    genre_context = ""

            # Build prompt with optional RAG context
            prompt_text = f"""You are a music genre expert. Analyze this artist and song to determine the most likely genre.

Artist: {artist}
Song: {title}
"""

            # Include RAG context if available
            if genre_context:
                prompt_text += f"\n{genre_context}\n"

            prompt_text += """
Consider the artist's origin, musical style, and song characteristics. Choose from these genres:
- Dancehall
- Soca
- Afrobeats
- Hip-Hop
- R&B
- Reggae
- Pop
- Rock
- Funk
- Disco

Return your response as JSON only in this exact format:
{{"genre": "genre_name", "confidence": 0.0-1.0}}"""

            response = self.ai_client.chat.completions.create(
                model="google/gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": "You are a music genre expert. Return only JSON responses."},
                    {"role": "user", "content": prompt_text}
                ],
                temperature=0.1,
                max_tokens=100
            )

            response_text = response.choices[0].message.content

            # Extract and parse JSON response
            json_str = response_text.strip()
            if not json_str.startswith('{'):
                json_start = json_str.find('{')
                if json_start != -1:
                    json_str = json_str[json_start:]
            if not json_str.endswith('}'):
                json_end = json_str.rfind('}')
                if json_end != -1:
                    json_str = json_str[:json_end + 1]

            result = json.loads(json_str)
            genre = result.get("genre", "").lower()
            confidence = float(result.get("confidence", 0.0))

            return genre, confidence

        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return None, 0.0

    def _analyze_context(self, artist: str, title: str, confidence_scores: Dict[str, float]):
        """Analyze contextual clues in the title and artist name."""
        # Seasonal context
        if re.search(r'(?i)carnival|cropover|jouvert', f"{artist} {title}"):
            confidence_scores['soca'] += 0.2

        # Collaboration patterns
        if re.search(r'(?i)feat\.?\s+(?:vybz|popcaan|shaggy|sean\s*paul)', f"{artist} {title}"):
            confidence_scores['dancehall'] += 0.15

        if re.search(r'(?i)feat\.?\s+(?:wizkid|burna\s*boy|davido|tems)', f"{artist} {title}"):
            confidence_scores['afrobeats'] += 0.15

        # Word choice patterns
        if re.search(r'(?i)wine|whine|gyal|badman|dutty', title):
            confidence_scores['dancehall'] += 0.1

        if re.search(r'(?i)waka|joro|doro|naija', title):
            confidence_scores['afrobeats'] += 0.1

    def update_patterns(self, new_patterns: Dict):
        """Allow dynamic updating of genre patterns."""
        self.genre_patterns.update(new_patterns)
        self.last_update = datetime.now()