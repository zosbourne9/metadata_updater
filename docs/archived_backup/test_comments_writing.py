#!/usr/bin/env python3
"""
Test script to debug comments tag writing
"""

import os
import sys
import tempfile
import shutil

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hf_llm_utils import HFLLMUtilities
from mutagen.mp3 import MP3
from mutagen.id3 import ID3NoHeaderError

def test_comments_writing():
    """Test writing comments to an MP3 file."""
    print("Testing Comments Tag Writing")
    print("=" * 40)
    
    # Create a temporary MP3 file for testing
    # We'll need to copy an existing MP3 or create a basic one
    
    # For this test, let's use a simple approach - check if there's an MP3 file we can use
    test_files = [
        "/Volumes/Main/Music/Katy Perry ft Doechii - I'M HIS, HE'S MINE (Clean).mp3"
    ]
    
    source_file = None
    for file_path in test_files:
        if os.path.exists(file_path):
            source_file = file_path
            break
    
    if not source_file:
        print("No test MP3 file found. Cannot run test.")
        return
    
    # Create a temporary copy
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
        temp_path = temp_file.name
    
    try:
        shutil.copy2(source_file, temp_path)
        print(f"Created temporary test file: {temp_path}")
        
        # Initialize HF LLM Utils
        utils = HFLLMUtilities()
        
        # Test metadata with comments
        test_metadata = {
            'title': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'genre': 'Pop',
            'year': '2024',
            'comments': 'Dance Pop, Electronic',  # This should be written to COMM tag
        }
        
        print(f"\nTest metadata: {test_metadata}")
        
        # Load the audio file
        audio = MP3(temp_path)
        # Ensure it has tags
        if audio.tags is None:
            audio.add_tags()
        
        print(f"Audio file type: {type(audio)}")
        
        # Try to set the metadata
        print("\n--- Setting Metadata ---")
        result = utils.set_metadata(audio, test_metadata)
        print(f"Set metadata result: {result}")
        
        # Read back the metadata to verify
        print("\n--- Reading Back Metadata ---")
        # Reload the file to verify the tags were saved
        audio_verify = MP3(temp_path)
        read_metadata = utils.get_metadata(audio_verify)
        print(f"Read back metadata: {read_metadata}")
        
        # Check specifically for comments
        if 'comments' in read_metadata:
            print(f"✓ Comments field found: '{read_metadata['comments']}'")
        else:
            print("✗ Comments field not found in read back metadata")
        
        # Also check the raw audio tags
        print("\n--- Raw Audio Tags ---")
        for tag_name in audio.tags.keys():
            if tag_name.startswith('COMM'):
                tag = audio.tags[tag_name]
                print(f"Found COMM tag: {tag_name} = {tag.text}")
        
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.unlink(temp_path)
            print(f"\nCleaned up temporary file: {temp_path}")


if __name__ == "__main__":
    test_comments_writing()