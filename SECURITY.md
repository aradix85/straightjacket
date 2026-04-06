# Security

## API keys

Straightjacket handles AI provider API keys. These are stored in:

- `config.yaml` (server-wide key, file permissions restricted to owner on write)
- `users/{name}/settings.json` (per-user keys when no server key is set)
- Environment variables (configured via `ai.api_key_env` in config.yaml)

API keys are never logged, never included in save files, and never sent to the frontend.

## Reporting vulnerabilities

If you find a security issue, email the maintainer directly instead of opening a public issue. Include steps to reproduce.

## Scope

This is a self-hosted application. It runs a NiceGUI web server, typically on localhost or a local network. It is not designed for public internet deployment without additional hardening (reverse proxy, authentication, rate limiting beyond the built-in invite code system).
