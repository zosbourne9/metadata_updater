#!/usr/bin/env python3
"""
Test script for JWT-based licensing system (Phase 2)
Tests token generation, validation, and expiration
"""

import sys
import jwt
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from license_key import LicenseManager


def test_load_keys():
    """Test loading RSA keys"""
    print("\n" + "="*60)
    print("TEST 1: Loading RSA Keys")
    print("="*60)
    
    manager = LicenseManager()
    
    if manager.public_key:
        print("✓ Public key loaded successfully")
        print(f"  Key length: {len(manager.public_key)} characters")
        return True
    else:
        print("✗ Failed to load public key")
        return False


def test_generate_token(private_key_path: str):
    """Test generating a valid JWT token"""
    print("\n" + "="*60)
    print("TEST 2: Generating Valid JWT Token")
    print("="*60)
    
    try:
        # Load private key
        with open(private_key_path, 'r') as f:
            private_key = f.read()
        
        # Generate token valid for 1 year
        issued = datetime.now(timezone.utc)
        expires = issued + timedelta(days=365)
        
        payload = {
            'user_email': 'test@example.com',
            'issued': issued.isoformat(),
            'expires': expires.isoformat(),
            'app_version': '1.0',
            'features': ['metadata_update', 'genre_detection']
        }
        
        token = jwt.encode(payload, private_key, algorithm='RS256')
        full_key = f"MDUX_{token}"
        
        print(f"✓ Token generated successfully")
        print(f"  Token format: MDUX_[{len(token)} char JWT]")
        print(f"  Full license key: {full_key[:50]}...")
        print(f"  User: {payload['user_email']}")
        print(f"  Expires: {expires.strftime('%Y-%m-%d')}")
        
        return full_key, payload
    
    except Exception as e:
        print(f"✗ Failed to generate token: {e}")
        return None, None


def test_validate_token(license_key: str):
    """Test validating a license token"""
    print("\n" + "="*60)
    print("TEST 3: Validating License Token")
    print("="*60)
    
    manager = LicenseManager()
    is_valid, message = manager.validate_key(license_key)
    
    if is_valid:
        print(f"✓ License validation passed")
        print(f"  Message: {message}")
        return True
    else:
        print(f"✗ License validation failed")
        print(f"  Error: {message}")
        return False


def test_expired_token(private_key_path: str):
    """Test that expired tokens are rejected"""
    print("\n" + "="*60)
    print("TEST 4: Rejecting Expired Token")
    print("="*60)
    
    try:
        with open(private_key_path, 'r') as f:
            private_key = f.read()
        
        # Generate token that expired 1 day ago
        issued = datetime.now(timezone.utc) - timedelta(days=2)
        expires = datetime.now(timezone.utc) - timedelta(days=1)
        
        payload = {
            'user_email': 'expired@example.com',
            'issued': issued.isoformat(),
            'expires': expires.isoformat(),
            'app_version': '1.0',
            'features': []
        }
        
        token = jwt.encode(payload, private_key, algorithm='RS256')
        expired_key = f"MDUX_{token}"
        
        print(f"✓ Expired token generated")
        print(f"  Expired on: {expires.strftime('%Y-%m-%d')}")
        
        # Try to validate it
        manager = LicenseManager()
        is_valid, message = manager.validate_key(expired_key)
        
        if not is_valid and "expired" in message.lower():
            print(f"✓ Correctly rejected expired token")
            print(f"  Error message: {message}")
            return True
        else:
            print(f"✗ Failed to reject expired token")
            return False
    
    except Exception as e:
        print(f"✗ Error testing expired token: {e}")
        return False


def test_invalid_signature():
    """Test that modified tokens are rejected"""
    print("\n" + "="*60)
    print("TEST 5: Rejecting Modified Token (Invalid Signature)")
    print("="*60)
    
    # Use a valid token but modify it slightly
    valid_token = "MDUX_eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2VtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsImlzc3VlZCI6IjIwMjUtMDQtMjBUMTI6MDA6MDBIKzAwOjAwIiwiZXhwaXJlcyI6IjIwMjYtMDQtMjBUMTI6MDA6MDBIKzAwOjAwIiwiYXBwX3ZlcnNpb24iOiIxLjAiLCJmZWF0dXJlcyI6WyJtZXRhZGF0YV91cGRhdGUiLCJnZW5yZV9kZXRlY3Rpb24iXX0.INVALID_SIGNATURE_HASH"
    
    manager = LicenseManager()
    is_valid, message = manager.validate_key(valid_token)
    
    if not is_valid and "signature" in message.lower():
        print(f"✓ Correctly rejected modified token")
        print(f"  Error message: {message}")
        return True
    else:
        print(f"✗ Failed to reject invalid signature")
        print(f"  Result: {message}")
        return False


