# Setup Guide - Metadata Updater

This guide will help you set up the Metadata Updater application with the required API credentials.

## Prerequisites

- Python 3.12 or higher
- pip or conda package manager
- API keys for:
  - **Spotify Developer API**
  - **OpenRouter API**

## Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/metadata_updater.git
cd metadata_updater
```

## Step 2: Create a Virtual Environment (Recommended)

```bash
# Using venv
python -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

## Step 3: Install Dependencies

```bash
pip install -r requirements_webview.txt
```

## Step 4: Configure API Credentials

### 4.1 Copy the Example Environment File

```bash
cp .env.example .env
```

### 4.2 Get Your Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in or create a Spotify account
3. Create a new application
4. Accept the terms and create the app
5. Copy your **Client ID** and **Client Secret**
6. Add them to your `.env` file:

```
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
```

### 4.3 Get Your OpenRouter API Key

1. Go to [OpenRouter Keys](https://openrouter.ai/keys)
2. Log in or create an account
3. Create a new API key
4. Copy the key (it starts with `sk-or-v1-`)
5. Add it to your `.env` file:

```
OPENROUTER_API_KEY=sk-or-v1-your_key_here
```

## Step 5: Run the Application

```bash
cd src
python main.py
```

## Step 6: Using the Application

1. **Select Files**: Drag and drop audio files or use the file browser
2. **Choose Fields**: Select which metadata fields you want to update
3. **Process**: Click "Start Processing" to update your files
4. **Monitor Progress**: Watch the progress bar as files are processed

## Environment Variables

All sensitive configuration is stored in the `.env` file. The variables are:

| Variable | Purpose | Source |
|----------|---------|--------|
| `SPOTIFY_CLIENT_ID` | Spotify API authentication | Spotify Developer Dashboard |
| `SPOTIFY_CLIENT_SECRET` | Spotify API authentication | Spotify Developer Dashboard |
| `OPENROUTER_API_KEY` | OpenRouter API access | OpenRouter Keys page |

**Important**: Never commit `.env` to version control. The file is automatically excluded by `.gitignore`.

## Troubleshooting

### "API key not found" or "CLIENT_ID is empty"

**Solution**: Ensure your `.env` file exists in the project root directory and contains all required variables.

```bash
# Check if .env exists
ls -la .env

# Verify the content (don't share this output publicly!)
cat .env
```

### Spotify Authentication Fails

1. Verify your credentials are correct in the `.env` file
2. Check that your Spotify app hasn't been revoked
3. Ensure you have an active Spotify Developer account

### OpenRouter Requests Fail

1. Verify your API key is valid at https://openrouter.ai/keys
2. Check that you have credits available
3. Ensure your `.env` file contains the correct key format

### Application Won't Start

1. Ensure all dependencies are installed: `pip install -r requirements_webview.txt`
2. Verify Python version is 3.12+: `python --version`
3. Check the debug log: `cat docs/metadata_updater_debug.txt`

## Security Notes

- **Never commit** `.env` files to version control
- **Never share** your API keys in issues, PRs, or discussions
- **Regenerate keys** if you accidentally expose them
- **Use environment variables** for all sensitive configuration

## Next Steps

- Read the main [README.md](docs/README.md) for feature documentation
- Check [CLAUDE.md](CLAUDE.md) for technical architecture details
- Review common commands in the troubleshooting section

## Support

For issues or questions:
1. Check the debug log: `docs/metadata_updater_debug.txt`
2. Review existing issues on GitHub
3. Create a new issue with details about your error
