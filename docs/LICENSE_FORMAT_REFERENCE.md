# License Key Format Reference

Quick reference for understanding and debugging license keys.

## Format Overview

```
MDUX_[JWT TOKEN]
```

### Example Full License Key
```
MDUX_eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2VtYWlsIjoiam9obkBleGFtcGxlLmNvbSIsImlzc3VlZCI6IjIwMjUtMDQtMTlUMTY6NDQ6MTkuMTM3NDA1KzAwOjAwIiwiZXhwaXJlcyI6IjIwMjYtMDQtMTlUMTY6NDQ6MTkuMTM3NDA1KzAwOjAwIiwiYXBwX3ZlcnNpb24iOiIxLjAiLCJmZWF0dXJlcyI6WyJtZXRhZGF0YV91cGRhdGUiLCJnZW5yZV9kZXRlY3Rpb24iXX0.BgiFEvjtwqcDLpoQh7rihZ_arlGaHRAoNT7P_fhzsJ6nB96rYpkEFVpCbNWsdivPqHqt3L7pd5cqz89uqhQwVn97ySYai8cbePWXbWYU30KDztdOiGHu26LMmSwXpUItmzzokPNvhWt5l172OmVUK3R3UyfIxWG0BMf_jsz_nD455mJVRotFFD-ARcQfLh9CiY7-DHRgmDWeywTp92woS50aiSJ0UJ5QimxUdMJ0Prj6Bdl_HHMhDu8PsVc7nxN3EdCPMianSt5NHYgvfdMkshhV0TeD3LyCsDowiw3mZ2c8ZfVOK8iA8jIc-WpVyuqHG9K6mDON2R5OLs9G4UDJOg
```

## Structure

### Prefix: `MDUX_`
- Identifies this as a Metadata Updater license
- Always exactly 5 characters
- Required for app to recognize as valid format

### JWT Token (after `MDUX_`)
Split into three parts by dots (`.`):

```
HEADER.PAYLOAD.SIGNATURE
```

### HEADER
```json
{
  "alg": "RS256",    // Algorithm: RSA 256-bit
  "typ": "JWT"       // Type: JSON Web Token
}
```

Encoded as Base64URL.

### PAYLOAD
```json
{
  "user_email": "john@example.com",
  "issued": "2025-04-19T16:44:19.137405+00:00",
  "expires": "2026-04-19T16:44:19.137405+00:00",
  "app_version": "1.0",
  "features": [
    "metadata_update",
    "genre_detection"
  ]
}
```

Key fields:
- **user_email**: License holder's email
- **issued**: When license was created
- **expires**: When license stops working (365 days later)
- **app_version**: Minimum app version required
- **features**: What user can do

Encoded as Base64URL.

### SIGNATURE
- **Algorithm**: RS256 (RSA with SHA-256)
- **Computation**: `HMACSHA256(Base64URL(HEADER) + "." + Base64URL(PAYLOAD), PRIVATE_KEY)`
- **Purpose**: Proves token hasn't been tampered with
- **Cannot forge without**: Private key (stored only in n8n)

Encoded as Base64URL.

## Key Properties

| Property | Value |
|----------|-------|
| **Total Length** | ~650-700 characters |
| **Prefix Length** | 5 chars (`MDUX_`) |
| **Token Length** | 645-695 chars |
| **Valid Period** | 365 days from issue |
| **After Expiry** | Automatically rejected |
| **Signature** | Cannot be forged |
| **Shareable** | Technically yes, but tied to email |

## Validation Checklist

### When validating a license key:

✅ **Format Check**
- Starts with `MDUX_`
- Followed by valid JWT

✅ **Structure Check**
- Has exactly 3 parts (header.payload.signature)
- Each part is valid Base64URL

✅ **Signature Check**
- Signature verifies using public key
- No tampering detected

✅ **Expiration Check**
- Current date < expires date
- License not yet expired

