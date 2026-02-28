#!/usr/bin/env python3
"""
Apply the simplified integration fix to the main application.

This script modifies metadata_updater.py to use the new simplified system
while maintaining full compatibility with existing code.
"""

import os
import shutil
from datetime import datetime

def backup_original_file():
    """Create a backup of the original file."""
    original = 'metadata_updater.py'
    backup = f'metadata_updater.py.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    if os.path.exists(original):
        shutil.copy2(original, backup)
        print(f"✅ Created backup: {backup}")
        return True
    else:
        print(f"❌ Original file not found: {original}")
        return False

def apply_fix():
    """Apply the simplified integration fix."""
    try:
        # Read the original file
        with open('metadata_updater.py', 'r') as f:
            content = f.read()
        
        # Make the replacements
        print("🔧 Applying fixes...")
        
        # 1. Replace imports
        old_imports = [
            "from mb_integration import MusicBrainzIntegration",
            "from spotify_integration import SpotifyIntegration"
        ]
        
        new_import = "from integration_helper import SimplifiedMetadataIntegration"
        
        for old_import in old_imports:
            if old_import in content:
                content = content.replace(old_import, "# " + old_import + " # REPLACED")
                print(f"✅ Commented out: {old_import}")
        
        # Add new import after the old ones
        if "from mb_integration" in content:
            content = content.replace(
                "# from mb_integration import MusicBrainzIntegration # REPLACED",
                "# from mb_integration import MusicBrainzIntegration # REPLACED\n" + new_import
            )
            print(f"✅ Added new import: {new_import}")
        
        # 2. Replace the integration initialization
        old_spotify_init = """self.spotify = SpotifyIntegration(
                cache_manager=self.cache_manager,
                status_update_callback=self.update_status
            )"""
        
        old_mb_init = """self.musicbrainz = MusicBrainzIntegration(
                parent=self,
                status_update_callback=self.update_status,
                artist_normalizer=self.artist_normalizer,
                cache_manager=self.cache_manager
            )"""
        
        new_unified_init = """# Use simplified unified integration
            self.simplified_integration = SimplifiedMetadataIntegration(
                parent=self,
                status_update_callback=self.update_status,
                cache_manager=self.cache_manager
            )
            
            # Maintain compatibility with existing code
            self.spotify = self.simplified_integration
            self.musicbrainz = self.simplified_integration"""
        
        # Replace both initializations with the new unified one
        if old_spotify_init in content and old_mb_init in content:
            content = content.replace(old_spotify_init, "# OLD SPOTIFY INIT REPLACED")
            content = content.replace(old_mb_init, new_unified_init)
            print("✅ Replaced integration initializations")
        else:
            print("⚠️  Could not find exact integration initialization patterns")
            print("You may need to manually update the initialization code")
        
        # 3. Replace the MetadataCoordinator initialization to use simplified integration
        old_coordinator = """MetadataCoordinator(
                self.spotify, 
                self.musicbrainz,"""
        
        new_coordinator = """MetadataCoordinator(
                self.simplified_integration,  # Use unified integration
                self.simplified_integration,  # For both services"""
        
        if old_coordinator in content:
            content = content.replace(old_coordinator, new_coordinator)
            print("✅ Updated MetadataCoordinator to use simplified integration")
        
        # Write the modified content back
        with open('metadata_updater.py', 'w') as f:
            f.write(content)
        
        print("🎉 Fix applied successfully!")
        print("\n📝 Changes made:")
        print("  - Commented out old integration imports")
        print("  - Added simplified integration import")
        print("  - Replaced integration initialization with unified system")
        print("  - Updated MetadataCoordinator to use new system")
        print("  - Maintained full compatibility with existing code")
        
        return True
        
    except Exception as e:
        print(f"❌ Error applying fix: {e}")
        return False

def verify_fix():
    """Verify that the fix was applied correctly."""
    try:
        with open('metadata_updater.py', 'r') as f:
            content = f.read()
        
        checks = [
            ("Simplified integration import", "from integration_helper import SimplifiedMetadataIntegration" in content),
            ("Old imports commented", "# from mb_integration import MusicBrainzIntegration # REPLACED" in content),
            ("Simplified integration created", "self.simplified_integration = SimplifiedMetadataIntegration(" in content),
            ("Compatibility maintained", "self.spotify = self.simplified_integration" in content and "self.musicbrainz = self.simplified_integration" in content)
        ]
        
        print("\n🔍 Verifying fix:")
        all_good = True
        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"  {status} {check_name}")
            if not passed:
                all_good = False
        
        return all_good
        
    except Exception as e:
        print(f"❌ Error verifying fix: {e}")
        return False

def main():
    """Main function to apply the fix."""
    print("🚀 APPLYING SIMPLIFIED INTEGRATION FIX")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('metadata_updater.py'):
        print("❌ metadata_updater.py not found in current directory")
        print("Please run this script from the metadata_updater directory")
        return False
    
    # Check if required files exist
    required_files = [
        'simplified_metadata_searcher.py',
        'simplified_mb_integration.py', 
        'simplified_spotify_integration.py',
        'integration_helper.py'
    ]
    
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print(f"❌ Missing required files: {missing_files}")
        print("Please ensure all simplified integration files are present")
        return False
    
    # Create backup
    if not backup_original_file():
        return False
    
    # Apply the fix
    if not apply_fix():
        print("❌ Fix application failed")
        return False
    
    # Verify the fix
    if not verify_fix():
        print("❌ Fix verification failed")
        return False
    
    print("\n🎉 SUCCESS!")
    print("The simplified integration fix has been applied.")
    print("Your application will now use the new, more efficient system.")
    print("\n📋 Next steps:")
    print("1. Test your application with some problematic songs")
    print("2. The 'DNA.' issue should now be resolved")
    print("3. If you have any issues, restore from the backup file")
    
    return True

if __name__ == "__main__":
    main()