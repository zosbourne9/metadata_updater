# Contributing

Thanks for contributing! This document covers the non-obvious parts of working in this repo.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS/Linux
pip install -r requirements_webview.txt
cp .env.example .env            # then add your API keys
```

## Running

```bash
cd src
python main.py
```

**Important:** `src/` modules use flat imports (`from api import ...`). Always run from inside `src/` — the package does not work as `python src/main.py` from the repo root in all environments, and it is not importable as a package.

## Verification

There is no test suite, linter, or type checker configured. To verify changes:

1. Launch the app and smoke test the flow: select files → process → review modal → verify tags written (e.g. with `mutagen` or any tag viewer).
2. For build changes, run `bash build.sh` and launch the resulting executable from `dist/`.

## Gotchas

- **Resource paths**: never hardcode paths to `config/`, `web/`, or `assets/`. Use `src/resource_path.get_resource_path()` — it resolves correctly in dev and inside PyInstaller bundles (`sys._MEIPASS`).
- **New data files** must be added to the `datas` list in `build_pywebview.spec` or they will be missing from builds.
- **App version** string (`"2.0"`) is duplicated in `src/metadata_updater_webview.py` and `src/api.py` — update both.
- **Secrets**: `.env`, `config/spotify_credentials.json`, `*.pem`, `*.key` are gitignored. Never commit credentials. See [SECURITY.md](SECURITY.md).

## Style

- Python 3.12+, stdlib style; keep modules in `src/` flat-importable.
- Frontend is plain HTML/CSS/JS in `web/` — no bundler, no framework.
- Prefer `logging` over `print()` for diagnostics in library-style modules.
