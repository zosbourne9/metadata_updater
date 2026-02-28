#!/usr/bin/env python3
"""
Test script for the simplified metadata searcher.
Run this to test the new implementation before integrating it.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simplified_metadata_searcher import SimplifiedMetadataSearcher
from artist_normalizer import ArtistNormalizer

def test_search(artist, title):
    """Test a single search."""
    print(f"\n{'='*60}")
    print(f"Testing: {artist} - {title}")
    print('='*60)
    
    # Create searcher (no cache for testing)
    searcher = SimplifiedMetadataSearcher(cache_manager=None)
    
    # Test the search
    result = searcher.search_metadata(artist, title)
    
    if result:
        print(f"\n✅ SUCCESS!")
        print(f"Title: {result.get('title', 'N/A')}")
        print(f"Artist: {result.get('artist', 'N/A')}")
        print(f"Album: {result.get('album', 'N/A')}")
        print(f"Year: {result.get('year', 'N/A')}")
        print(f"Genre: {result.get('genre', 'N/A')}")
        print(f"Comments: {result.get('comments', 'N/A')}")
        if result.get('spotify_id'):
            print(f"Spotify ID: {result['spotify_id']}")
    else:
        print(f"\n❌ NO RESULTS FOUND")

def test_connections():
    """Test API connections."""
    print("\n" + "="*60)
    print("TESTING API CONNECTIONS")
    print("="*60)
    
    searcher = SimplifiedMetadataSearcher(cache_manager=None)
    results = searcher.test_connections()
    
    print(f"MusicBrainz: {'✅ Connected' if results['musicbrainz'] else '❌ Failed'}")
    print(f"Spotify: {'✅ Connected' if results['spotify'] else '❌ Failed'}")

def test_artist_normalization():
    """Test the artist normalization logic."""
    print("\n" + "="*60)
    print("TESTING ARTIST NORMALIZATION")
    print("="*60)

    normalizer = ArtistNormalizer()
    test_cases = {
        "Brandy · Chris Brown": "brandy",
        "Brandy ft. Chris Brown": "brandy",
        "Brandy featuring Chris Brown": "brandy",
        "Brandy with Chris Brown": "brandy",
        "Hall & Oates": "hall & oates",
        "Simon & Garfunkel": "simon & garfunkel",
        "Crosby, Stills & Nash": "crosby, stills & nash",
    }

    success_count = 0
    for artist, expected in test_cases.items():
        normalized_artist = normalizer.clean_artist_name(artist)
        if normalized_artist == expected:
            print(f"✅ '{artist}' -> '{normalized_artist}'")
            success_count += 1
        else:
            print(f"❌ '{artist}' -> '{normalized_artist}' (expected '{expected}')")

    print(f"\n📊 SUMMARY: {success_count}/{len(test_cases)} artist normalization tests passed")

def main():
    """Run the tests."""
    print("🚀 SIMPLIFIED METADATA SEARCHER TEST")
    
    # Test connections first
    test_connections()

    # Test artist normalization
    test_artist_normalization()
    
    # Test cases that should work well
    test_cases = [
        ("Brandy · Chris Brown", "Put It Down"),
        ("Brandy ft Chris Brown", "Put It Down"),
        ("Kendrick Lamar", "DNA."),  # The original problem case
        ("The Beatles", "Yesterday"),  # Classic song
        ("Billie Eilish", "Bad Guy"),  # Modern pop
        ("Drake", "God's Plan"),  # Hip-hop
        ("Ed Sheeran", "Shape of You"),  # Popular song
    ]
    
    print(f"\n🧪 Running {len(test_cases)} search test cases...")
    
    success_count = 0
    for artist, title in test_cases:
        try:
            searcher = SimplifiedMetadataSearcher(cache_manager=None)
            result = searcher.search_metadata(artist, title)
            
            if result and result.get('title') and result.get('artist'):
                success_count += 1
                print(f"✅ {artist} - {title}: Found")
            else:
                print(f"❌ {artist} - {title}: Not found")
                
        except Exception as e:
            print(f"💥 {artist} - {title}: Error - {e}")
    
    print(f"\n📊 SUMMARY: {success_count}/{len(test_cases)} search tests passed")
    
    if success_count > 0:
        print("\n🎉 The simplified system is working!")
        print("You can now integrate it into the main application.")
    else:
        print("\n⚠️  Issues detected. Check the error messages above.")

if __name__ == "__main__":
    main()
