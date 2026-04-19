import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MAX_FILENAME_LENGTH = 255  # Maximum filename length for most file systems

# Spotify API configuration
# Get your credentials from: https://developer.spotify.com/dashboard
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', '')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET', '')

# OpenRouter API configuration
# Get your API key from: https://openrouter.ai/keys
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')

# AI Model Configuration - Change this to switch models across the entire app
# Popular options:
#   - google/gemini-2.5-flash (current default - fast & cheap)
#   - google/gemini-2.0-flash-thinking (extended thinking)
#   - anthropic/claude-3.5-sonnet (best balance)
#   - anthropic/claude-3.5-opus (most powerful)
#   - openai/gpt-4o (latest GPT)
#   - openai/gpt-4-turbo
#   - openai/gpt-3.5-turbo (cheapest)
AI_MODEL = os.getenv('AI_MODEL', 'google/gemini-2.5-flash')