# n8n License Flow - Quick Setup Guide

## 📋 Prerequisites

Before importing the workflow, you need:

1. **n8n instance** running (cloud or self-hosted)
2. **Private Key** from `config/license_private.pem`
3. **Mailchimp API Key** (optional if not integrating with Mailchimp)
4. **Python 3.7+** for generating keys (already done)

## 🚀 Setup Steps

### Step 1: Set Environment Variable in n8n

Your **private key must be stored as an environment variable** in n8n, NOT hardcoded in the workflow.

**In n8n Interface**:
1. Click **Settings** (gear icon)
2. Go to **Environment Variables**
3. Add new variable:
   - **Name**: `LICENSE_PRIVATE_KEY`
   - **Value**: Copy entire content from `config/license_private.pem`

**Important**: 
- Include the `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----` lines
- Preserve all line breaks
- Keep it secret!

### Step 2: Import Workflow

1. In n8n, click **Workflows** → **New Workflow**
2. Click **Menu** (•••) → **View Source Code**
3. Copy entire content of `n8n_license_flow.json`
4. Paste into the source editor
5. Click **Update**
6. Click back to visual editor

### Step 3: Configure Mailchimp (Optional but Recommended)

If you want to auto-update Mailchimp:

1. Find the **"Update Mailchimp Contact"** node
2. Set your values:
   - Replace `YOUR_MAILCHIMP_API_KEY` with your actual API key
   - Replace `YOUR_LIST_ID` with your Mailchimp audience ID
3. Replace `us1` in URL with your Mailchimp datacenter code (find in API key)

**If skipping Mailchimp**:
- The workflow still outputs the JSON needed for Mailchimp
- You can use it elsewhere or copy/paste manually

### Step 4: Test the Workflow

1. Navigate to **Manual Trigger** node
2. Click **Execute Workflow** button
3. In "Get Email Input" node, manually enter:
   ```json
   {
     "email": "test@example.com"
   }
   ```
4. Watch it flow through and check **Output Mailchimp JSON** node
5. Verify license key is generated

## 📤 Using the Workflow

### Manual Trigger (Default)
```
Execute Workflow → Enter email → License generated → Mailchimp updated
```

### Webhook Trigger (Advanced)
To trigger from external system:

1. Right-click **Manual Trigger** node
2. Click **Convert to** → **Webhook**
3. Configure webhook details
4. Send POST request:
```bash
curl -X POST https://your-n8n-instance.com/webhook/license-generator \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com"
  }'
```

## 🔑 License Key Format

Generated keys look like:
```
MDUX_eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2VtYWlsIjoiem...
```

**Key Components**:
- **Prefix**: `MDUX_` (identifies as Metadata Updater license)
- **JWT Token**: Everything after prefix (634+ characters)
- **Valid for**: 365 days from generation
- **User**: Encoded in token (user email)

## 📊 Mailchimp Output

The workflow outputs JSON in this format:

```json
{
  "email_address": "user@example.com",
  "status": "subscribed",
  "merge_fields": {
    "LICENSE_KEY": "MDUX_eyJhbGc...",
    "LICENSE_EXPIRES": "2026-04-19",
    "DAYS_VALID": "365",
    "FEATURES": "Metadata Update, Genre Detection",
    "ACTIVATION_DATE": "2025-04-19T16:44:19.137405Z",
    "DOWNLOAD_LINK": "https://your-domain.com/download",
    "SUPPORT_EMAIL": "support@your-domain.com"
  },
  "tags": ["license_active", "2025"],
  "marketing_permissions": {
    "marketing_consent": "opted_in"
  }
}
```

**Use this to**:
- Update Mailchimp contacts automatically
- Trigger email templates
- Send custom emails with license details
- Track license issuance

## ✅ Testing Locally

Before deploying, test the full pipeline:

```bash
cd /Users/djzrex/Documents/GitHub/metadata_updater

# Test 1: Verify JWT validation works
python3 test_jwt_licensing.py

# Test 2: Manually generate a token (for testing in n8n)
python3 -c "
import sys
sys.path.insert(0, 'src')
from license_key import LicenseManager

# Create test license
mgr = LicenseManager()
test_key = 'MDUX_test_token_here'
is_valid, msg = mgr.validate_key(test_key)
print(f'Valid: {is_valid}')
print(f'Message: {msg}')
"
```

## 🐛 Troubleshooting

### Error: "LICENSE_PRIVATE_KEY not found"
- ✅ Check environment variable is set in n8n Settings
- ✅ Verify spelling: `LICENSE_PRIVATE_KEY` (all caps, underscore)
- ✅ Test by adding a debug node that outputs `{{ process.env.LICENSE_PRIVATE_KEY }}`

### Error: "Invalid JWT signature"
- ✅ Verify private key matches public key in app
- ✅ Check RS256 algorithm is used
- ✅ Regenerate keys if necessary (starts fresh)

### Mailchimp update fails
- ✅ Verify API key is correct
- ✅ Verify List ID is correct
- ✅ Check datacenter code matches (us1, us2, etc.)
- ✅ Confirm email is valid

### License key not working in app
- ✅ Verify app has public key in `config/license_public.pem`
- ✅ Check license expiration date hasn't passed
- ✅ Test with `test_jwt_licensing.py` script
- ✅ Reinstall app dependencies: `pip install -r requirements_webview.txt`

## 🔒 Security Best Practices

1. **Private Key Protection**:
   - ✅ Store only in n8n environment variables
   - ✅ Never commit to Git
   - ✅ Never share with anyone

2. **API Key Protection**:
   - ✅ Store Mailchimp API key in n8n credentials
   - ✅ Don't hardcode in workflow

3. **Audit Trail**:
   - ✅ Enable n8n execution history
   - ✅ Log all license generations
   - ✅ Monitor suspicious patterns

4. **Key Rotation**:
   - ✅ Rotate private key annually
   - ✅ Update public key in app repo and deployed apps
   - ✅ Existing licenses continue working (time-based expiration)

## 📈 Next Steps

1. ✅ Deploy workflow to n8n
2. ✅ Test with sample emails
3. ✅ Connect to Mailchimp for email delivery
4. ✅ Setup dashboards to monitor license issuance
5. ✅ Document licensing process for team

## 💡 Advanced: Custom Features

You can modify the workflow to support feature-specific licenses:

**Example**: Developer license vs Standard license

```javascript
// In "Build Mailchimp JSON" node, add:
features: $json.license_type === 'developer' 
  ? ['metadata_update', 'genre_detection', 'api_access']
  : ['metadata_update', 'genre_detection']
```

## 🆘 Getting Help

If issues arise:

1. Check n8n logs: **Menu** → **Executions** (view failed runs)
2. Test JWT locally: Run `test_jwt_licensing.py`
3. Verify environment variables: Add debug node in workflow
4. Check Mailchimp API status: https://status.mailchimp.com/

---

**Questions?** Reference the full documentation in `N8N_LICENSE_FLOW.md`
