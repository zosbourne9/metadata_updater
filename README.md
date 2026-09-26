# Metadata Updater

A cross-platform desktop application that automatically fixes audio metadata (MP3/M4A) by combining Spotify, MusicBrainz, and AI-powered genre detection — built for DJs and music collectors.

Built with Python and [pywebview](https://pywebview.flowrl.com/); the UI is plain HTML/CSS/JS rendered in a native webview.

## Features

- **Multi-source metadata retrieval** — combines Spotify and MusicBrainz data with quality scoring to pick the best source (release-date accuracy, album type, data completeness, source reliability)
- **AI-powered genre detection** — uses an LLM via OpenRouter (default: `google/gemini-2.5-flash`) constrained to a curated genre taxonomy (`config/categorized_genres.json`)
- **Batch processing** — process folders of files at once with configurable concurrency
- **Review flow** — ambiguous matches pause processing and let you pick or edit the right metadata
- **File renaming** — optionally rename files from the updated metadata
- **Serato integration** — resolves filenames against Serato libraries; Spotify popularity is written as ID3 POPM ratings for DJ software
- **Supported formats** — MP3 (`.mp3`) and M4A (`.m4a`)

## Setup

Requires Python 3.12+.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements_webview.txt

# 3. Configure API credentials
cp .env.example .env
```

Edit `.env` with your credentials:

```
SPOTIFY_CLIENT_ID=...        # https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_SECRET=...
OPENROUTER_API_KEY=sk-or-... # https://openrouter.ai/keys
```

## Usage

```bash
cd src
python main.py
```

1. Drag and drop audio files (or browse) into the app
2. Select which metadata fields to update
3. Click **Start Processing** and monitor progress
4. Review any ambiguous matches when prompted

## Building an executable

```bash
bash build.sh        # runs PyInstaller with build_pywebview.spec
```

Output lands in `dist/` (`Metadata Updater.exe` / `.app` / binary depending on platform).

## Configuration

- `.env` — API credentials (never commit this)
- `config/categorized_genres.json` — the genre taxonomy the AI must classify into
- `config/genre_characteristics.json` — per-genre characteristics injected into prompts
- `AI_MODEL` env var — override the OpenRouter model (see `src/constants.py`)

## Development notes

- All `src/` modules use flat imports (`from api import ...`) — run Python from the `src/` directory, not as a package.
- Access `config/`, `web/`, `assets/` through `src/resource_path.get_resource_path()` so paths work in both dev and PyInstaller bundles.
- Python ↔ JS bridge: `src/api.py` exposes `MetadataUpdaterAPI` to the frontend; `web/app.js` calls methods via `pywebview.api.*`.
- New data files must be added to the `datas` list in `build_pywebview.spec` or they won't ship in the bundle.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SETUP.md](SETUP.md) for more detail.

## License

Released under the [MIT License](LICENSE).
