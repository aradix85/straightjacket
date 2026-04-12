#!/usr/bin/env python3
"""WebSocket message handlers. One function per protocol message type.

Each handler receives (session, ws, msg) and is fully async.
Engine calls run via asyncio.to_thread(). Errors are caught per-handler
and sent to the client as {"type": "error"} messages.

Handlers mutate session state and send JSON to the WebSocket.
They never access module-level globals.
"""

import asyncio
import contextlib

from starlette.websockets import WebSocket

from ..engine import (
    call_recap,
    create_user,
    delete_save,
    delete_user,
    generate_epilogue,
    list_saves_with_info,
    list_users,
    load_game,
    log,
    process_correction,
    process_momentum_burn,
    process_turn,
    reset_stale_reflection_flags,
    run_deferred_director,
    save_game,
    start_new_chapter,
    start_new_game,
)
from ..engine.ai.api_client import get_provider
from ..i18n import t
from .serializers import build_creation_options, build_narrative_status, build_tracks_status, highlight_dialog
from .session import BurnOffer, Session


async def _send(ws: WebSocket, msg: dict) -> None:
    """Send JSON, swallowing errors if the connection is dead."""
    with contextlib.suppress(Exception):
        await ws.send_json(msg)


# ── Player management ─────────────────────────────────────────


async def handle_list_players(session: Session, ws: WebSocket, _msg: dict) -> None:
    players = [u["name"] for u in list_users()]
    await _send(ws, {"type": "players_list", "players": players})


async def handle_create_player(session: Session, ws: WebSocket, msg: dict) -> None:
    name = msg.get("name", "").strip()
    if not name:
        await _send(ws, {"type": "error", "text": "Player name cannot be empty."})
        return
    create_user(name)
    await handle_select_player(session, ws, {"name": name})


async def handle_select_player(session: Session, ws: WebSocket, msg: dict) -> None:
    name = msg.get("name", "").strip()
    if not name:
        await _send(ws, {"type": "error", "text": "No player name provided."})
        return

    session.player = name
    session.save_name = "autosave"

    game, messages = load_game(name, "autosave")
    if game:
        session.game = game
        session.chat_messages = messages
        await _send(
            ws,
            {
                "type": "player_selected",
                "name": name,
                "has_game": True,
                "messages": session.filtered_messages(),
            },
        )
    else:
        session.clear_game()
        await _send(
            ws,
            {
                "type": "player_selected",
                "name": name,
                "has_game": False,
                "creation_options": build_creation_options(),
            },
        )


async def handle_delete_player(session: Session, ws: WebSocket, msg: dict) -> None:
    name = msg.get("name", "").strip()
    if name:
        delete_user(name)
        if session.player == name:
            session.player = ""
            session.clear_game()
    await handle_list_players(session, ws, msg)


# ── Game creation ─────────────────────────────────────────────


async def handle_start_game(session: Session, ws: WebSocket, msg: dict) -> None:
    if session.processing:
        await _send(ws, {"type": "error", "text": t("game.still_processing")})
        return
    session.processing = True
    try:
        creation_data = msg.get("creation_data", {})
        await _send(ws, {"type": "status", "text": t("creation.world_awakens")})

        provider = get_provider()
        game, narration = await asyncio.to_thread(
            start_new_game, provider, creation_data, session.config, session.player
        )

        session.game = game
        session.chat_messages = [{"role": "assistant", "content": narration}]
        save_game(game, session.player, session.chat_messages, session.save_name)

        await _send(
            ws,
            {
                "type": "narration",
                "text": highlight_dialog(narration),
                "scene": game.narrative.scene_count,
                "location": game.world.current_location,
            },
        )
    except Exception as e:
        log(f"[Web] start_game failed: {e}", level="error")
        await _send(ws, {"type": "error", "text": str(e)})
    finally:
        session.processing = False


# ── Turn processing ───────────────────────────────────────────


