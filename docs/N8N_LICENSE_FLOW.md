# n8n License Generation Flow - Phase 2

This document describes the n8n workflow for generating JWT-based license tokens and preparing data for Mailchimp integration.

## Workflow Overview

```
Trigger (Manual Button) 
    ↓
Get User Input (Email)
    ↓
Validate Email Format
    ↓
Generate JWT Token
    ↓
Create Mailchimp Payload
    ↓
Output JSON
```

## Workflow Steps

### Step 1: Trigger (Manual Button)
- **Type**: Manual Trigger
- **Description**: User clicks button to generate new license
- **Output**: None (user will provide data in next step)

### Step 2: Get User Input (Email)
- **Type**: HTTP Request (POST from form/external input)
- **Input**: JSON with `email` field
- **Example Input**:
```json
{
  "email": "user@example.com"
}
```

### Step 3: Validate Email
- **Type**: Set node (validation logic)
- **Operation**: Check if email matches pattern
```javascript
// In n8n's Set node
{
  email: '{{ $json.email }}',
  isValid: '{{ /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test($json.email) }}'
}
```

### Step 3b: Email Valid? (Switch Node)
- **Type**: Switch node (conditional branching)
- **Condition**: `{{ $json.isValid === true }}`
- **Branch 1 (True)**: Route to JWT generation
- **Branch 2 (False)**: Route to error output

### Step 4: Generate Timestamps
- **Type**: Set node
- **Description**: Create issued and expiration dates
```javascript
{
  now: DateTime.now().toISO(),
  expires: DateTime.now().plus({ days: 365 }).toISO(),
  timestamp: Unix.now()
}
```

### Step 5: Build JWT Payload
- **Type**: Set node
- **Description**: Create the JWT payload object
```javascript
{
  payload: {
    user_email: '{{ $json.email }}',
    issued: '{{ $json.now }}',
    expires: '{{ $json.expires }}',
    app_version: '1.0',
    features: ['metadata_update', 'genre_detection']
  }
}
```

### Step 6: Generate JWT Token
- **Type**: Custom code node (Node.js)
- **Description**: Sign the payload with private key
- **Code**:

```javascript
// Node.js code in n8n Custom Code node
const jwt = require('jsonwebtoken');

// GET YOUR PRIVATE KEY FROM ENVIRONMENT VARIABLE
// CRITICAL: Store your private key in n8n as an environment variable
// Never hardcode it or paste it in plaintext
const privateKey = process.env.LICENSE_PRIVATE_KEY;

if (!privateKey) {
  throw new Error('LICENSE_PRIVATE_KEY environment variable not set');
}

const payload = {
  user_email: $json.email,
  issued: $json.now,
  expires: $json.expires,
  app_version: '1.0',
  features: ['metadata_update', 'genre_detection']
};

try {
  const token = jwt.sign(payload, privateKey, {
    algorithm: 'RS256',
    expiresIn: '365d'
  });
  
  return {
    license_key: `MDUX_${token}`,
    user_email: payload.user_email,
    issued: payload.issued,
    expires: payload.expires,
    features: payload.features,
    success: true
  };
} catch (error) {
  return {
    success: false,
    error: error.message
  };
}
```

### Step 7: Build Mailchimp Payload
- **Type**: Set node
- **Description**: Create the JSON structure for Mailchimp template merge variables

**Output Structure**:
```json
{
  "email_address": "user@example.com",
  "status": "subscribed",
  "merge_fields": {
    "LICENSE_KEY": "MDUX_eyJhbGc...",
    "LICENSE_EXPIRES": "2026-04-19",
    "DAYS_VALID": "365",
    "FEATURES": "Metadata Update, Genre Detection",
    "ACTIVATION_DATE": "2025-04-19T16:44:19+00:00",
    "DOWNLOAD_LINK": "https://your-domain.com/download",
    "SUPPORT_EMAIL": "support@your-domain.com"
  },
  "tags": ["license_active", "2025"],
  "marketing_permissions": {
    "marketing_consent": "opted_in"
  }
}
```

