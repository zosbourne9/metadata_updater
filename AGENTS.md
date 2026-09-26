# AGENTS.md

Desktop app (Python 3.12+, pywebview) that auto-updates audio metadata (MP3/M4A) from Spotify, MusicBrainz, and OpenRouter AI genre detection. No pytest, lint, typecheck, or CI config exists — the only runnable check is `python test_jwt_licensing.py`.

## Run / Build

- Install deps from `requirements_webview.txt` into `.venv` (torch included — heavy install).
- Run the app: `cd src && python main.py` (SETUP.md's documented entrypoint).
- Build executable: `bash build.sh` → runs PyInstaller with `build_pywebview.spec`; output in `dist/`.
- New data files (web/, config/, assets/) must be added to the `datas` list in `build_pywebview.spec` or they will be missing from the bundle.

## Architecture

- `src/main.py` creates the pywebview window loading `web/index.html`; Python↔JS bridge is `src/api.py` (`MetadataUpdaterAPI`, exposed as `js_api`; frontend calls `pywebview.api.*` from `web/app.js`).
- Core business logic (search pipeline, review flow, processing threads) lives in `src/metadata_updater_webview.py`; `integration_helper.py` wires the Spotify/MusicBrainz/AI integrations.
- All `src/` modules use flat imports (`from api import ...`) — run from `src/` context, not as a package.
- Access `config/`, `web/`, `assets/` via `src/resource_path.get_resource_path()` — it resolves dev vs PyInstaller (`_MEIPASS`) paths. Don't hardcode relative paths.
- Config files: `config/categorized_genres.json`, `config/genre_characteristics.json` (genre data), `config/spotify_credentials.json`.

## Environment & secrets

- Copy `.env.example` → `.env` at repo root (loaded by `src/constants.py` via `load_dotenv()`): `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `OPENROUTER_API_KEY`.
- `AI_MODEL` env var selects the OpenRouter model (default `google/gemini-2.5-flash`, see `src/constants.py`).
- Licensing is JWT/RSA: keys at `config/license_private.pem` / `license_public.pem` (*.pem is gitignored). Never commit the private key. `test_jwt_licensing.py` verifies the key/token flow (expects the private key path as an argument when generating test tokens).

## Gotchas

- `docs/README.md` is stale — it still describes the old PyQt6 UI. Trust the code; the current UI is pywebview.
- `SETUP.md` references a root `CLAUDE.md` that no longer exists (it's gitignored).
- Debug logging: set `ENABLE_DEBUG_LOGGING = True` in `src/main.py`; logs write to `docs/metadata_updater_debug.txt` and `docs/search_debug.log`.
- App version string (`"2.0"`) is duplicated in `src/metadata_updater_webview.py` and `src/api.py` — update both if bumping.
- Cache location: `~/.metadata_updater` (Windows) / `~/Library/Application Support/Metadata Updater` (macOS), set as `CACHE_DIR` in `main.py`.
