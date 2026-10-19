import asyncio
import ipaddress
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..engine.engine_loader import eng
from ..engine.logging_util import log
from ..i18n import all_strings, t
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
    handle_request_succession_creation,
    handle_retire,
    handle_save,
    handle_select_player,
    handle_start_game,
    handle_start_succession,
    handle_status_query,
    handle_threats_query,
    handle_tracks_query,
    player_selected_message,
)
from .session import new_session

_STATIC_DIR = Path(__file__).resolve().parent / "static"


_session = new_session()


_HANDLERS: dict[str, Callable[..., Any]] = {
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
    "retire": handle_retire,
    "request_succession_creation": handle_request_succession_creation,
    "start_succession": handle_start_succession,
    "debug_state": handle_debug_state,
}


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _check_origin(ws: WebSocket) -> bool:
    origin = (ws.headers.get("origin") or "").strip()

    if not origin:
        return True

    try:
        parsed = urlparse(origin)
        host = parsed.hostname or ""
        if host in _LOOPBACK_HOSTS:
            return True
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return parsed.netloc.lower() == (ws.headers.get("host") or "").strip().lower()


async def _takeover_existing_session(ws: WebSocket) -> None:
    if _session.active_ws is not None:
        try:
            await _session.active_ws.send_json({"type": "session_taken"})
            await _session.active_ws.close()
        except (WebSocketDisconnect, RuntimeError, OSError) as e:
            log(f"[Web] takeover notify on old ws failed: {e}", level="debug")
    _rl = eng().rate_limit
    for _ in range(_rl.warn_probe_max_tries):
        if not _session.processing:
            break
        await asyncio.sleep(_rl.warn_probe_poll_seconds)
    _session.active_ws = ws


async def _send_initial_state(ws: WebSocket) -> None:
    await _send(ws, {"type": "ui_strings", "strings": all_strings()})
    await handle_list_players(_session, ws, {})

    orphan = _session.orphan_input()
    if orphan:
        await _send(ws, {"type": "retry_available", "text": orphan})

    if _session.player:
        await _send(ws, player_selected_message(_session))


async def _dispatch_one_message(ws: WebSocket, data: dict[str, Any]) -> None:
    msg_type = data.get("type")
    if not isinstance(msg_type, str) or not msg_type:
        await _send(ws, {"type": "error", "text": t("error.malformed_message")})
        return
    handler = _HANDLERS.get(msg_type)
    if handler:
        try:
            await handler(_session, ws, data)
        except WebSocketDisconnect:
            raise
        except Exception as e:
            log(f"[Web] {msg_type} failed: {type(e).__name__}: {e}", level="error")
            await _send(ws, {"type": "error", "text": t("error.unexpected")})
    else:
        await _send(ws, {"type": "error", "text": t("error.unknown_msg_type", msg_type=msg_type)})


async def _message_loop(ws: WebSocket) -> None:
    rate_limit = eng().rate_limit
    message_times: list[float] = []

    while True:
        data = await ws.receive_json()

        now = asyncio.get_running_loop().time()
        message_times = [tm for tm in message_times if now - tm < rate_limit.window_seconds]
        if len(message_times) >= rate_limit.max_requests:
            await _send(ws, {"type": "error", "text": t("error.rate_limited")})
            continue
        message_times.append(now)

        await _dispatch_one_message(ws, data)


async def websocket_endpoint(ws: WebSocket) -> None:
    if not _check_origin(ws):
        log(f"[Web] Rejected WebSocket from origin: {ws.headers.get('origin')}", level="warning")
        await ws.close(code=1008)
        return

    await ws.accept()
    await _takeover_existing_session(ws)

    try:
        await _send_initial_state(ws)
    except (WebSocketDisconnect, RuntimeError, OSError) as e:
        log(f"[Web] initial state send failed: {e}", level="warning")
        return

    try:
        await _message_loop(ws)
    except WebSocketDisconnect:
        pass
    finally:
        if _session.active_ws is ws:
            _session.active_ws = None


async def homepage(_request: object) -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app = Starlette(
    routes=[
        Route("/", homepage),
        WebSocketRoute("/ws", websocket_endpoint),
    ],
)
