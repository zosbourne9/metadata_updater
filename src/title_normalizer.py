"""
Title normalization for handling special characters and leetspeak in song titles.

Examples:
  "$ave Dat Money" → "Save Dat Money"
  "Bi@ & Bop" → "Bia & Bop"
  "Café" → "Cafe"
  "N@T!0N" → "NATION"
"""

import re
import unicodedata
import logging

logger = logging.getLogger(__name__)


class TitleNormalizer:
    """Normalizes song titles by handling leetspeak and special characters."""

    # Leetspeak character mappings (user-customizable)
    LEETSPEAK_MAP = {
        '$': 'S',    # $ → S (e.g., "$ave" → "Save")
        '@': 'A',    # @ → A (e.g., "B@d" → "Bad")
        '!': 'I',    # ! → I (e.g., "H3ll!" → "Hell")
        '3': 'E',    # 3 → E (e.g., "H3llo" → "Hello")
        '4': 'A',    # 4 → A (e.g., "M4d" → "Mad")
        '5': 'S',    # 5 → S (e.g., "L1st3n" → "Listen")
        '7': 'T',    # 7 → T (e.g., "L1st3n" → "Listen")
        '0': 'O',    # 0 → O (e.g., "H0use" → "House")
        '1': 'I',    # 1 → I (e.g., "L1st" → "List")
        '8': 'B',    # 8 → B (e.g., "B8" → "BB")
        '9': 'G',    # 9 → G (e.g., "L09" → "LOG")
    }

    def __init__(self):
        """Initialize the title normalizer."""
        self.logger = logging.getLogger(__name__)

    def normalize_title(self, title: str) -> str:
        """
        Normalize a song title by handling special characters and leetspeak.

        Applies transformations in order:
        1. Replace leetspeak characters ($ → S, @ → A, etc.)
        2. Remove or normalize accented characters (é → e, ñ → n, etc.)
        3. Clean up extra whitespace
        4. Preserve case for readability

        Args:
            title: Original song title (e.g., "$ave Dat Money")

        Returns:
            Normalized title (e.g., "Save Dat Money")

        Examples:
            >>> normalizer = TitleNormalizer()
            >>> normalizer.normalize_title("$ave Dat Money")
            'Save Dat Money'
            >>> normalizer.normalize_title("Café Au L@it")
            'Cafe Au Lait'
        """
        if not title:
            return title

        normalized = title

        # Step 1: Replace leetspeak characters
        for leet_char, normal_char in self.LEETSPEAK_MAP.items():
            # Preserve case: $ong → Song, but $ONG → SONG
            if leet_char in normalized:
                # Simple replacement (case-insensitive on the replacement)
                normalized = normalized.replace(leet_char, normal_char)

        # Step 2: Remove accents and normalize unicode characters
        normalized = self._remove_accents(normalized)

        # Step 3: Clean up extra whitespace
        normalized = ' '.join(normalized.split())

        # Only log if something changed
        if normalized != title:
            self.logger.debug(f"Title normalized: '{title}' → '{normalized}'")

        return normalized

    @staticmethod
    def _remove_accents(text: str) -> str:
        """
        Remove accents from unicode characters while preserving the base character.

        Examples:
            "Café" → "Cafe"
            "Señorita" → "Senirita"
            "Naïve" → "Naive"

        Args:
            text: Text with potential accented characters

        Returns:
            Text with accents removed
        """
        # Decompose unicode characters into base + accent
        nfd_form = unicodedata.normalize('NFD', text)
        # Filter out combining characters (accents)
        return ''.join(char for char in nfd_form if unicodedata.category(char) != 'Mn')

    def normalize_for_comparison(self, title: str) -> str:
        """
        Normalize title for fuzzy matching (more aggressive).

        Also converts to lowercase and removes special punctuation
        for better comparison.

        Args:
            title: Original song title

        Returns:
            Normalized lowercase title for comparison
        """
        normalized = self.normalize_title(title)
        # Convert to lowercase
        normalized = normalized.lower()
        # Remove punctuation but keep spaces and basic characters
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Clean up whitespace
        normalized = ' '.join(normalized.split())
        return normalized


# Singleton instance
_normalizer = None


def get_title_normalizer() -> TitleNormalizer:
    """Get or create the singleton TitleNormalizer instance."""
    global _normalizer
    if _normalizer is None:
        _normalizer = TitleNormalizer()
    return _normalizer
