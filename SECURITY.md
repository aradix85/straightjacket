# Security

## API keys

Straightjacket reads AI provider API keys from the environment variables that `config.yaml` names; the key itself never goes in the file.

API keys are never logged, never included in save files, and never sent over the WebSocket.

## Input sanitization

Player names and save names are sanitized before use as filesystem paths. Path separators (`/`, `\`), parent references (`..`), and null bytes are stripped. This prevents path traversal attacks where a crafted name could read or write files outside the intended directory. Names that Windows cannot store safely are refused with `InvalidNameError` rather than altered: names holding any of `< > : " | ? *` or a control character (a drive name such as `D:` would otherwise point outside the users directory), reserved device names such as `CON`, `NUL`, `COM1`, or `LPT1` (with or without an extension), and names ending in a dot, which Windows would silently drop so that two names shared one folder. The player hears that the name cannot be used, and a rejected save name leaves the current save name in place.

The sanitization is in `user_management.py._safe_name()` and is applied in all persistence functions (save, load, delete) and user management functions (create, delete).

## Prompt injection via player input

Player input is included in AI prompts as XML element content. All player-supplied text (input, names, backstory, vow text) is escaped before insertion into prompt XML: `xml_utils.xe()` for element content and `xml_utils.xa()` for attribute values, both HTML entity escaping. This prevents players from injecting XML tags that could alter AI behavior — e.g. closing a `<scene>` tag and injecting a fake `<result type="STRONG_HIT">`.

The escaping is applied in every prompt-assembly module (`prompt_action.py`, `prompt_dialog.py`, `prompt_boundary.py`, `prompt_shared.py`, `prompt_blocks.py`, `director.py`) and in `ai/brain.py`, which escapes the player's input, NPC names, track names, the player name, the location, and the scene context with the same `xml_utils` helpers. Where the Brain must copy a choice back exactly, it chooses an id rather than a name: NPCs by their engine id, tracks by their track id. A track id is built from the track's name with every run of non-word characters replaced by an underscore (`game/turn.py` → `_maybe_create_track`), so it carries no markup even when the name does; the background vow, whose name is the player's own vow text, has the fixed id `vow_background`. The Brain's `player_intent` field is AI-generated from player input, not raw player text, which provides a secondary layer of isolation.

## Session model

Single-session server: one active player at a time. Opening a second browser tab or reconnecting takes over the existing session — the previous connection is closed with a notification. This is by design (solo RPG), not a bug. There is no multi-user support.

## Reporting vulnerabilities

If you find a security issue, contact the maintainer privately through the project page at blindgamer85.itch.io instead of opening a public issue. Include steps to reproduce.

## Scope

This is a self-hosted application. It runs a Starlette/uvicorn server on localhost by default (`server.host: "127.0.0.1"` in config.yaml). To allow LAN access (e.g. playing from a phone on the same network), set `server.host: "0.0.0.0"` — but only on trusted networks. It is not designed for public internet deployment without additional hardening (reverse proxy, TLS, authentication, rate limiting).
