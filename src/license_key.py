"""
License management module - handles signed JWT token validation.
Supports Phase 2: JWT-based licensing with automatic expiration.
"""

import json
import jwt
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, Dict, Optional


class LicenseManager:
    def __init__(self):
        self._home_dir = Path.home()
        self._license_file = self._home_dir / '.metadata_updater_license'
        self._project_root = Path(__file__).parent.parent

        # Resolve the public key via the shared resource helper so it works
        # both in development and inside the PyInstaller bundle (sys._MEIPASS).
        try:
            from resource_path import get_resource_path
            self._public_key_path = Path(get_resource_path('config/license_public.pem'))
        except Exception:
            self._public_key_path = self._project_root / 'config' / 'license_public.pem'
        
        self.max_free_files = 10  # Free version limited to 10 files
        self.processed_files_count = 0
        self.current_license = None
        self.public_key = None
        
        # Load public key for JWT verification
        self._load_public_key()
        
        # Load existing license
        self.load_license()

    def _load_public_key(self):
        """Load RSA public key from config directory."""
        try:
            if self._public_key_path.exists():
                self.public_key = self._public_key_path.read_text()
                print(f"✓ Public key loaded from {self._public_key_path}")
            else:
                print(f"⚠ Public key not found at {self._public_key_path}")
                self.public_key = None
        except Exception as e:
            print(f"Error loading public key: {e}")
            self.public_key = None

    def validate_key(self, key: str) -> Tuple[bool, str]:
        """
        Validate a license key (JWT token format: MDUX_{jwt_token})
        Returns tuple of (is_valid, message)
        """
        if not key:
            return False, "No license key provided"
        
        if not self.public_key:
            return False, "License validation unavailable (public key missing)"
        
        try:
            # Check format
            if not key.startswith('MDUX_'):
                return False, "Invalid license format (must start with MDUX_)"
            
            # Extract JWT portion
            jwt_token = key[5:]  # Remove "MDUX_" prefix
            
            # Verify JWT signature
            payload = jwt.decode(jwt_token, self.public_key, algorithms=['RS256'])
            
            # Check expiration
            expires_str = payload.get('expires')
            if not expires_str:
                return False, "Invalid license (missing expiration)"
            
            expires = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            
            if now > expires:
                return False, f"License expired on {expires.strftime('%Y-%m-%d')}"
            
            # Check required fields
            required_fields = ['user_email', 'issued', 'expires', 'app_version']
            for field in required_fields:
                if field not in payload:
                    return False, f"Invalid license (missing {field})"
            
            # Save valid license
            self.save_license(key, payload)
            
            days_left = (expires - now).days
            return True, f"✓ License valid! Expires in {days_left} days ({expires.strftime('%Y-%m-%d')})"
        
        except jwt.ExpiredSignatureError:
            return False, "License has expired"
        except jwt.InvalidSignatureError:
            return False, "Invalid license signature (key may be corrupted)"
        except jwt.DecodeError as e:
            return False, f"Invalid license format: {str(e)}"
        except Exception as e:
            return False, f"License validation error: {str(e)}"

    @property
    def home_dir(self):
        """Return home directory as string for API serialization."""
        return str(self._home_dir)

    @property
    def license_file(self):
        """Return license file path as string for API serialization."""
        return str(self._license_file)

    def load_license(self) -> Optional[Dict]:
        """Load and validate license from file."""
        try:
            if self._license_file.exists():
                license_data = json.loads(self._license_file.read_text())
                stored_key = license_data.get('key')
                
                if not stored_key:
                    print("Invalid license file (no key)")
                    self.current_license = None
                    return None
                
                # Validate the stored key
                is_valid, message = self.validate_key(stored_key)
                
                if is_valid:
                    # Restore processed files count from disk
                    self.processed_files_count = license_data.get('processed_files', 0)
                    self.current_license = license_data
                    print(f"✓ Valid license loaded: {license_data.get('user_email')}")
                    return license_data
                else:
                    print(f"Invalid license: {message}")
                    self.current_license = None
                    return None
            
        except Exception as e:
            print(f"Error loading license: {e}")
            self.current_license = None
        
        return None

    def save_license(self, key: str, payload: Dict = None) -> None:
        """Save license information to file."""
        try:
            license_data = {
                'key': key,
                'processed_files': self.processed_files_count,
                'user_email': payload.get('user_email') if payload else 'unknown',
                'activated': datetime.now(timezone.utc).isoformat(),
            }
            
            if payload:
                license_data['expires'] = payload.get('expires')
                license_data['features'] = payload.get('features', [])
            
            self._license_file.write_text(json.dumps(license_data, indent=2))
            self.current_license = license_data
            print(f"✓ License saved: {license_data.get('user_email')}")
        
        except Exception as e:
            print(f"Error saving license: {e}")

    def is_licensed(self) -> bool:
        """Check if app has valid, non-expired license."""
        if not self.current_license:
            return False
        
        try:
            key = self.current_license.get('key')
            if not key:
                return False
            
            # Validate the key (checks expiration, signature, etc.)
            is_valid, _ = self.validate_key(key)
            return is_valid
        
        except Exception:
            return False

    def can_process_files(self, num_files: int = 1) -> Tuple[bool, str]:
        """
        Check if files can be processed based on license status.
        Returns tuple of (can_process, message)
        
        Licensed version: Unlimited
        Free version: Limited to 10 files
        """
        if self.is_licensed():
            license_info = self.current_license or {}
            user_email = license_info.get('user_email', 'User')
            return True, f"✓ Licensed ({user_email}) - Unlimited file processing"

        # Free version has 10-file limit
        files_after = self.processed_files_count + num_files
        if files_after > self.max_free_files:
            return False, f"Free version limited to {self.max_free_files} files. Please enter a license key to process more files."

        remaining = self.max_free_files - self.processed_files_count
        return True, f"✓ Free version - {remaining} files remaining"

    def increment_processed_files(self, count: int = 1) -> None:
        """Increment the processed files counter and save immediately."""
        self.processed_files_count += count
        
        # Save the updated count
        if self.current_license:
            key = self.current_license.get('key')
            if key:
                self.save_license(key)
        else:
            # Save count for free version
            license_data = {
                'key': None,
                'processed_files': self.processed_files_count,
                'activated': datetime.now(timezone.utc).isoformat(),
            }
            self._license_file.write_text(json.dumps(license_data))
            self.current_license = license_data

    def reset_processed_files(self) -> None:
        """Reset the processed files counter."""
        self.processed_files_count = 0
        if self.current_license and self.current_license.get('key'):
            self.save_license(self.current_license['key'])
        else:
            # Clear the license file if it exists
            if self._license_file.exists():
                self._license_file.unlink()
            self.current_license = None

    def get_remaining_files(self) -> float:
        """
        Get number of remaining files.
        Licensed: unlimited (infinity)
        Free: up to 10 files
        """
        if self.is_licensed():
            return float('inf')  # Unlimited for licensed version
        return max(0, self.max_free_files - self.processed_files_count)

    def get_license_status(self) -> Dict:
        """Get license status for UI display."""
        if self.is_licensed():
            license_info = self.current_license or {}
            try:
                expires_str = license_info.get('expires', '')
                if expires_str:
                    expires = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    days_left = (expires - now).days
                else:
                    days_left = None
            except:
                days_left = None
            
            return {
                'licensed': True,
                'user_email': license_info.get('user_email', 'Unknown'),
                'expires': license_info.get('expires'),
                'days_left': days_left,
                'processed_files': self.processed_files_count,
                'remaining_files': float('inf'),
                'features': license_info.get('features', [])
            }
        else:
            return {
                'licensed': False,
                'processed_files': self.processed_files_count,
                'remaining_files': max(0, self.max_free_files - self.processed_files_count),
                'max_free_files': self.max_free_files
            }
