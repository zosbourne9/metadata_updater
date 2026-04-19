import json
import os
import re
import unicodedata
from openai import OpenAI
from typing import List, Dict, Optional
from fuzzywuzzy import fuzz
from constants import AI_MODEL

VERSION = "1.2.0"

class ArtistNormalizer:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize ArtistNormalizer with OpenRouter Gemini 2.5 Flash."""
        self.client = None
        
        if api_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
        
        self.cache_path = './.artist_variations_cache'
        self.cache = self.load_cache()
        
        # Initialize patterns for basic normalization
        self.duo_patterns = {
            r'hall\s*[&\+\-]\s*oates': 'daryl hall & john oates',
            r'simon\s*[&\+\-]\s*garfunkel': 'simon & garfunkel'
        }

    def preprocess_artist_name(self, artist_name):
        """
        Determine if artist name should be cleaned or kept as-is before searching.
        Returns tuple of (should_clean, processed_name)
        """
        # Group patterns that should NOT be cleaned
        group_patterns = [
            # Band names with specific formats
            r'^[A-Za-z\s]+\s*&\s*[A-Za-z\s]+$',  # e.g. "Hall & Oates"
            r'^[A-Za-z\s]+,\s*[A-Za-z\s]+\s*&\s*[A-Za-z\s]+$',  # e.g. "Crosby, Stills & Nash"
            
            # Known specific groups
            r'^Earth,?\s*Wind\s*&\s*Fire$',
            r'^Simon\s*&\s*Garfunkel$',
            r'^Hall\s*&\s*Oates$',
            r'^Bell\s*Biv\s*DeVoe$',
            
            # General group patterns
            r'^The\s+[A-Za-z\s&]+$',  # e.g. "The Mamas & The Papas"
        ]
        
        # Feature patterns that SHOULD be cleaned
        feature_patterns = [
            r'(\s+|^)feat\.?\s+',
            r'(\s+|^)ft\.?\s+',
            r'(\s+|^)featuring\s+',
            r'(\s+|^)with\s+',
            r'\s*\(.*?(feat|ft|featuring).*?\)',
            r'\s*\[.*?(feat|ft|featuring).*?\]'
        ]

        # NEW: Check if this is a simple single-word artist name
        if re.match(r'^[A-Za-z]+$', artist_name):
            print(f"Simple single-name artist found: '{artist_name}', keeping as-is")
            return False, artist_name
        
        # First check if this contains any featuring patterns
        artist_name_lower = artist_name.lower()
        for pattern in feature_patterns:
            if re.search(pattern, artist_name_lower):
                print(f"Found featuring pattern in '{artist_name}', will clean")
                return True, artist_name
        
        # Then check if this matches any known group patterns
        for pattern in group_patterns:
            if re.match(pattern, artist_name, re.IGNORECASE):
                print(f"Found group pattern match for '{artist_name}', keeping as-is")
                return False, artist_name
        
        # If no patterns match, should clean
        print(f"No specific patterns match for '{artist_name}', will clean")
        return True, artist_name

    def normalize_artist_name(self, artist_name: str) -> List[str]:
        """Enhanced artist name normalization with minimal AI usage."""
        should_clean, artist_name = self.preprocess_artist_name(artist_name)
        
        if not should_clean:
            # Just generate basic variations without cleaning for groups
            variations = {artist_name}
            variations.add(self.clean_artist_name(artist_name))
            variations.update(self.generate_format_variations(artist_name))
            return list(filter(None, variations))
        
        normalized = artist_name.lower()
        cache_key = self.clean_artist_name(normalized)
        
        # Check cache first
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Generate basic variations first
        variations = {normalized}
        variations.add(self.clean_artist_name(normalized))
        variations.update(self.generate_format_variations(normalized))
        
        # Only use AI if basic matching fails
        if self.client and len(variations) < 2:
            ai_variations = self.get_ai_variations(normalized)
            variations.update(ai_variations)
        
        cleaned_variations = {self.clean_artist_name(v) for v in variations}
        final_variations = list(filter(None, cleaned_variations))
        
        self.cache[cache_key] = final_variations
        self.save_cache()
        
        return final_variations

    def get_ai_variations(self, artist_name: str) -> List[str]:
        """Get artist name variations using OpenRouter Gemini 2.5 Flash."""
        try:
            prompt = f"""You are a music database expert. Generate variations of the artist name, including previous names, alternate spellings, and common variations.

Artist: {artist_name}

