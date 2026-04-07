#!/usr/bin/env python3
"""Starlette app: routes, WebSocket endpoint, message dispatch.

Single-session server: one active player at a time. A new WebSocket
connection takes over from any existing one (session takeover).

Thin routing layer. All game logic is in handlers.py, all state in
session.py, all serialization in serializers.py. This module owns
only: HTTP routes, WebSocket lifecycle, session takeover, and the
handler dispatch table.
"""

import contextlib
from collections.abc import Callable
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..engine import narration_language
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
)
from .serializers import build_creation_options, build_state
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
    "generate_epilogue": handle_generate_epilogue,
    "dismiss_epilogue": handle_dismiss_epilogue,
    "new_chapter": handle_new_chapter,
    "debug_state": handle_debug_state,
}

# ── WebSocket endpoint ────────────────────────────────────────


async def websocket_endpoint(ws: WebSocket) -> None:
    """WebSocket lifecycle: accept, takeover, state resend, message loop."""
    await ws.accept()

    # Session takeover: notify and close old connection
    if _session.active_ws is not None:
        with contextlib.suppress(Exception):
            await _session.active_ws.send_json({"type": "session_taken"})
            await _session.active_ws.close()
    _session.active_ws = ws

    # Initial state
    try:
        await handle_list_players(_session, ws, {})

        # Orphan input recovery
        orphan = _session.orphan_input()
        if orphan:
            await _send(ws, {"type": "retry_available", "text": orphan})

        # Resend current player state on reconnect
        if _session.player and _session.game is not None:
            await _send(ws, {
                "type": "player_selected",
                "name": _session.player,
                "has_game": True,
                "state": build_state(_session.game),
                "messages": _session.filtered_messages(),
            })
        elif _session.player:
            await _send(ws, {
                "type": "player_selected",
                "name": _session.player,
                "has_game": False,
                "creation_options": build_creation_options(),
            })
    except Exception:
        return

    # Message loop
    try:
        while True:
            data = await ws.receive_json()
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

async def homepage(_request):
    return FileResponse(_STATIC_DIR / "index.html")


# ── App ───────────────────────────────────────────────────────

app = Starlette(
    routes=[
        Route("/", homepage),
        WebSocketRoute("/ws", websocket_endpoint),
    ],
)
