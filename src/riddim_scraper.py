"""
Riddim Scraper for dancehall/reggae metadata lookup.

This module provides scraped metadata for dancehall and reggae songs from riddimguide.com.
It specializes in finding riddim information, which is crucial for categorizing dancehall/reggae tracks.

Usage:
    from riddim_scraper import RiddimScraper
    scraper = RiddimScraper()
    songs = scraper.search("bob marley")
    scraper.close()
"""

import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class RiddimScraper:
    """
    Scraper for riddimguide.com song data.

    Specializes in dancehall and reggae music metadata, particularly riddim information
    which is essential for proper categorization of these genres.
    """

    BASE_URL = "https://www.riddimguide.com"

    def __init__(self):
        """Initialize the HTTP client with proper headers and timeout."""
        self.client = httpx.Client(
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        self.is_available = True

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for songs on riddimguide.com.

        Args:
            query (str): Search query (artist, song title, or combination)

        Returns:
            List[Dict]: List of songs with metadata (artist, title, riddim, year, label, producer)
                       Returns empty list if search fails (no exception raised)
        """
        try:
            url = f"{self.BASE_URL}/tunes"
            params = {"q": query, "c": ""}

            response = self.client.get(url, params=params)
            response.raise_for_status()

            songs = self._parse_search_results(response.text)
            logger.info(f"RiddimGuide: Found {len(songs)} songs for query: {query}")
            return songs

        except Exception as e:
            logger.warning(f"RiddimGuide search failed for query '{query}': {str(e)}")
            self.is_available = False
            return []  # Return empty list instead of raising - graceful degradation

    def _parse_search_results(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse HTML search results and extract song data.

        Looks for table rows containing: Artist | Song | Riddim | Year | Label | Producer
        """
        try:
            # Try lxml first (faster), fall back to html.parser
            try:
                soup = BeautifulSoup(html, "lxml")
            except Exception:
                logger.debug("lxml parser not available, using html.parser fallback")
                soup = BeautifulSoup(html, "html.parser")

            songs = []

            # Find the results table
            table = soup.find("table")

            if not table:
                logger.debug("No results table found in RiddimGuide response")
                return songs

            rows = table.find_all("tr")[1:]  # Skip header row

            for row in rows:
                try:
                    cells = row.find_all("td")
                    if len(cells) < 6:
                        continue

                    song = {
                        "artist": self._extract_text(cells[0]),
                        "title": self._extract_text(cells[1]),
                        "riddim": self._extract_text(cells[2]),
                        "year": self._parse_year(cells[3]),
                        "label": self._extract_text(cells[4]),
                        "producer": self._extract_text(cells[5]),
                        "source": "riddimguide"
                    }

                    # Only add if it has at least a title and artist
                    if song["title"] and song["artist"]:
                        songs.append(song)

                except Exception as e:
                    logger.debug(f"Error parsing RiddimGuide row: {str(e)}")
                    continue

            return songs

        except Exception as e:
            logger.warning(f"Error parsing RiddimGuide results: {str(e)}")
            return []

    def _extract_text(self, cell) -> str:
        """Extract text from a table cell, handling links."""
        try:
            if cell.find("a"):
                return cell.find("a").get_text(strip=True)
            return cell.get_text(strip=True)
        except:
            return ""

    def _parse_year(self, cell) -> Optional[int]:
        """Extract year from cell."""
        try:
            text = cell.get_text(strip=True)
            return int(text) if text and text.isdigit() else None
        except (ValueError, AttributeError):
            return None

    def close(self):
        """Close HTTP client."""
        try:
            self.client.close()
        except:
            pass


# Global singleton instance
_scraper_instance: Optional[RiddimScraper] = None


def get_riddim_scraper() -> RiddimScraper:
    """Get or create the global riddim scraper instance."""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = RiddimScraper()
    return _scraper_instance
