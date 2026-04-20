"""Starlette app: routes, WebSocket endpoint, message dispatch.

Single-session server: one active player at a time. A new WebSocket
connection takes over from any existing one (session takeover).

Thin routing layer. All game logic is in handlers.py, all state in
session.py, all serialization in serializers.py. This module owns
only: HTTP routes, WebSocket lifecycle, session takeover, and the
handler dispatch table.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..engine.config_loader import narration_language
from ..engine.engine_loader import eng
from ..engine.logging_util import log
from ..engine.models import EngineConfig
from ..i18n import t
from .handlers import (
    _send,
    handle_advance_asset,
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
    handle_threats_query,
    handle_tracks_query,
)
from .serializers import build_creation_options, build_ui_strings
from .session import Session


_STATIC_DIR = Path(__file__).resolve().parent / "static"


_session = Session(config=EngineConfig(narration_lang=narration_language()))


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
    "threats_query": handle_threats_query,
    "advance_asset": handle_advance_asset,
    "generate_epilogue": handle_generate_epilogue,
    "dismiss_epilogue": handle_dismiss_epilogue,
    "new_chapter": handle_new_chapter,
    "debug_state": handle_debug_state,
}


_SAFE_ORIGINS = {"localhost", "127.0.0.1", "[::1]"}


def _check_origin(ws: WebSocket) -> bool:
    """Reject WebSocket connections from untrusted origins (cross-site hijacking)."""
    origin = (ws.headers.get("origin") or "").strip()
    # Non-browser clients (curl, Elvira) don't send Origin — allow through.
    if not origin:
        return True
    # Fail-closed: any parse error means we cannot verify the origin, so reject.
    try:
        from urllib.parse import urlparse

        host = urlparse(origin).hostname or ""
        return host in _SAFE_ORIGINS
    except ValueError as e:
        log(f"[Web] Origin parse failed for '{origin}': {e}", level="warning")
        return False


async def websocket_endpoint(ws: WebSocket) -> None:
    """WebSocket lifecycle: origin check, accept, takeover, state resend, message loop."""
    if not _check_origin(ws):
        log(f"[Web] Rejected WebSocket from origin: {ws.headers.get('origin')}", level="warning")
        await ws.close(code=1008)
        return

    await ws.accept()

    # Session takeover: notify old connection and wait for any in-flight turn
    if _session.active_ws is not None:
        try:
            await _session.active_ws.send_json({"type": "session_taken"})
            await _session.active_ws.close()
        except (WebSocketDisconnect, RuntimeError, OSError) as e:
            # Old socket already dead (disconnect) or in an invalid state —
            # takeover still proceeds; nothing else to clean up here.
            log(f"[Web] takeover notify on old ws failed: {e}", level="debug")
    # Wait for in-flight processing to finish before accepting new commands.
    # Prevents the new connection from reading partially-mutated game state.
    _rl = eng().rate_limit
    for _ in range(_rl.warn_probe_max_tries):
        if not _session.processing:
            break
        await asyncio.sleep(_rl.warn_probe_poll_seconds)
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
    except (WebSocketDisconnect, RuntimeError, OSError) as e:
        # Client closed before we finished sending initial state. Nothing to
        # recover; message loop below will exit on the same disconnect.
        log(f"[Web] initial state send failed: {e}", level="warning")
        return

    # Message loop with rate limiting — parameters from engine.yaml rate_limit.
    _msg_times: list[float] = []
    _RATE_WINDOW = _rl.window_seconds
    _RATE_MAX = _rl.max_requests

    try:
        while True:
            data = await ws.receive_json()

            now = asyncio.get_event_loop().time()
            _msg_times = [t for t in _msg_times if now - t < _RATE_WINDOW]
            if len(_msg_times) >= _RATE_MAX:
                await _send(ws, {"type": "error", "text": t("error.rate_limited")})
                continue
            _msg_times.append(now)

            msg_type = data.get("type", "")
            handler = _HANDLERS.get(msg_type)
            if handler:
                await handler(_session, ws, data)
            else:
                await _send(ws, {"type": "error", "text": t("error.unknown_msg_type", msg_type=msg_type)})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log(f"[Web] WebSocket error: {e}", level="error")
    finally:
        if _session.active_ws is ws:
            _session.active_ws = None


async def homepage(_request: object) -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


async def health(_request: object) -> JSONResponse:
    """Health check for monitoring and Elvira server readiness."""
    return JSONResponse({"status": "ok"})


app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/health", health),
        WebSocketRoute("/ws", websocket_endpoint),
    ],
)
