#!/usr/bin/env python3
"""Starlette app: routes, WebSocket endpoint, message dispatch.

Single-session server: one active player at a time. A new WebSocket
connection takes over from any existing one (session takeover).

Thin routing layer. All game logic is in handlers.py, all state in
session.py, all serialization in serializers.py. This module owns
only: HTTP routes, WebSocket lifecycle, session takeover, and the
handler dispatch table.
"""

import asyncio
import contextlib
from collections.abc import Callable
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..engine.config_loader import narration_language
from ..engine.logging_util import log
from ..engine.models import EngineConfig
from .handlers import (
    _send,
    handle_burn_momentum,
    handle_correction,
    handle_create_player,
    handle_debug_state,
    handle_delete_player,
    handle_delete_save,
    handle_dismiss_epilogue,
    handle_generate_epilogue,
    handle_list_players,
    handle_list_saves,
    handle_load,
    handle_new_chapter,
    handle_player_input,
    handle_recap,
    handle_save,
    handle_select_player,
    handle_start_game,
    handle_status_query,
    handle_tracks_query,
)
from .serializers import build_creation_options, build_ui_strings
from .session import Session

# ── Static files ──────────────────────────────────────────────

_STATIC_DIR = Path(__file__).resolve().parent / "static"

# ── Shared session ────────────────────────────────────────────

_session = Session(config=EngineConfig(narration_lang=narration_language()))

# ── Handler dispatch table ────────────────────────────────────

_HANDLERS: dict[str, Callable] = {
    "list_players": handle_list_players,
    "create_player": handle_create_player,
    "select_player": handle_select_player,
    "delete_player": handle_delete_player,
    "start_game": handle_start_game,
    "player_input": handle_player_input,
    "correction": handle_correction,
    "burn_momentum": handle_burn_momentum,
    "list_saves": handle_list_saves,
    "save": handle_save,
    "load": handle_load,
    "delete_save": handle_delete_save,
    "recap": handle_recap,
    "status_query": handle_status_query,
    "tracks_query": handle_tracks_query,
    "generate_epilogue": handle_generate_epilogue,
    "dismiss_epilogue": handle_dismiss_epilogue,
    "new_chapter": handle_new_chapter,
    "debug_state": handle_debug_state,
}

# ── Origin check ──────────────────────────────────────────────

_SAFE_ORIGINS = {"localhost", "127.0.0.1", "[::1]"}


def _check_origin(ws: WebSocket) -> bool:
    """Reject WebSocket connections from untrusted origins (cross-site hijacking)."""
    origin = (ws.headers.get("origin") or "").strip()
    if not origin:
        return True  # Non-browser clients (curl, Elvira) don't send Origin
    try:
        from urllib.parse import urlparse

        host = urlparse(origin).hostname or ""
        return host in _SAFE_ORIGINS
    except Exception:
        return False


# ── WebSocket endpoint ────────────────────────────────────────


async def websocket_endpoint(ws: WebSocket) -> None:
    """WebSocket lifecycle: origin check, accept, takeover, state resend, message loop."""
    if not _check_origin(ws):
        log(f"[Web] Rejected WebSocket from origin: {ws.headers.get('origin')}", level="warning")
        await ws.close(code=1008)
        return

    await ws.accept()

    # Session takeover: notify old connection and wait for any in-flight turn
    if _session.active_ws is not None:
        with contextlib.suppress(Exception):
            await _session.active_ws.send_json({"type": "session_taken"})
            await _session.active_ws.close()
    # Wait for in-flight processing to finish before accepting new commands.
    # Prevents the new connection from reading partially-mutated game state.
    for _ in range(100):  # 10s max wait
        if not _session.processing:
            break
        await asyncio.sleep(0.1)
    _session.active_ws = ws

    # Initial state
    try:
        await _send(ws, {"type": "ui_strings", "strings": build_ui_strings()})
        await handle_list_players(_session, ws, {})

        # Orphan input recovery
        orphan = _session.orphan_input()
        if orphan:
            await _send(ws, {"type": "retry_available", "text": orphan})

        # Resend current player state on reconnect
        if _session.player and _session.game is not None:
            await _send(
                ws,
                {
                    "type": "player_selected",
                    "name": _session.player,
                    "has_game": True,
                    "messages": _session.filtered_messages(),
                },
            )
        elif _session.player:
            await _send(
                ws,
                {
                    "type": "player_selected",
                    "name": _session.player,
                    "has_game": False,
                    "creation_options": build_creation_options(),
                },
            )
    except Exception:
        return

    # Message loop with rate limiting (10 messages per second burst, 2/s sustained)
    _msg_times: list[float] = []
    _RATE_WINDOW = 5.0  # seconds
    _RATE_MAX = 20  # max messages per window

    try:
        while True:
            data = await ws.receive_json()

            now = asyncio.get_event_loop().time()
            _msg_times = [t for t in _msg_times if now - t < _RATE_WINDOW]
            if len(_msg_times) >= _RATE_MAX:
                await _send(ws, {"type": "error", "text": "Rate limited. Please slow down."})
                continue
            _msg_times.append(now)

            msg_type = data.get("type", "")
            handler = _HANDLERS.get(msg_type)
            if handler:
                await handler(_session, ws, data)
            else:
                await _send(ws, {"type": "error", "text": f"Unknown message type: {msg_type}"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log(f"[Web] WebSocket error: {e}", level="error")
    finally:
        if _session.active_ws is ws:
            _session.active_ws = None


# ── HTTP routes ───────────────────────────────────────────────


async def homepage(_request: object) -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


async def health(_request: object) -> JSONResponse:
    """Health check for monitoring and Elvira server readiness."""
    return JSONResponse({"status": "ok"})


# ── App ───────────────────────────────────────────────────────

app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/health", health),
        WebSocketRoute("/ws", websocket_endpoint),
    ],
)
