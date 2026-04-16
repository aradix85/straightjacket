# Security

## API keys

Straightjacket handles AI provider API keys. These are stored in:

- `config.yaml` (`ai.api_key_env` points to an environment variable)
- Environment variables (e.g. `CEREBRAS_API_KEY`)

API keys are never logged, never included in save files, and never sent over the WebSocket.

## Input sanitization

Player names and save names are sanitized before use as filesystem paths. Path separators (`/`, `\`), parent references (`..`), and null bytes are stripped. This prevents path traversal attacks where a crafted name could read or write files outside the intended directory.

The sanitization is in `user_management.py._safe_name()` and is applied in all persistence functions (save, load, delete) and user management functions (create, delete).

## Prompt injection via player input

Player input is included in AI prompts as XML element content. All player-supplied text (input, names, backstory, vow text) is escaped via `xml_utils.xe()` (HTML entity escaping) before insertion into prompt XML. This prevents players from injecting XML tags that could alter AI behavior — e.g. closing a `<scene>` tag and injecting a fake `<result type="STRONG_HIT">`.

The escaping is applied in `prompt_builders.py` (all prompt assembly functions) and `brain.py` (Brain prompt). The Brain's `player_intent` field is AI-generated from player input, not raw player text, which provides a secondary layer of isolation.

## Session model

Single-session server: one active player at a time. Opening a second browser tab or reconnecting takes over the existing session — the previous connection is closed with a notification. This is by design (solo RPG), not a bug. There is no multi-user support.

## Reporting vulnerabilities

If you find a security issue, email the maintainer directly instead of opening a public issue. Include steps to reproduce.

## Scope

This is a self-hosted application. It runs a Starlette/uvicorn server on localhost by default (`server.host: "127.0.0.1"` in config.yaml). To allow LAN access (e.g. playing from a phone on the same network), set `server.host: "0.0.0.0"` — but only on trusted networks. It is not designed for public internet deployment without additional hardening (reverse proxy, TLS, authentication, rate limiting).