✅ **Payload Check**
- Contains all required fields
- Email is valid format
- Features list is present

## Decoding (for debugging)

### Manual Decoding

1. Remove `MDUX_` prefix
2. Extract middle part (between dots)
3. Add padding if needed: `var padding = 4 - (payload.length % 4); payload += "=".repeat(padding);`
4. Base64 decode

### Online Decoder
- JWT.io: https://jwt.io (paste full token)
- ⚠️ WARNING: Only use for testing, never paste real production tokens

### Python Decoding (safe, local)
```python
import jwt
from pathlib import Path

# Load public key
with open('config/license_public.pem') as f:
    public_key = f.read()

# Token without MDUX_ prefix
token = "eyJhbGci..."

# Decode and verify
try:
    payload = jwt.decode(token, public_key, algorithms=['RS256'])
    print("✓ Valid token")
    print(f"User: {payload['user_email']}")
    print(f"Expires: {payload['expires']}")
except jwt.InvalidSignatureError:
    print("✗ Invalid signature (token was tampered with)")
except jwt.ExpiredSignatureError:
    print("✗ Token expired")
except Exception as e:
    print(f"✗ Error: {e}")
```

## Error Messages You'll See

| Message | Meaning | Solution |
|---------|---------|----------|
| "Invalid license format (must start with MDUX_)" | Missing prefix | Regenerate from n8n |
| "License has expired" | Past expiration date | Get new license |
| "Invalid license signature" | Token was modified | Don't modify token |
| "Invalid license format" | Malformed JWT | Copy full token carefully |
| "License validation unavailable" | Public key missing | Reinstall app |

## Examples

### Valid License (In Progress)
```
MDUX_eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2VtYWlsIjoicGF0aUBleGFtcGxlLmNvbSIsImV4cGlyZXMiOiIyMDI2LTA1LTI1VDAwOjAwOjAwWiJ9.SIGNATURE_HASH...
```
Result: ✅ Licensed

### Expired License
```
MDUX_eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2VtYWlsIjoibWlrZUBleGFtcGxlLmNvbSIsImV4cGlyZXMiOiIyMDI0LTA1LTI1VDAwOjAwOjAwWiJ9.SIGNATURE_HASH...
```
Result: ❌ "License expired on 2024-05-25"

### Invalid Signature
```
MDUX_eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2VtYWlsIjoiam9obkBleGFtcGxlLmNvbSJ9.INVALID_SIGNATURE_HASH
```
Result: ❌ "Invalid license signature (key may be corrupted)"

### Missing Prefix
```
eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2VtYWlsIjoiamFuZUBleGFtcGxlLmNvbSJ9.SIGNATURE_HASH
```
Result: ❌ "Invalid license format (must start with MDUX_)"

## Features Per License

All generated licenses currently include:

```json
{
  "features": [
    "metadata_update",      // Can update MP3/M4A metadata
    "genre_detection"       // Can use AI genre detection
  ]
}
```

Future versions may support:
- `"api_access"` - Can use REST API
- `"batch_processing"` - Unlimited file processing
- `"custom_genres"` - Upload custom genre mapping

## Expiration Timeline

### At Generation
```
Issued: 2025-04-19 12:00:00
Expires: 2026-04-19 12:00:00
Valid: ✅
```

### 364 days later
```
Current: 2026-04-18 23:59:59
Expires: 2026-04-19 12:00:00
Valid: ✅ (11 hours left)
```

### At expiration
```
Current: 2026-04-19 12:00:01
Expires: 2026-04-19 12:00:00
Valid: ❌ (expired)
```

## For Support/Debugging

When a user reports license issues, ask for:

1. **Full license key** (example: `MDUX_eyJ...`)
2. **Email address** used to generate it
3. **When they received it**
4. **Error message** they're seeing

Then you can:
- Decode on jwt.io to verify dates
- Check in n8n execution history
- Regenerate if needed

---

**Remember**: Never share this reference with real license keys. Treat keys like passwords!
