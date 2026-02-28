"""
Integration helper to swap out the old complex system with the simplified one.

This provides a drop-in replacement that maintains the same interface
but uses the new simplified backend.
"""

from simplified_metadata_searcher import SimplifiedMetadataSearcher

class SimplifiedMetadataIntegration:
    """
    Drop-in replacement for the old MusicBrainzIntegration and SpotifyIntegration classes.
    Maintains compatibility with existing code while using the new simplified backend.
    """
    
    def __init__(self, parent=None, status_update_callback=None, cache_manager=None, **kwargs):
        """Initialize with the same interface as the old classes."""
        self.parent = parent
        self.cache_manager = cache_manager
        
        # Create the simplified searcher
        self.searcher = SimplifiedMetadataSearcher(
            parent=parent,
            status_update_callback=status_update_callback,
            cache_manager=cache_manager
        )

        # Expose artist_normalizer for compatibility
        self.artist_normalizer = self.searcher.artist_normalizer

        print("✅ Simplified metadata integration loaded")

    def search_metadata(self, artist_name, track_title, riddim_mode=None):
        """Main search method - same interface as old system.

        Args:
            artist_name: Name of the artist
            track_title: Title of the track
            riddim_mode: Dict with riddim mode flags (isDancehall, isReggae)
        """
        return self.searcher.search_metadata(artist_name, track_title, riddim_mode=riddim_mode)
    
    def get_artist_genres_from_mb(self, artist_name):
        """Get artist genres - same interface as old MusicBrainz integration."""
        return self.searcher.musicbrainz.get_artist_genres_from_mb(artist_name)
    
    def clear_cache(self):
        """Clear cache - same interface as old system."""
        self.searcher.clear_all_caches()
    
    def test_connection(self):
        """Test connections - same interface as old system.""" 
        results = self.searcher.test_connections()
        return results.get('musicbrainz', False) or results.get('spotify', False)

    # Legacy method names for compatibility
    def search_track_metadata(self, artist_name, track_title, riddim_mode=None):
        """Legacy method name support."""
        return self.search_metadata(artist_name, track_title, riddim_mode=riddim_mode)
    
    def get_metadata(self, artist_name, track_title):
        """Legacy method name support."""
        return self.search_metadata(artist_name, track_title)
    
    def extract_metadata_from_spotify(self, artist_name, track_title, *args, **kwargs):
        """Legacy method for Spotify extraction - now uses unified search."""
        # The new system automatically tries both MusicBrainz and Spotify
        # Accept any additional arguments for compatibility but ignore them
        return self.search_metadata(artist_name, track_title)

def replace_integrations_in_main(main_instance):
    """
    Helper function to replace the old integrations in a main application instance.
    
    Usage:
        from integration_helper import replace_integrations_in_main
        replace_integrations_in_main(self)  # Call from within your main class
    """
    try:
        print("🔄 Replacing old integrations with simplified system...")
        
        # Get existing parameters
        parent = getattr(main_instance, 'parent', None)
        cache_manager = getattr(main_instance, 'cache_manager', None)
        status_callback = getattr(main_instance, 'status_update_callback', None)
        
        # Create new integrated searcher
        new_integration = SimplifiedMetadataIntegration(
            parent=parent,
            status_update_callback=status_callback,
            cache_manager=cache_manager
        )
        
        # Replace the old integrations
        if hasattr(main_instance, 'mb_integration'):
            main_instance.mb_integration = new_integration
            print("✅ Replaced MusicBrainz integration")
            
        if hasattr(main_instance, 'musicbrainz_integration'):
            main_instance.musicbrainz_integration = new_integration
            print("✅ Replaced MusicBrainz integration (alt name)")
        
        if hasattr(main_instance, 'spotify_integration'):
            # Keep reference for any Spotify-specific calls, but route search through new system
            old_spotify = main_instance.spotify_integration
            main_instance.spotify_integration = new_integration
            # Store old one as backup if needed
            main_instance._old_spotify_integration = old_spotify
            print("✅ Replaced Spotify integration")
        
        print("🎉 Integration replacement complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error replacing integrations: {e}")
        return False

# Simple test function
def test_replacement():
    """Test the replacement system."""
    print("🧪 Testing simplified integration...")
    
    integration = SimplifiedMetadataIntegration()
    
    # Test the problem case
    result = integration.search_metadata("Kendrick Lamar", "DNA.")
    
    if result and result.get('album') == 'DAMN.':
        print("✅ Integration replacement working correctly!")
        print(f"Found: {result}")
        return True
    else:
        print("❌ Integration replacement failed")
        print(f"Result: {result}")
        return False

if __name__ == "__main__":
    test_replacement()