async def handle_player_input(session: Session, ws: WebSocket, msg: dict) -> None:
    if session.processing:
        await _send(ws, {"type": "error", "text": t("game.still_processing")})
        return
    if not session.game:
        await _send(ws, {"type": "error", "text": "No active game."})
        return

    text = msg.get("text", "").strip()
    if not text:
        return

    session.processing = True
    try:
        session.append_chat("user", text)
        await _send(ws, {"type": "status", "text": "..."})

        provider = get_provider()
        game, narration, roll, burn_info, director_ctx = await asyncio.to_thread(
            process_turn, provider, session.game, text, session.config
        )
        session.game = game
        session.append_chat("assistant", narration)

        await _send(
            ws,
            {
                "type": "scene_marker",
                "scene": game.narrative.scene_count,
                "location": game.world.current_location,
            },
        )
        await _send(
            ws,
            {
                "type": "narration",
                "text": highlight_dialog(narration),
                "scene": game.narrative.scene_count,
                "location": game.world.current_location,
            },
        )

        # Roll data stays engine-internal; player sees only narration
        # (design doc: "no stats, no dice, no system references")

        if burn_info:
            session.pending_burn = BurnOffer(
                roll=burn_info["roll"],
                new_result=burn_info["new_result"],
                cost=burn_info["cost"],
                brain=burn_info["brain"],
                player_words=burn_info["player_words"],
                pre_snapshot=burn_info["pre_snapshot"],
                scene_setup=burn_info.get("scene_setup"),
            )
            await _send(
                ws,
                {
                    "type": "burn_offer",
                    "current": burn_info["roll"].result,
                    "upgrade": burn_info["new_result"],
                    "cost": burn_info["cost"],
                },
            )

        if game.game_over:
            await _send(ws, {"type": "game_over"})
        elif (
            game.narrative.story_blueprint
            and game.narrative.story_blueprint.story_complete
            and not game.campaign.epilogue_dismissed
        ):
            await _send(ws, {"type": "story_complete"})

        save_game(game, session.player, session.chat_messages, session.save_name)

        if director_ctx:
            try:
                await asyncio.to_thread(run_deferred_director, provider, game, director_ctx)
                save_game(game, session.player, session.chat_messages, session.save_name)
            except Exception as e:
                log(f"[Web] Director failed: {e}", level="warning")
        elif any(n.needs_reflection for n in game.npcs):
            reset_stale_reflection_flags(game)

        await _send(ws, {"type": "turn_complete"})

    except Exception as e:
        log(f"[Web] player_input failed: {e}", level="error")
        await _send(ws, {"type": "error", "text": str(e)})
        session.pop_last_user_message()
    finally:
        session.processing = False


# ── Correction ────────────────────────────────────────────────


async def handle_correction(session: Session, ws: WebSocket, msg: dict) -> None:
    if session.processing:
        await _send(ws, {"type": "error", "text": t("game.still_processing")})
        return
    if not session.game:
        return

    text = msg.get("text", "").strip()
    if not text:
        return

    session.processing = True
    try:
        await _send(ws, {"type": "status", "text": "..."})
        provider = get_provider()
        game, narration, director_ctx = await asyncio.to_thread(
            process_correction, provider, session.game, text, session.config
        )
        session.game = game

        await _send(ws, {"type": "replace_narration", "text": highlight_dialog(narration)})

        session.append_chat("user", f"## {text}")
        session.append_chat("assistant", narration)
        save_game(game, session.player, session.chat_messages, session.save_name)

        if director_ctx:
            try:
                await asyncio.to_thread(run_deferred_director, provider, game, director_ctx)
                save_game(game, session.player, session.chat_messages, session.save_name)
            except Exception:
                pass
        await _send(ws, {"type": "turn_complete"})
    except Exception as e:
        log(f"[Web] correction failed: {e}", level="error")
        await _send(ws, {"type": "error", "text": str(e)})
    finally:
        session.processing = False


# ── Momentum burn ─────────────────────────────────────────────


async def handle_burn_momentum(session: Session, ws: WebSocket, msg: dict) -> None:
    if not session.game:
        return

    accept = msg.get("accept", False)
    burn = session.pending_burn
    session.pending_burn = None

    if not accept or not burn:
        return

    session.processing = True
    try:
        await _send(ws, {"type": "status", "text": t("momentum.gathering")})
        provider = get_provider()
        game, narration = await asyncio.to_thread(
            process_momentum_burn,
            provider=provider,
            game=session.game,
            old_roll=burn.roll,
            new_result=burn.new_result,
            brain_data=burn.brain,
            player_words=burn.player_words,
            config=session.config,
            pre_snapshot=burn.pre_snapshot,
            scene_setup=burn.scene_setup,
        )
        session.game = game

        await _send(ws, {"type": "replace_narration", "text": highlight_dialog(narration)})

        session.replace_last_assistant(narration)
        save_game(game, session.player, session.chat_messages, session.save_name)
        await _send(ws, {"type": "turn_complete"})
    except Exception as e:
        log(f"[Web] burn failed: {e}", level="error")
        await _send(ws, {"type": "error", "text": str(e)})
    finally:
        session.processing = False


# ── Saves ─────────────────────────────────────────────────────


async def handle_list_saves(session: Session, ws: WebSocket, _msg: dict) -> None:
    if not session.player:
        return
    saves = list_saves_with_info(session.player)
    await _send(ws, {"type": "saves_list", "saves": saves})