Return only a JSON array of strings with all known variations:
["variation1", "variation2", "variation3"]"""

            response = self.client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": "Generate artist name variations. Return only JSON array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=200
            )
            response_text = response.choices[0].message.content

            # Extract JSON array from response
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                variations = json.loads(json_str)
            else:
                variations = []
                
            print(f"AI generated variations for {artist_name}: {variations}")
            return variations

        except Exception as e:
            print(f"Error getting AI variations: {e}")
            return []

    def generate_format_variations(self, name: str) -> set:
        """Generate common format variations of the artist name."""
        variations = set()
        
        # Base variation
        variations.add(name)
        
        # Handle special characters and formatting
        formats = [
            (r'\band\b', '&'),
            (r'\band\b', '+'),
            (r'\band\b', 'n'),
            (r'\s+', ''),
            (r'\s+', '-'),
            (r'\.', ''),
            (r'ft\.?|feat\.?|featuring', 'feat')
        ]
        
        for pattern, replacement in formats:
            try:
                new_variation = re.sub(pattern, replacement, name)
                if new_variation != name:
                    variations.add(new_variation)
            except Exception as e:
                print(f"Error generating variation: {e}")
                continue
        
        return variations

    def fuzzy_match_artists(self, str1: str, str2: str, threshold: int = 85) -> int:
        """Enhanced fuzzy matching for artist names with better variation handling."""
        try:
            # Get variations for both strings
            str1_variations = self.normalize_artist_name(str1)
            str2_variations = self.normalize_artist_name(str2)
            
            # Try all combinations and return the highest match score
            best_score = 0
            for var1 in str1_variations:
                for var2 in str2_variations:
                    # Clean strings for comparison
                    clean1 = re.sub(r'[^\w\s]', '', var1).lower()
                    clean2 = re.sub(r'[^\w\s]', '', var2).lower()
                    
                    # Calculate multiple matching scores
                    token_sort_score = fuzz.token_sort_ratio(clean1, clean2)
                    token_set_score = fuzz.token_set_ratio(clean1, clean2)
                    partial_ratio = fuzz.partial_ratio(clean1, clean2)
                    
                    # Use the highest score
                    score = max(token_sort_score, token_set_score, partial_ratio)
                    best_score = max(best_score, score)
                    
                    # Early return if we find a very good match
                    if best_score >= 95:
                        return best_score
                    
            return best_score

        except Exception as e:
            print(f"Error in fuzzy matching: {e}")
            return 0

    def clean_artist_name(self, name: str) -> str:
        """
        Clean and normalize artist name, including leetspeak and special characters.

        For collaborative tracks, keeps primary artists but removes featured artist clauses.

        Examples:
            "Compton Av, Steelz, Blueface & Lola Brooke ft Natalie Nunn & India Love"
            → "compton av steelz blueface lola brooke"
            (removes "ft Natalie Nunn & India Love")

            "The Beatles feat. Yoko Ono" → "the beatles"
        """
        try:
            # Convert to lowercase
            name = name.lower()

            # Step 1: Normalize leetspeak and special characters
            # This handles: $ → S, @ → A, ! → I, 3 → E, 4 → A, 5 → S, 7 → T, 0 → O, 1 → I, etc.
            leetspeak_map = {
                '$': 's', '@': 'a', '!': 'i', '3': 'e', '4': 'a',
                '5': 's', '7': 't', '0': 'o', '1': 'i', '8': 'b', '9': 'g'
            }
            for leet_char, normal_char in leetspeak_map.items():
                name = name.replace(leet_char, normal_char)

            # Step 2: Remove accents and normalize unicode (é → e, ñ → n, etc.)
            nfd_form = unicodedata.normalize('NFD', name)
            name = ''.join(char for char in nfd_form if unicodedata.category(char) != 'Mn')

            # Step 3: Remove featured artist clauses (but keep collaborators)
            # Only remove content that comes AFTER explicit feature keywords
            # This preserves "Artist1, Artist2 & Artist3" but removes "ft. Guest Artist"
            featured_patterns = [
                # Remove "featuring ...", "feat. ...", "ft. ...", etc. and everything after
                r'\s+(featuring|feat\.?|ft\.?)\s+.*$',
                # Remove "with ..." when followed by typical featured artist names
                r'\s+with\s+[^,&]+$',
                # Remove content in parentheses that are ONLY featuring info
                r'\s*\(\s*feat\.?.*?\)',
                r'\s*\(\s*featuring.*?\)',
            ]
            for pattern in featured_patterns:
                name = re.sub(pattern, '', name, flags=re.IGNORECASE)

            # Step 4: Replace common collaborator separators with spaces for consistency
            # Convert "&" and "," to spaces so "Artist1, Artist2 & Artist3" becomes "artist1 artist2 artist3"
            name = re.sub(r'[,&]', ' ', name)

            # Step 5: Clean up extra spaces
            name = re.sub(r'\s+', ' ', name)
            return name.strip()

        except Exception as e:
            print(f"Error cleaning artist name: {e}")
            return name

    def load_cache(self) -> Dict[str, List[str]]:
        """Load the cache from disk."""
        try:
            if not os.path.exists(self.cache_path):
                return {}
            with open(self.cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
            return {}

    def save_cache(self) -> None:
        """Save the cache to disk."""
        try:
            with open(self.cache_path, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            print(f"Error saving cache: {e}")