**n8n Set node code**:
```javascript
const daysValid = Math.ceil(
  (new Date($json.expires) - new Date($json.issued)) / (1000 * 60 * 60 * 24)
);

const featuresList = $json.features.map(f => {
  const capitalize = str => str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  return capitalize(f);
}).join(', ');

const expirationDate = new Date($json.expires).toISOString().split('T')[0];

return {
  email_address: $json.user_email,
  status: 'subscribed',
  merge_fields: {
    LICENSE_KEY: $json.license_key,
    LICENSE_EXPIRES: expirationDate,
    DAYS_VALID: daysValid.toString(),
    FEATURES: featuresList,
    ACTIVATION_DATE: new Date().toISOString(),
    DOWNLOAD_LINK: 'https://your-domain.com/download',
    SUPPORT_EMAIL: 'support@your-domain.com'
  },
  tags: ['license_active', new Date().getFullYear().toString()],
  marketing_permissions: {
    marketing_consent: 'opted_in'
  }
};
```

### Step 8: Final Output (Mailchimp Ready)
- **Type**: Output node or Mailchimp API Call
- **Output**: The JSON from Step 7 (ready to send to Mailchimp)

This JSON can be directly passed to a Mailchimp node to:
- Add/update contact
- Trigger email template
- Update merge fields with license info

## Configuration

### Environment Variables (in n8n)
Set these in your n8n instance via Settings → Environment Variables:

```
LICENSE_PRIVATE_KEY = -----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA7H+nERU/nJqKX98Q9E2q...
(your private key from config/license_private.pem)
-----END RSA PRIVATE KEY-----
```

**CRITICAL SECURITY NOTES**:
1. **Never** commit private key to Git
2. **Never** paste it in workflow UI - use environment variables only
3. **Only** you (and n8n service account) should have access to this key
4. Rotate key annually
5. Store backup copy offline in secure location

## Testing the Workflow

### Test Case 1: Valid Email
```json
{
  "email": "newuser@example.com"
}
```

**Expected Output**:
```json
{
  "email_address": "newuser@example.com",
  "status": "subscribed",
  "merge_fields": {
    "LICENSE_KEY": "MDUX_eyJhbGciOiJSUzI1NiIs...",
    "LICENSE_EXPIRES": "2026-04-19",
    "DAYS_VALID": "365",
    "FEATURES": "Metadata Update, Genre Detection",
    "ACTIVATION_DATE": "2025-04-19T16:44:19Z",
    "DOWNLOAD_LINK": "https://your-domain.com/download",
    "SUPPORT_EMAIL": "support@your-domain.com"
  }
}
```

### Test Case 2: Invalid Email
```json
{
  "email": "not-an-email"
}
```

**Expected Behavior**: Workflow stops with validation error

## Integration with Mailchimp

After this workflow outputs the JSON, you can connect it to a Mailchimp node:

1. **Mailchimp Node Configuration**:
   - **Resource**: Contact
   - **Operation**: Create or Update
   - **List ID**: Your Mailchimp audience ID
   - **Email Address**: `{{ $json.email_address }}`
   - **Merge Fields**: `{{ $json.merge_fields }}`
   - **Tags**: `{{ $json.tags }}`

2. **Email Template Setup in Mailchimp**:
   - Create template with merge variables:
     - `*|LICENSE_KEY|*` - Display the license key
     - `*|LICENSE_EXPIRES|*` - Show expiration date
     - `*|FEATURES|*` - List features
     - `*|DOWNLOAD_LINK|*` - Link to app download
     - `*|ACTIVATION_DATE|*` - When license was activated

3. **Example Email Template HTML**:
```html
<h2>Welcome!</h2>
<p>Your Metadata Updater Pro license has been activated.</p>

<h3>License Details</h3>
<ul>
  <li><strong>License Key:</strong> <code>*|LICENSE_KEY|*</code></li>
  <li><strong>Valid Until:</strong> *|LICENSE_EXPIRES|*</li>
  <li><strong>Activated:</strong> *|ACTIVATION_DATE|*</li>
  <li><strong>Features:</strong> *|FEATURES|*</li>
</ul>

<p>
  <a href="*|DOWNLOAD_LINK|*" class="button">Download App</a>
</p>

<p>Questions? <a href="mailto:*|SUPPORT_EMAIL|*">Contact support</a></p>
```

## Workflow Variations

### Variant A: License Duration as Parameter
Modify the "Build JWT Payload" step to accept `duration_days` from input:

```javascript
// Input could include duration_days
{
  "email": "user@example.com",
  "duration_days": 180
}

// Then in JWT generation:
expires: DateTime.now().plus({ days: $json.duration_days }).toISO()
```

### Variant B: Custom Features
Allow selecting which features to enable:

