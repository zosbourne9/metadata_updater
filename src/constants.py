import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_FILENAME_LENGTH = 255  # Maximum filename length for most file systems

# Spotify API configuration
# Get your credentials from: https://developer.spotify.com/dashboard
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', '')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', '')

# OpenRouter API configuration for Gemini 2.5 Flash
# Get your API key from: https://openrouter.ai/keys
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')