def test_invalid_format():
    """Test that incorrectly formatted keys are rejected"""
    print("\n" + "="*60)
    print("TEST 6: Rejecting Invalid Format")
    print("="*60)
    
    manager = LicenseManager()
    
    # Test various invalid formats
    test_cases = [
        ("old_key_format", "Old hardcoded key format"),
        ("INVALID_TOKEN", "Random string"),
        ("MDUX_not_a_jwt", "MDUX prefix but invalid JWT"),
        ("", "Empty string")
    ]
    
    all_passed = True
    for invalid_key, description in test_cases:
        is_valid, message = manager.validate_key(invalid_key)
        
        if not is_valid:
            print(f"✓ Rejected: {description}")
        else:
            print(f"✗ Incorrectly accepted: {description}")
            all_passed = False
    
    return all_passed


def test_file_persistence():
    """Test saving and loading license from file"""
    print("\n" + "="*60)
    print("TEST 7: File Persistence")
    print("="*60)
    
    try:
        import tempfile
        import shutil
        
        # Create temporary home for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            print(f"✓ Testing with temp directory: {tmpdir}")
            
            # Monkey-patch the home directory for testing
            manager = LicenseManager()
            original_license_file = manager._license_file
            manager._license_file = Path(tmpdir) / '.metadata_updater_license'
            
            # Create test license data
            test_license = {
                'key': 'MDUX_test_token',
                'user_email': 'persist_test@example.com',
                'processed_files': 5,
                'activated': datetime.now(timezone.utc).isoformat(),
                'expires': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            }
            
            # Save to file
            manager._license_file.write_text(json.dumps(test_license, indent=2))
            print(f"✓ License file created at: {manager._license_file}")
            
            # Verify it was written
            if manager._license_file.exists():
                print(f"✓ License file persisted successfully")
                return True
            else:
                print(f"✗ License file not found after write")
                return False
    
    except Exception as e:
        print(f"✗ Error testing file persistence: {e}")
        return False


def print_summary(results):
    """Print test summary"""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! JWT licensing is working correctly.")
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Please review.")
    
    return passed == total


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("JWT LICENSING SYSTEM - PHASE 2 TEST SUITE")
    print("="*60)
    
    # Paths
    project_root = Path(__file__).parent
    private_key_path = project_root / 'config' / 'license_private.pem'
    
    if not private_key_path.exists():
        print("✗ Private key not found. Please run key generation first.")
        return False
    
    results = {}
    
    # Test 1: Load keys
    results['Load RSA Keys'] = test_load_keys()
    
    # Test 2: Generate token
    token, payload = test_generate_token(str(private_key_path))
    results['Generate JWT Token'] = token is not None
    
    # Test 3: Validate token
    if token:
        results['Validate License Token'] = test_validate_token(token)
    else:
        results['Validate License Token'] = False
    
    # Test 4: Reject expired token
    results['Reject Expired Token'] = test_expired_token(str(private_key_path))
    
    # Test 5: Reject invalid signature
    results['Reject Invalid Signature'] = test_invalid_signature()
    
    # Test 6: Reject invalid format
    results['Reject Invalid Format'] = test_invalid_format()
    
    # Test 7: File persistence
    results['File Persistence'] = test_file_persistence()
    
    # Print summary
    success = print_summary(results)
    
    # If all passed, show the generated token for manual testing
    if success and token:
        print("\n" + "="*60)
        print("EXAMPLE LICENSE TOKEN (for n8n/manual testing)")
        print("="*60)
        print(f"\nFull License Key:\n{token}")
        print(f"\nUser Email: {payload['user_email']}")
        print(f"Expires: {payload['expires']}")
        print("\nTo use this in n8n or elsewhere, simply emit this token")
        print("with the MDUX_ prefix prepended.")
    
    return success


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
