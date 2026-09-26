# Security Policy

## Reporting a vulnerability

Please open a [GitHub issue](https://github.com/zosbourne9/metadata_updater/issues) marked `security`, or contact the maintainer directly. Include steps to reproduce and the affected version.

## Scope

This is a local desktop application. The main security-relevant surfaces are:

- **API credentials** (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `OPENROUTER_API_KEY`) — stored in a local `.env` file, never transmitted anywhere except to the respective APIs.
- **Audio file handling** — files are read/written locally via `mutagen`.
- **HTTP requests** — Spotify, MusicBrainz, OpenRouter, and a riddim-name scraper (httpx/requests).

## For contributors

- **Never commit secrets.** `.env`, `config/spotify_credentials.json`, `*.pem`, and `*.key` are gitignored — keep it that way.
- If you discover a secret has been committed, notify the maintainer immediately so the credential can be rotated and history scrubbed.
- Do not log credentials or access tokens, even at debug level.
