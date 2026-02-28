# Metadata Updater

A powerful Python desktop application for automatically updating audio metadata using Spotify, MusicBrainz, and AI-powered genre detection.

## Features

- **Multi-Source Metadata Retrieval**: Combines data from Spotify and MusicBrainz APIs for comprehensive metadata
- **AI-Powered Genre Detection**: Uses OpenRouter's Gemini 2.5 Flash for intelligent genre classification
- **Smart Source Selection**: Intelligently chooses the best metadata source based on quality scoring
- **Batch Processing**: Process multiple files or entire folders at once
- **Progress Tracking**: Real-time progress updates with detailed status information
- **File Renaming**: Automatically rename files based on updated metadata
- **License Management**: Built-in license system for controlling usage
- **Cross-Platform**: Supports macOS and other platforms

## Supported Audio Formats

- MP3 (.mp3)
- M4A (.m4a)

## Installation

### Dependencies

Install the required Python packages:

```bash
pip install openai>=1.0.0
```

Additional dependencies include:
- PyQt6 (GUI framework)
- spotipy (Spotify API)
- mutagen (audio metadata handling)
- requests (HTTP requests)
- certifi (SSL certificates)

### Building Executable

The project includes a PyInstaller spec file for creating standalone executables:

```bash
pyinstaller "Metadata Updater.spec"
```

## Configuration

### API Keys Setup

The application requires API keys for external services. These are configured via environment variables for security:

1. **Copy the example environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Add your API credentials to `.env`**:
   ```
   SPOTIFY_CLIENT_ID=your_spotify_client_id_here
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
   OPENROUTER_API_KEY=sk-or-v1-your_openrouter_api_key_here
   ```

3. **Get your API keys**:
   - **Spotify**: https://developer.spotify.com/dashboard
   - **OpenRouter**: https://openrouter.ai/keys

## Usage

### Running the Application

```bash
python main.py
```

### Basic Workflow

1. **Select Files**: Choose individual files or an entire folder
2. **Choose Fields**: Select which metadata fields to update
3. **Process**: Click "Update Tags" to begin processing
4. **Monitor Progress**: Watch real-time progress and status updates

### Features Overview

#### Metadata Fields
- Artist
- Title
- Album
- Year
- Genre & Subgenres
- Track Number
- Spotify ID
- Artist ID
- **Rating** (Spotify popularity converted to ID3 POPM frame)

#### Smart Genre Detection
The application uses a sophisticated genre detection system that:
- Prioritizes MusicBrainz data when reliable
- Falls back to AI-powered classification when needed
- Considers confidence scores and genre reliability
- Avoids generic or unreliable classifications

#### Rating System
The application pulls track popularity from Spotify and converts it to a standard ID3 POPM frame rating:
- Spotify popularity scale (0-100) → ID3 POPM rating (0-255)
- Example: Spotify popularity 69 → Rating 176
- Ratings are stored in the ID3 POPM frame with email identifier "Serato" for DJ compatibility
- Works with both MP3 and M4A files

#### Intelligent Source Selection
The metadata engine scores sources based on:
- Release date accuracy (prefers original releases)
- Album type (avoids compilations)
- Data completeness
- Source reliability

## Architecture

### Core Components

- **MetadataUpdater**: Main application class and UI controller
- **SpotifyIntegration**: Handles Spotify API interactions
- **MusicBrainzIntegration**: Manages MusicBrainz queries
- **GenreFinder**: AI-powered genre detection
- **UnifiedCacheManager**: Caching system for API responses
- **LicenseManager**: Usage tracking and licensing
- **UIElements**: Qt-based user interface components

### Key Files

- `main.py`: Application entry point and initialization
- `metadata_updater.py`: Core metadata processing logic
- `spotify_integration.py`: Spotify API integration
- `mb_integration.py`: MusicBrainz API integration
- `genre_finder.py`: AI genre detection
- `ui_elements.py`: User interface components
- `constants.py`: API keys and configuration

## Development

### Debug Mode

Enable debug logging by setting `ENABLE_DEBUG_LOGGING = True` in `main.py`. This will:
- Log all operations to `metadata_updater_debug.txt`
- Redirect console output to the log file
- Provide detailed error information

### Platform-Specific Features

#### macOS
- Automatic bundle path detection
- Dark theme support
- Dock icon integration
- App cache directory management

## License

This project includes a license management system for controlling usage and access.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Troubleshooting

### Common Issues

1. **API Rate Limits**: The application includes rate limiting to prevent API quota exhaustion
2. **File Access**: Ensure audio files are not locked by other applications
3. **Network Connectivity**: Required for Spotify, MusicBrainz, and OpenRouter APIs

### Debug Information

Check the debug log file (`metadata_updater_debug.txt`) for detailed error information when troubleshooting issues.

## Version

Current version: 1.7

## API Integration

### Spotify
- Uses spotipy library for Spotify Web API access
- Implements automatic token refresh
- Includes smart search with artist hints

### MusicBrainz  
- Direct API integration with rate limiting
- Prefers original release data
- Handles multiple release matching

### OpenRouter (Gemini 2.5 Flash)
- AI-powered genre classification
- Confidence scoring for reliability
- Enhanced pattern matching for genre detection