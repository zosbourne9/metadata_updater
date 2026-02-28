#!/usr/bin/env python3
"""
Test script to read metadata from audio files and compare with filename.
This will help debug why "Snoop Dogg" is being extracted instead of "112".
"""

import os
import sys
from pathlib import Path

def read_file_metadata(file_path):
    """Read metadata from audio file using multiple methods."""
    print(f"🎵 ANALYZING FILE: {os.path.basename(file_path)}")
    print("=" * 80)
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    # Show filename breakdown
    filename = os.path.basename(file_path)
    filename_no_ext = os.path.splitext(filename)[0]
    
    print(f"📁 Full path: {file_path}")
    print(f"📄 Filename: {filename}")
    print(f"📝 Name without extension: {filename_no_ext}")
    
    # Try to parse artist/title from filename
    if " - " in filename_no_ext:
        parts = filename_no_ext.split(" - ", 1)
        filename_artist = parts[0].strip()
        filename_title = parts[1].strip()
        print(f"🔍 Parsed from filename:")
        print(f"   Artist: '{filename_artist}'")
        print(f"   Title: '{filename_title}'")
    else:
        print("🔍 Could not parse artist - title from filename")
    
    print("\n" + "─" * 80)
    
    # Method 1: Using mutagen (most reliable)
    try:
        from mutagen import File
        from mutagen.id3 import ID3NoHeaderError
        
        print("🔧 METHOD 1: Using mutagen")
        audio_file = File(file_path)
        
        if audio_file is None:
            print("❌ Mutagen could not read the file")
        else:
            print(f"📊 File type: {audio_file.mime[0] if audio_file.mime else 'Unknown'}")
            print(f"📊 File info: {type(audio_file).__name__}")
            
            # Print all available tags
            print("📋 All metadata tags:")
            if hasattr(audio_file, 'tags') and audio_file.tags:
                for key, value in audio_file.tags.items():
                    if isinstance(value, list) and len(value) == 1:
                        value = value[0]
                    print(f"   {key}: {value}")
            else:
                print("   No tags found")
            
            # Extract common fields
            fields_to_check = {
                'title': ['TIT2', 'TITLE', '\xa9nam', 'Title'],
                'artist': ['TPE1', 'ARTIST', '\xa9ART', 'Artist'],
                'album': ['TALB', 'ALBUM', '\xa9alb', 'Album'],
                'date': ['TDRC', 'DATE', '\xa9day', 'Date'],
                'year': ['TYER', 'YEAR', 'Year']
            }
            
            print("\n📝 Extracted common fields:")
            for field_name, possible_keys in fields_to_check.items():
                value = None
                found_key = None
                
                for key in possible_keys:
                    if hasattr(audio_file, 'tags') and audio_file.tags and key in audio_file.tags:
                        value = audio_file.tags[key]
                        if isinstance(value, list) and len(value) > 0:
                            value = value[0]
                        found_key = key
                        break
                
                if value:
                    print(f"   {field_name.capitalize()}: '{value}' (from {found_key})")
                else:
                    print(f"   {field_name.capitalize()}: Not found")
    
    except ImportError:
        print("❌ Mutagen not available")
    except Exception as e:
        print(f"❌ Error with mutagen: {e}")
    
    print("\n" + "─" * 80)
    
    # Method 2: Using eyed3 (if available)
    try:
        import eyed3
        
        print("🔧 METHOD 2: Using eyed3")
        audio_file = eyed3.load(file_path)
        
        if audio_file is None or audio_file.tag is None:
            print("❌ eyed3 could not read tags")
        else:
            print("📝 eyed3 extracted fields:")
            print(f"   Artist: '{audio_file.tag.artist}'")
            print(f"   Title: '{audio_file.tag.title}'")
            print(f"   Album: '{audio_file.tag.album}'")
            print(f"   Date: '{audio_file.tag.getBestDate()}'")
            print(f"   Genre: '{audio_file.tag.genre}'")
    
    except ImportError:
        print("⚠️  eyed3 not available")
    except Exception as e:
        print(f"❌ Error with eyed3: {e}")
    
    print("\n" + "─" * 80)
    
    # Method 3: Using the application's own utility
    try:
        sys.path.insert(0, '/Users/djzrex/Documents/GitHub/metadata_updater')
        from hf_llm_utils import HFLLMUtilities
        
        print("🔧 METHOD 3: Using application's HFLLMUtilities")
        
        # Load audio with mutagen like the app does
        from mutagen import File
        audio = File(file_path)
        
        if audio is None:
            print("❌ Could not load audio file")
        else:
            utils = HFLLMUtilities()
            artist, title = utils.get_artist_and_title_from_audio(audio, file_path)
            
            print("📝 Application extracted fields:")
            print(f"   Artist: '{artist}'")
            print(f"   Title: '{title}'")
            
            # Also try the individual extraction methods
            try:
                extracted_artist = utils.extract_artist_from_audio(audio)
                extracted_title = utils.extract_title_from_audio(audio, file_path)
                
                print("📝 Individual extraction methods:")
                print(f"   extract_artist_from_audio(): '{extracted_artist}'")
                print(f"   extract_title_from_audio(): '{extracted_title}'")
            except Exception as e:
                print(f"⚠️  Individual extraction failed: {e}")
    
    except ImportError as e:
        print(f"⚠️  Application utilities not available: {e}")
    except Exception as e:
        print(f"❌ Error with application utilities: {e}")
    
    print("\n" + "=" * 80)
    return True

def main():
    """Main function to test metadata reading."""
    print("🎵 AUDIO METADATA READER TEST")
    print("=" * 80)
    
    # Check if file path provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if not read_file_metadata(file_path):
            return
    else:
        # Prompt for file path
        file_path = input("Enter the full path to your audio file: ").strip()
        if not file_path:
            print("❌ No file path provided")
            return
        
        # Remove quotes if present
        file_path = file_path.strip('"\'')
        
        if not read_file_metadata(file_path):
            return
    
    print("\n🎯 SUMMARY:")
    print("This shows exactly what metadata is stored in your file vs. what the filename suggests.")
    print("If 'Snoop Dogg' appears in the metadata tags but the filename says '112',")
    print("then the file has been previously tagged incorrectly.")

if __name__ == "__main__":
    main()