async def handle_save(session: Session, ws: WebSocket, msg: dict) -> None:
    if not session.game or not session.player:
        return
    name = msg.get("name", session.save_name).strip() or session.save_name
    session.save_name = name
    save_game(session.game, session.player, session.chat_messages, name)
    await _send(ws, {"type": "status", "text": t("actions.saved")})


async def handle_load(session: Session, ws: WebSocket, msg: dict) -> None:
    if not session.player:
        return
    name = msg.get("name", "autosave").strip()
    game, messages = load_game(session.player, name)
    if not game:
        await _send(ws, {"type": "error", "text": t("actions.load_failed")})
        return
    session.game = game
    session.chat_messages = messages
    session.save_name = name
    await _send(
        ws,
        {
            "type": "player_selected",
            "name": session.player,
            "has_game": True,
            "messages": session.filtered_messages(),
        },
    )


async def handle_delete_save(session: Session, ws: WebSocket, msg: dict) -> None:
    if not session.player:
        return
    name = msg.get("name", "").strip()
    if name:
        delete_save(session.player, name)
    await handle_list_saves(session, ws, msg)


# ── Recap ─────────────────────────────────────────────────────


async def handle_recap(session: Session, ws: WebSocket, _msg: dict) -> None:
    if not session.game or session.processing:
        return
    session.processing = True
    try:
        await _send(ws, {"type": "status", "text": t("actions.recap_loading")})
        provider = get_provider()
        recap_text = await asyncio.to_thread(call_recap, provider, session.game, session.config)
        await _send(ws, {"type": "recap", "text": recap_text})
    except Exception as e:
        await _send(ws, {"type": "error", "text": str(e)})
    finally:
        session.processing = False


# ── Status query ─────────────────────────────────────────────


async def handle_status_query(session: Session, ws: WebSocket, _msg: dict) -> None:
    if not session.game:
        await _send(ws, {"type": "status", "text": t("status.no_game")})
        return
    text = build_narrative_status(session.game)
    await _send(ws, {"type": "status", "text": text})


async def handle_tracks_query(session: Session, ws: WebSocket, _msg: dict) -> None:
    if not session.game:
        await _send(ws, {"type": "status", "text": t("status.no_game")})
        return
    text = build_tracks_status(session.game)
    await _send(ws, {"type": "status", "text": text})


# ── Epilogue & chapters ──────────────────────────────────────


async def handle_generate_epilogue(session: Session, ws: WebSocket, _msg: dict) -> None:
    if not session.game or session.processing:
        return
    session.processing = True
    try:
        await _send(ws, {"type": "status", "text": t("epilogue.generating")})
        provider = get_provider()
        game, epilogue = await asyncio.to_thread(generate_epilogue, provider, session.game, session.config)
        session.game = game
        session.append_chat("assistant", epilogue, epilogue=True)
        save_game(game, session.player, session.chat_messages, session.save_name)
        await _send(ws, {"type": "epilogue", "text": highlight_dialog(epilogue)})
    except Exception as e:
        await _send(ws, {"type": "error", "text": str(e)})
    finally:
        session.processing = False


async def handle_dismiss_epilogue(session: Session, ws: WebSocket, _msg: dict) -> None:
    if not session.game:
        return
    session.game.campaign.epilogue_dismissed = True
    save_game(session.game, session.player, session.chat_messages, session.save_name)


async def handle_new_chapter(session: Session, ws: WebSocket, _msg: dict) -> None:
    if not session.game or session.processing:
        return
    session.processing = True
    try:
        game = session.game
        ch_num = game.campaign.chapter_number
        await _send(ws, {"type": "status", "text": t("epilogue.chapter_msg", n=ch_num + 1)})

        provider = get_provider()
        game, narration = await asyncio.to_thread(start_new_chapter, provider, game, session.config, session.player)
        session.game = game
        session.chat_messages = [{"role": "assistant", "content": narration}]
        save_game(game, session.player, session.chat_messages, session.save_name)

        await _send(
            ws,
            {
                "type": "chapter_started",
                "chapter": game.campaign.chapter_number,
                "narration": highlight_dialog(narration),
            },
        )
    except Exception as e:
        log(f"[Web] new_chapter failed: {e}", level="error")
        await _send(ws, {"type": "error", "text": str(e)})
    finally:
        session.processing = False


# ── Debug (Elvira integration testing) ────────────────────────


async def handle_debug_state(session: Session, ws: WebSocket, _msg: dict) -> None:
    """Return full serialized GameState for invariant checking.

    Not used by the normal client. Elvira's WebSocket runner sends this
    after each turn to get the complete game state for quality checks
    and invariant assertions.
    """
    if not session.game:
        await _send(ws, {"type": "debug_state", "data": None})
        return
    await _send(ws, {"type": "debug_state", "data": session.game.to_dict()})
