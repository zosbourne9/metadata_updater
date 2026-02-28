"""
Genre Knowledge Base using Retrieval-Augmented Generation (RAG)

This module provides a RAG system that uses your curated genre definitions
from config/genre_characteristics.json to augment AI genre classification.

The system:
1. Loads genre characteristics from JSON
2. Converts them into documents and embeddings
3. Creates a vector store for semantic search
4. Retrieves relevant genre context when classifying music

This allows the AI to make classifications based on your specific genre
definitions rather than just its training data.
"""

import json
import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

# Use updated LangChain imports for v1.0+
try:
    from langchain_community.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    # Fallback for older LangChain versions
    try:
        from langchain.vectorstores import Chroma
        from langchain.embeddings import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.vectorstores import Chroma
        from langchain_community.embeddings import HuggingFaceEmbeddings

# Document import - works in v1.0+
try:
    from langchain_core.documents import Document
except ImportError:
    # Fallback for older versions
    try:
        from langchain.schema import Document
    except ImportError:
        from langchain_core.schema import Document

logger = logging.getLogger(__name__)


class GenreKnowledgeBase:
    """RAG-powered genre knowledge system using Chroma vector store."""

    def __init__(self, config_path: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize the genre knowledge base.

        Args:
            config_path: Path to genre_characteristics.json. If None, searches standard locations.
            cache_dir: Directory for Chroma persistent storage. If None, uses in-memory store.
        """
        self.vectorstore = None
        self.genre_data = {}
        self.documents = []
        self._initialized = False

        try:
            # Find config file
            config_file = self._find_config_file(config_path)
            if not config_file:
                logger.warning("Genre characteristics file not found, RAG disabled")
                return

            # Load genre data
            self.genre_data = self._load_genre_data(config_file)
            if not self.genre_data:
                logger.warning("No genre data loaded, RAG disabled")
                return

            # Create documents from genre data
            self.documents = self._create_documents()
            if not self.documents:
                logger.warning("No documents created from genre data, RAG disabled")
                return

            # Initialize embeddings
            embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",  # Lightweight, fast model
                model_kwargs={"device": "cpu"}  # Use CPU to avoid GPU memory issues
            )

            # Create vector store
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
                self.vectorstore = Chroma.from_documents(
                    self.documents,
                    embeddings,
                    persist_directory=os.path.join(cache_dir, "genre_knowledge"),
                    collection_name="genres"
                )
            else:
                # In-memory store (recreated each run)
                self.vectorstore = Chroma.from_documents(
                    self.documents,
                    embeddings,
                    collection_name="genres"
                )

            self._initialized = True
            logger.info(f"✓ Genre knowledge base initialized with {len(self.genre_data)} genres")

        except Exception as e:
            logger.error(f"Error initializing genre knowledge base: {e}", exc_info=True)
            self._initialized = False

    def _find_config_file(self, config_path: Optional[str] = None) -> Optional[str]:
        """Find the genre_characteristics.json file."""
        if config_path and os.path.exists(config_path):
            return config_path

        # Search standard locations
        search_paths = [
            "config/genre_characteristics.json",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "genre_characteristics.json"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "genre_characteristics.json")),
        ]

        for path in search_paths:
            if os.path.exists(path):
                logger.debug(f"Found genre characteristics at: {path}")
                return path

        logger.warning(f"Genre characteristics not found in any of: {search_paths}")
        return None

    def _load_genre_data(self, config_path: str) -> Dict[str, Any]:
        """Load genre characteristics from JSON file."""
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            logger.debug(f"Loaded {len(data)} genres from {config_path}")
            return data
        except Exception as e:
            logger.error(f"Error loading genre data from {config_path}: {e}")
            return {}

    def _create_documents(self) -> List[Document]:
        """Convert genre data into LangChain documents for embedding."""
        documents = []

        for genre_name, genre_info in self.genre_data.items():
            # Build comprehensive document content
            content_parts = []

            # Genre name
            content_parts.append(f"Genre: {genre_name}")

            # Related terms
            if genre_info.get("related_terms"):
                terms = ", ".join(genre_info["related_terms"])
                content_parts.append(f"Related Terms: {terms}")

            # Subgenres
            if genre_info.get("subgenres"):
                subgenres = ", ".join(genre_info["subgenres"][:10])  # Limit to first 10
                content_parts.append(f"Subgenres: {subgenres}")

            # BPM range
            if genre_info.get("bpm_range"):
                bpm = genre_info["bpm_range"]
                content_parts.append(f"Typical BPM: {bpm[0]}-{bpm[1]}")

            # Year range (for historical genres)
            if genre_info.get("year_range"):
                year = genre_info["year_range"]
                content_parts.append(f"Historical Period: {year[0]}-{year[1]}")

            # Modern alternative (for legacy genres)
            if genre_info.get("modern_alternative"):
                content_parts.append(f"Modern Alternative: {genre_info['modern_alternative']}")

            # Regional variations (for genres like Soca)
            if genre_info.get("regional_variations"):
                regions = ", ".join(genre_info["regional_variations"][:5])
                content_parts.append(f"Regional Variations: {regions}")

            # Join all content
            full_content = "\n".join(content_parts)

            # Create document with metadata
            # NOTE: Chroma requires metadata values to be strings, ints, floats, or bools
            # Convert lists to JSON strings
            doc = Document(
                page_content=full_content,
                metadata={
                    "genre": genre_name,
                    "related_terms": json.dumps(genre_info.get("related_terms", [])),
                    "subgenres": json.dumps(genre_info.get("subgenres", [])),
                }
            )
            documents.append(doc)

        logger.debug(f"Created {len(documents)} documents from genre data")
        return documents

    def is_initialized(self) -> bool:
        """Check if knowledge base is properly initialized."""
        return self._initialized and self.vectorstore is not None

    def get_relevant_genres(
        self,
        artist_name: str,
        track_title: str = "",
        album_name: str = "",
        k: int = 3
    ) -> str:
        """
        Retrieve relevant genre context for an artist/track/album.

        Args:
            artist_name: Artist name to search for
            track_title: Track title (optional, for context)
            album_name: Album name (optional, for context)
            k: Number of genres to retrieve

        Returns:
            Formatted string with relevant genre information for use in prompts
        """
        if not self.is_initialized():
            logger.debug("Knowledge base not initialized, returning empty context")
            return ""

        try:
            # Build search query
            query_parts = [artist_name]
            if track_title:
                query_parts.append(track_title)
            if album_name:
                query_parts.append(album_name)

            query = " ".join(query_parts)

            # Search for relevant genres
            results = self.vectorstore.similarity_search(query, k=k)

            if not results:
                logger.debug(f"No similar genres found for query: {query}")
                return ""

            # Format results
            genre_context_lines = ["### Relevant Genre Characteristics:"]

            for result in results:
                genre = result.metadata.get("genre", "Unknown")
                content = result.page_content

                genre_context_lines.append(f"\n**{genre}:**")
                genre_context_lines.append(content)

            genre_context = "\n".join(genre_context_lines)
            logger.debug(f"Retrieved genre context for: {query}")
            return genre_context

        except Exception as e:
            logger.error(f"Error retrieving genre context: {e}", exc_info=True)
            return ""

    def get_genre_info(self, genre_name: str) -> Optional[Dict[str, Any]]:
        """
        Get raw genre information from the knowledge base.

        Args:
            genre_name: Name of the genre to look up

        Returns:
            Dictionary with genre information, or None if not found
        """
        if not self.genre_data:
            return None

        # Exact match first
        if genre_name in self.genre_data:
            return self.genre_data[genre_name]

        # Case-insensitive match
        for key, value in self.genre_data.items():
            if key.lower() == genre_name.lower():
                return value

        return None

    def get_all_genres(self) -> List[str]:
        """Get list of all genres in the knowledge base."""
        return list(self.genre_data.keys())

    def get_subgenres(self, genre_name: str) -> List[str]:
        """Get all subgenres for a given genre."""
        genre_info = self.get_genre_info(genre_name)
        if genre_info:
            return genre_info.get("subgenres", [])
        return []

    def get_related_terms(self, genre_name: str) -> List[str]:
        """Get all related search terms for a genre."""
        genre_info = self.get_genre_info(genre_name)
        if genre_info:
            return genre_info.get("related_terms", [])
        return []


# Module-level instance (lazy initialized)
_knowledge_base = None


def get_knowledge_base(
    config_path: Optional[str] = None,
    cache_dir: Optional[str] = None
) -> GenreKnowledgeBase:
    """
    Get or create the module-level genre knowledge base instance.

    This allows the knowledge base to be shared across the application
    without recreating it multiple times.

    Args:
        config_path: Path to genre_characteristics.json
        cache_dir: Directory for persistent vector store cache

    Returns:
        GenreKnowledgeBase instance
    """
    global _knowledge_base

    if _knowledge_base is None:
        _knowledge_base = GenreKnowledgeBase(config_path, cache_dir)

    return _knowledge_base


def reset_knowledge_base():
    """Reset the module-level knowledge base instance."""
    global _knowledge_base
    _knowledge_base = None
