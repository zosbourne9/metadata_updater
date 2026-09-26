# AGENTS.md

Desktop app (Python 3.12+, pywebview) that auto-updates audio metadata (MP3/M4A) from Spotify, MusicBrainz, and OpenRouter AI genre detection. No pytest, lint, typecheck, or CI config exists — verification is manual (launch the app and smoke test; see CONTRIBUTING.md).

## Run / Build

- Install deps from `requirements_webview.txt` into `.venv` (light install — heavy ML deps were removed).
- Run the app: `cd src && python main.py` (SETUP.md's documented entrypoint).
- Build executable: `bash build.sh` → runs PyInstaller with `build_pywebview.spec`; output in `dist/`.
- New data files (web/, config/, assets/) must be added to the `datas` list in `build_pywebview.spec` or they will be missing from the bundle.

## Architecture

- `src/main.py` creates the pywebview window loading `web/index.html`; Python↔JS bridge is `src/api.py` (`MetadataUpdaterAPI`, exposed as `js_api`; frontend calls `pywebview.api.*` from ES modules in `web/js/`).
- Frontend is ES modules (`web/js/main.js` entry). Inline HTML handlers reference `window.*` globals — cross-module functions used by inline handlers must be assigned to `window` (see files.js, processing.js, review.js). Python→JS callbacks (`window.onProgressUpdate`, etc.) must stay on `window`.
- Core business logic (search pipeline, review flow, processing threads) lives in `src/metadata_updater_webview.py`; `integration_helper.py` wires the Spotify/MusicBrainz/AI integrations.
- All `src/` modules use flat imports (`from api import ...`) — run from `src/` context, not as a package.
- Access `config/`, `web/`, `assets/` via `src/resource_path.get_resource_path()` — it resolves dev vs PyInstaller (`_MEIPASS`) paths. Don't hardcode relative paths.
- Config files: `config/categorized_genres.json`, `config/genre_characteristics.json` (genre data).

## Environment & secrets

- Copy `.env.example` → `.env` at repo root (loaded by `src/constants.py` via `load_dotenv()`): `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `OPENROUTER_API_KEY`.
- Spotify credentials load from `.env` first; `config/spotify_credentials.json` (gitignored) works only as a local override.
- `AI_MODEL` env var selects the OpenRouter model (default `google/gemini-2.5-flash`, see `src/constants.py`).
- Never commit secrets: `.env`, `config/spotify_credentials.json`, `*.pem`, `*.key` are gitignored.

## Gotchas

- `SETUP.md` may lag the code — trust the code and CONTRIBUTING.md.
- Debug logging: set `ENABLE_DEBUG_LOGGING = True` in `src/main.py`; logs write to `docs/metadata_updater_debug.txt` and `docs/search_debug.log` (both gitignored).
- App version string (`"2.1"`) is duplicated in `src/metadata_updater_webview.py` and `src/api.py` — update both if bumping.
- Cache location: `~/.metadata_updater` (Windows) / `~/Library/Application Support/Metadata Updater` (macOS), set as `CACHE_DIR` in `main.py`.
