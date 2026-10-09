# Security

## API keys

Straightjacket reads AI provider API keys from the environment variables that `config.yaml` names; the key itself never goes in the file.

API keys are never logged, never included in save files, and never sent over the WebSocket.

## Input sanitization

Player names and save names become folder and file names, so a name that could reach outside the users directory, or that the file system would quietly change, is refused with `InvalidNameError` rather than altered. Refused are names holding a path separator (`/`, `\`), any of `< > : " | ? *`, or a control character, null byte included (a drive name such as `D:` would otherwise point outside the users directory); names starting with a dot, which covers `.` and `..`; names ending in a dot, which Windows would silently drop; and reserved device names such as `CON`, `NUL`, `COM1`, or `LPT1`, with or without an extension. Refusing instead of stripping keeps two different names from sharing one folder. The only change made to a name is whitespace: leading and trailing spaces go, and a run of spaces becomes one. The player hears that the name cannot be used, and a rejected save name leaves the current save name in place.

The check is `user_management.py` → `_safe_name` and is applied in all persistence functions (save, load, delete) and user management functions (create, delete).

## Prompt injection via player input

Player input is included in AI prompts as XML element content. All player-supplied text (input, names, backstory, vow text) is escaped before insertion into prompt XML: `xml_utils.xe()` for element content and `xml_utils.xa()` for attribute values, both HTML entity escaping. This prevents players from injecting XML tags that could alter AI behavior — e.g. closing a `<scene>` tag and injecting a fake `<result type="STRONG_HIT">`.

The escaping is applied in every prompt-assembly module (`prompt_action.py`, `prompt_dialog.py`, `prompt_boundary.py`, `prompt_shared.py`, `prompt_blocks.py`, `director.py`) and in `ai/brain.py`, which escapes the player's input, NPC names, track names, the player name, the location, and the scene context with the same `xml_utils` helpers. Where the Brain must copy a choice back exactly, it chooses an id rather than a name: NPCs by their engine id, tracks by their track id. A track id is built from the track's name with every run of non-word characters replaced by an underscore (`game/turn.py` → `_maybe_create_track`), so it carries no markup even when the name does; the background vow, whose name is the player's own vow text, has the fixed id `vow_background`.

Escaping keeps markup out; it does not stop instructions written as plain text. A player can talk the Brain into a move, a stat, or a bonus the action does not warrant, but only among the options its schema offers, and the dice and the engine still decide the outcome. In a single-player game that changes only the player's own game.

## Session model

Single-session server: one active player at a time. Opening a second browser tab or reconnecting takes over the existing session — the previous connection is closed with a notification. This is by design (solo RPG), not a bug. There is no multi-user support.

## WebSocket origin

Because any new connection takes over the session, the server checks where a browser connection comes from (`web/server.py` → `_check_origin`). It accepts a page served from a loopback address (`localhost`, `127.0.0.1`, `::1`), and a page served from the same IP address and port the connection goes to, which is how a phone on the local network reaches the server. A page on any other site is refused, and so is a host name that is not loopback even when it matches, since a domain that resolves to a local address (DNS rebinding) would otherwise pass. A client that sends no `Origin` header is not a browser page and is accepted.

## Reporting vulnerabilities

If you find a security issue, contact the maintainer privately through the project page at blindgamer85.itch.io instead of opening a public issue. Include steps to reproduce.

## Scope

This is a self-hosted application. It runs a Starlette/uvicorn server on localhost by default (`server.host: "127.0.0.1"` in config.yaml). To allow LAN access (e.g. playing from a phone on the same network), set `server.host: "0.0.0.0"` — but only on trusted networks. It is not designed for public internet deployment without additional hardening (reverse proxy, TLS, authentication, rate limiting). Whoever can reach the server can take over the session, spend the API keys' credit, and read the whole game state, which the WebSocket hands out on a `debug_state` message for Elvira's WebSocket mode.
