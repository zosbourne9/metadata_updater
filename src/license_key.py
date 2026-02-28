"""
License management module - handles license validation and file processing limits.
PyQt6 UI components (LicenseDialog, LicenseBanner) have been removed and migrated to HTML/JavaScript.
"""

import json
from pathlib import Path
from datetime import datetime, timezone


class LicenseManager:
    def __init__(self):
        self._home_dir = Path.home()
        self._license_file = self._home_dir / '.metadata_updater_license'
        self.max_free_files = 10
        self.processed_files_count = 0  # Initialize counter first
        self.current_license = None  # Initialize license to None first
        
        # Valid license keys
        self.valid_keys = {
            "MDUX-2024-PRO1-K8N9",
            "MDUX-2024-PRO2-M5L7",
            "MDUX-2024-PRO3-P2Q4",
            "MDUX-2024-PRO4-R6T8",
            "MDUX-2024-PRO5-W3X5",
            "MDUX-2024-PRO6-Y9Z1",
            "MDUX-2024-PRO7-B4C6",
            "MDUX-2024-PRO8-F7H9",
            "MDUX-2024-PRO9-J2K4",
            "MDUX-2024-P10A-N5P7",
            "MDUX-2024-P11B-Q8R1",
            "MDUX-2024-P12C-T3V5",
            "MDUX-2024-P13D-W6X8",
            "MDUX-2024-P14E-Y1Z3",
            "MDUX-2024-P15F-B4C6",
            "MDUX-2024-P16G-H7J9",
            "MDUX-2024-P17H-K2L4",
            "MDUX-2024-P18I-M5N7",
            "MDUX-2024-P19J-P8Q1",
            "MDUX-2024-P20K-R3T5"
        }
        
        # Load existing license and count after initializing attributes
        self.load_license()

    def validate_key(self, key):
        """
        Validate a license key.
        Returns tuple of (is_valid, message)
        """
        if not key:
            return False, "No license key provided"
            
        # Check if key is in valid keys set
        if key in self.valid_keys:
            # Save valid license
            self.save_license(key)
            return True, "License key validated successfully!"
        
        return False, "Invalid license key"

    @property
    def home_dir(self):
        """Return home directory as string for API serialization."""
        return str(self._home_dir)

    @property
    def license_file(self):
        """Return license file path as string for API serialization."""
        return str(self._license_file)

    def load_license(self):
        """Load license information from file - no expiration"""
        try:
            if self._license_file.exists():
                license_data = json.loads(self._license_file.read_text())
                
                # Simply check if the key exists in our valid keys
                if license_data.get('key') in self.valid_keys:
                    self.current_license = license_data
                    self.processed_files_count = license_data.get('processed_files', 0)
                    print("Valid license loaded successfully")
                    return license_data
                else:
                    print("Invalid license found")
                    self.current_license = None
                    
        except Exception as e:
            print(f"Error loading license: {e}")
            self.current_license = None
        return None
     
    def save_license(self, key):
        """Save license information to file - no expiration"""
        try:
            license_data = {
                'key': key,
                'processed_files': self.processed_files_count
            }
            
            self._license_file.write_text(json.dumps(license_data, indent=2))
            self.current_license = license_data
            print(f"License saved successfully: {key}")
            
        except Exception as e:
            print(f"Error saving license: {e}")

    def is_licensed(self):
        """Check if app is licensed"""
        return (self.current_license is not None and 
                self.current_license.get('key') in self.valid_keys)

    def can_process_files(self, num_files=1):
        """
        Check if files can be processed based on license status
        Returns tuple of (can_process, message)
        """
        if self.is_licensed():
            return True, "Licensed version"
            
        files_after = self.processed_files_count + num_files
        if files_after > self.max_free_files:
            return False, f"Free version limited to {self.max_free_files} files. Please enter a license key to process more files."
            
        return True, f"Free version - {self.max_free_files - self.processed_files_count} files remaining"

    def increment_processed_files(self, count=1):
        """Increment the processed files counter and save immediately"""
        self.processed_files_count += count
        
        # Save the updated count
        if self.current_license:
            self.save_license(self.current_license['key'])
        else:
            # Save a temporary license data just to track the count
            license_data = {
                'key': None,
                'activation_date': datetime.now(timezone.utc).isoformat(),
                'processed_files': self.processed_files_count
            }
            self._license_file.write_text(json.dumps(license_data))
            self.current_license = license_data

    def reset_processed_files(self):
        """Reset the processed files counter and save"""
        self.processed_files_count = 0
        if self.current_license:
            self.save_license(self.current_license['key'])
        else:
            # Clear the license file if it exists
            if self.license_file.exists():
                self.license_file.unlink()
            self.current_license = None
                 
    def get_remaining_files(self):
        """Get number of remaining files in free version"""
        if self.is_licensed():
            return float('inf')  # Unlimited for licensed version
        return max(0, self.max_free_files - self.processed_files_count)