```javascript
{
  "email": "user@example.com",
  "features": ['metadata_update']  // Only metadata, not genre detection
}

// In JWT:
features: $json.features || ['metadata_update', 'genre_detection']
```

### Variant C: Batch License Generation
Accept array of emails and generate multiple licenses:

```javascript
// Input:
{
  "emails": ["user1@example.com", "user2@example.com"]
}

// Loop node over emails, generate token for each
```

## Workflow Import Troubleshooting

### Common Import Errors

**"Could not find property option"** or **"f[m] is not iterable"**
- ✓ These errors indicate JSON structure issues
- ✓ Use the corrected `n8n_license_flow.json` file from docs/
- ✓ Ensure you're importing the full file, not a partial copy
- ✓ Verify the JSON is valid (no syntax errors)

**"Property 'x' is not recognized"**
- ✓ Clear your browser cache and reload n8n
- ✓ Verify you're using a compatible n8n version (1.0+)
- ✓ Check that all node types exist in your n8n instance

**Import succeeds but workflow won't execute**
- ✓ Check that `LICENSE_PRIVATE_KEY` environment variable is set
- ✓ Verify the private key format has `BEGIN RSA PRIVATE KEY` markers
- ✓ Test by running: `echo $LICENSE_PRIVATE_KEY` in n8n shell
- ✓ Ensure no extra whitespace or line breaks in the key

## Error Handling

### Common Issues

**Issue 1: "LICENSE_PRIVATE_KEY not found"**
- ✓ Set environment variable in n8n Settings
- ✓ Format: Full private key with BEGIN/END markers
- ✓ Use `\n` for line breaks (or paste multiline in n8n)

**Issue 2: Invalid JWT signature on app side**
- ✓ Verify public key in app matches private key here
- ✓ Check RS256 algorithm is being used
- ✓ Ensure no extra whitespace in key

**Issue 3: Token expires immediately**
- ✓ Verify `expiresIn: '365d'` is set correctly
- ✓ Check system clock sync between n8n and app servers
- ✓ Ensure expires timestamp is in future

**Issue 4: Mailchimp field labels don't show**
- ✓ Verify merge field names exactly match (case-sensitive)
- ✓ Check merge fields exist in Mailchimp audience
- ✓ Format: `*|FIELD_NAME|*` (asterisks + pipes)

## Monitoring & Auditing

### Recommendations

1. **Log each license generation**:
   - Add step to save to Google Sheets/database with timestamp
   - Include: email, license_key (first 20 chars), expiration
   - Helps identify issues later

2. **Setup alerts**:
   - Alert if private key not set (workflow will fail)
   - Alert if email validation fails repeatedly
   - Alert if Mailchimp update fails

3. **Tracking**:
   - Save all generated licenses in a spreadsheet for auditing
   - Track which licenses were sent to which emails
   - Monitor license activation rate (track via app telemetry)

## Example n8n JSON Export

**Complete, production-ready workflow JSON:**

The full workflow is available in [`docs/n8n_license_flow.json`](n8n_license_flow.json) — this file can be imported directly into n8n:

**To import:**
1. In n8n, go to **Workflows** → Click menu (⋮) → **Import from file**
2. Select `n8n_license_flow.json`
3. Review the workflow structure
4. Set the `LICENSE_PRIVATE_KEY` environment variable (see Configuration section)
5. Test with sample email

**Workflow includes:**
- ✅ Email validation with Switch node for conditional routing
- ✅ JWT token generation with RS256 algorithm
- ✅ Mailchimp payload formatting
- ✅ Error handling for invalid emails
- ✅ Success and error output branches

**Key nodes in the workflow:**
1. **Start** - Manual trigger
2. **Validate & Prepare** - Email validation + timestamp generation
3. **Email Valid?** - Switch node for true/false branches
4. **Generate JWT Token** - Sign payload with private key
5. **Build Mailchimp JSON** - Format data for Mailchimp
6. **Output Success** - Return completed payload
7. **Output Error** - Return validation error

## Next Steps

1. ✅ Implement this workflow in your n8n instance
2. ✅ Test with sample emails
3. ✅ Connect to Mailchimp for email sending
4. ✅ Deploy to production
5. ✅ Monitor license generation and activation rates
6. ✅ (Optional) Setup analytics dashboard to track adoption

---

**Questions?** Refer to the test output in `test_jwt_licensing.py` to see example license tokens and how they're validated.
