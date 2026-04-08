# Security

## API keys

Straightjacket handles AI provider API keys. These are stored in:

- `config.yaml` (`ai.api_key_env` points to an environment variable)
- Environment variables (e.g. `CEREBRAS_API_KEY`)

API keys are never logged, never included in save files, and never sent over the WebSocket.

## Input sanitization

Player names and save names are sanitized before use as filesystem paths. Path separators (`/`, `\`), parent references (`..`), and null bytes are stripped. This prevents path traversal attacks where a crafted name could read or write files outside the intended directory.

The sanitization is in `logging_util._safe_name()` and is applied in all persistence functions (save, load, delete) and user management functions (create, delete).

## Session model

Single-session server: one active player at a time. Opening a second browser tab or reconnecting takes over the existing session — the previous connection is closed with a notification. This is by design (solo RPG), not a bug. There is no multi-user support.

## Reporting vulnerabilities

If you find a security issue, email the maintainer directly instead of opening a public issue. Include steps to reproduce.

## Scope

This is a self-hosted application. It runs a Starlette/uvicorn server on localhost by default (`server.host: "127.0.0.1"` in config.yaml). To allow LAN access (e.g. playing from a phone on the same network), set `server.host: "0.0.0.0"` — but only on trusted networks. It is not designed for public internet deployment without additional hardening (reverse proxy, TLS, authentication, rate limiting).
