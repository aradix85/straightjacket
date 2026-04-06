# Security

## API keys

Straightjacket handles AI provider API keys. These are stored in:

- `config.yaml` (`ai.api_key_env` points to an environment variable)
- Environment variables (e.g. `CEREBRAS_API_KEY`)

API keys are never logged, never included in save files, and never sent over the WebSocket.

## Reporting vulnerabilities

If you find a security issue, email the maintainer directly instead of opening a public issue. Include steps to reproduce.

## Scope

This is a self-hosted application. It runs a Starlette/uvicorn server, typically on localhost. It is not designed for public internet deployment without additional hardening (reverse proxy, TLS, authentication).
