from typing import Any
import asyncio
import copy
from concurrent.futures import Future

from starlette.websockets import WebSocket, WebSocketDisconnect

from ..engine.ai.api_client import get_provider
from ..engine.ai.provider_base import AIUnavailableError
from ..engine.ai.recap import call_recap
from ..engine.ai.sentence_stream import SentenceStream
from ..engine.config_loader import cfg
from ..engine.correction import process_correction
from ..engine.director import reset_stale_reflection_flags
from ..engine.engine_loader import eng
from ..engine.game import (
    BurnOffer,
    determine_end_reason,
    generate_epilogue,
    prepare_succession,
    process_momentum_burn,
    process_turn,
    run_deferred_director,
    start_new_chapter,
    start_new_game,
    start_succession_with_character,
)
from ..engine.logging_util import log
from ..engine.mechanics.legacy import advance_asset
from ..engine.models import GameState, TurnSnapshot
from ..engine.persistence import IncompatibleSaveError, delete_save, list_saves_with_info, load_game, save_game
from ..engine.user_management import InvalidNameError, create_user, delete_user, list_users
from ..i18n import t
from .serializers import (
    build_creation_options,
    build_narrative_status,
    build_succession_summary,
    build_threats_status,
    build_tracks_status,
    highlight_dialog,
)
from .session import Session


async def _send(ws: WebSocket, msg: dict[str, Any]) -> None:
    try:
        await ws.send_json(msg)
    except (WebSocketDisconnect, RuntimeError, OSError) as e:
        log(f"[Web] _send on dead ws ({msg['type']}): {e}", level="debug")


def _text(msg: dict[str, Any], key: str) -> str:
    value = msg.get(key)
    return value.strip() if isinstance(value, str) else ""


async def _require_str(ws: WebSocket, msg: dict[str, Any], key: str, error_key: str) -> str | None:
    value = _text(msg, key)
    if not value:
        await _send(ws, {"type": "error", "text": t(error_key)})
        return None
    return value


def player_selected_message(session: Session) -> dict[str, Any]:
    if session.game is None:
        return {
            "type": "player_selected",
            "name": session.player,
            "has_game": False,
            "creation_options": build_creation_options(),
        }
    return {"type": "player_selected", "name": session.player, "has_game": True, "messages": session.chat_messages}


def _narration_stream(ws: WebSocket, game: GameState) -> tuple[SentenceStream, list[Future[None]]]:
    loop = asyncio.get_running_loop()
    pending: list[Future[None]] = []

    def on_sentence(text: str) -> None:
        msg = {
            "type": "narration_sentence",
            "text": text,
            "scene": game.narrative.scene_count,
            "location": game.world.current_location,
        }
        pending.append(asyncio.run_coroutine_threadsafe(_send(ws, msg), loop))

    return SentenceStream(on_sentence), pending


async def handle_list_players(_session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    players = [u["name"] for u in list_users()]
    await _send(ws, {"type": "players_list", "players": players})


async def handle_create_player(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    name = await _require_str(ws, msg, "name", "error.empty_player_name")
    if name is None:
        return
    try:
        create_user(name)
    except InvalidNameError as e:
        log(f"[User] {e}", level="warning")
        await _send(ws, {"type": "error", "text": t("error.invalid_name")})
        return
    await handle_select_player(session, ws, {"name": name})


async def handle_select_player(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    name = await _require_str(ws, msg, "name", "error.no_player_name")
    if name is None:
        return

    session.player = name
    session.save_name = eng().persistence.default_save_name
    try:
        game, messages = load_game(name, session.save_name)
    except IncompatibleSaveError as e:
        log(f"[Load] {e}", level="warning")
        await _send(ws, {"type": "error", "text": t("actions.save_incompatible")})
        game, messages = None, []
    if game is None:
        session.clear_game()
    else:
        session.game = game
        session.chat_messages = messages
    await _send(ws, player_selected_message(session))


async def handle_delete_player(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    name = await _require_str(ws, msg, "name", "error.no_player_name")
    if name is None:
        return
    delete_user(name)
    if session.player == name:
        session.player = ""
        session.clear_game()
    await handle_list_players(session, ws, msg)


def _error_text(e: Exception) -> str:
    return t("error.ai_unavailable") if isinstance(e, AIUnavailableError) else t("error.unexpected")


async def _report_failure(ws: WebSocket, what: str, e: Exception) -> None:
    log(f"[Web] {what} not applied: {type(e).__name__}: {e}", level="error")
    await _send(ws, {"type": "error", "text": f"{_error_text(e)} {t('error.nothing_changed')}"})


async def handle_start_game(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    if session.processing:
        await _send(ws, {"type": "error", "text": t("game.still_processing")})
        return
    creation_data = msg.get("creation_data")
    if not isinstance(creation_data, dict):
        await _send(ws, {"type": "error", "text": t("succession.error_creation_data_malformed")})
        return
    session.processing = True
    try:
        await _send(ws, {"type": "status", "text": t("creation.world_awakens")})
        try:
            game, narration = await asyncio.to_thread(start_new_game, get_provider(), creation_data)
        except Exception as e:
            await _report_failure(ws, "start_game", e)
            return

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
    finally:
        session.processing = False


def _restore_after_failed_turn(
    game: GameState, snapshot: TurnSnapshot, last_turn_snapshot: TurnSnapshot | None
) -> None:
    game.restore(snapshot)
    game.last_turn_snapshot = last_turn_snapshot


async def _offer_burn(session: Session, ws: WebSocket, offer: BurnOffer | None) -> None:
    if offer is None:
        return
    session.pending_burn = offer
    await _send(
        ws,
        {"type": "burn_offer", "current": offer.roll.result, "upgrade": offer.new_result, "cost": offer.cost},
    )


async def handle_player_input(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    if session.processing:
        await _send(ws, {"type": "error", "text": t("game.still_processing")})
        return
    if not session.game:
        await _send(ws, {"type": "error", "text": t("error.no_active_game")})
        return
    text = _text(msg, "text")
    if not text:
        return

    session.processing = True
    session.pending_burn = None
    try:
        session.append_chat("user", text)
        await _send(ws, {"type": "status", "text": t("game.processing")})

        provider = get_provider()
        stream, pending_sentences = _narration_stream(ws, session.game) if cfg().server.stream_narration else (None, [])
        before, last_before = session.game.snapshot(), copy.deepcopy(session.game.last_turn_snapshot)
        try:
            game, narration, _roll, burn_offer, director_ctx = await asyncio.to_thread(
                process_turn, provider, session.game, text, stream
            )
        except Exception as e:
            _restore_after_failed_turn(session.game, before, last_before)
            session.pop_last_user_message()
            await _report_failure(ws, "turn", e)
            return
        for sent in pending_sentences:
            await asyncio.wrap_future(sent)
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
                "stream_complete": stream is not None and stream.complete,
            },
        )

        await _offer_burn(session, ws, burn_offer)

        if game.game_over:
            if not game.campaign.pending_succession:
                end_reason = determine_end_reason(game)
                await asyncio.to_thread(prepare_succession, game, end_reason)
            await _send(ws, {"type": "game_over", "succession": build_succession_summary(game)})
        elif (
            game.narrative.story_blueprint
            and game.narrative.story_blueprint.story_complete
            and not game.campaign.epilogue_dismissed
        ):
            await _send(ws, {"type": "story_complete"})

        save_game(game, session.player, session.chat_messages, session.save_name)

        if director_ctx:
            await asyncio.to_thread(run_deferred_director, provider, game, director_ctx)
            save_game(game, session.player, session.chat_messages, session.save_name)
        elif any(n.needs_reflection for n in game.npcs):
            reset_stale_reflection_flags(game)

        await _send(ws, {"type": "turn_complete"})
    finally:
        session.processing = False


async def handle_correction(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    if session.processing:
        await _send(ws, {"type": "error", "text": t("game.still_processing")})
        return
    if not session.game:
        return
    text = _text(msg, "text")
    if not text:
        return

    session.processing = True
    session.pending_burn = None
    try:
        await _send(ws, {"type": "status", "text": t("game.processing")})
        provider = get_provider()
        before, last_before = session.game.snapshot(), copy.deepcopy(session.game.last_turn_snapshot)
        try:
            game, narration, burn_offer, director_ctx = await asyncio.to_thread(
                process_correction, provider, session.game, text
            )
        except Exception as e:
            _restore_after_failed_turn(session.game, before, last_before)
            await _report_failure(ws, "correction", e)
            return
        session.game = game

        await _send(ws, {"type": "replace_narration", "text": highlight_dialog(narration)})
        await _offer_burn(session, ws, burn_offer)

        session.append_chat("user", f"## {text}")
        session.append_chat("assistant", narration)
        save_game(game, session.player, session.chat_messages, session.save_name)

        if director_ctx:
            await asyncio.to_thread(run_deferred_director, provider, game, director_ctx)
            save_game(game, session.player, session.chat_messages, session.save_name)
        await _send(ws, {"type": "turn_complete"})
    finally:
        session.processing = False


async def handle_burn_momentum(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    if not session.game:
        return

    accept = bool(msg.get("accept", False))
    burn = session.pending_burn
    session.pending_burn = None

    if not accept or not burn:
        return

    session.processing = True
    try:
        await _send(ws, {"type": "status", "text": t("momentum.gathering")})
        provider = get_provider()
        before, last_before = session.game.snapshot(), copy.deepcopy(session.game.last_turn_snapshot)
        try:
            game, narration, director_ctx = await asyncio.to_thread(process_momentum_burn, provider, session.game, burn)
        except Exception as e:
            _restore_after_failed_turn(session.game, before, last_before)
            await _report_failure(ws, "momentum burn", e)
            return
        session.game = game

        await _send(ws, {"type": "replace_narration", "text": highlight_dialog(narration)})

        session.replace_last_assistant(narration)
        save_game(game, session.player, session.chat_messages, session.save_name)

        if director_ctx:
            await asyncio.to_thread(run_deferred_director, provider, game, director_ctx)
            save_game(game, session.player, session.chat_messages, session.save_name)
        elif any(n.needs_reflection for n in game.npcs):
            reset_stale_reflection_flags(game)

        await _send(ws, {"type": "turn_complete"})
    finally:
        session.processing = False


async def handle_list_saves(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.player:
        return
    saves = list_saves_with_info(session.player)
    await _send(ws, {"type": "saves_list", "saves": saves})


async def handle_save(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    if not session.game or not session.player:
        return

    name = _text(msg, "name") or session.save_name
    try:
        save_game(session.game, session.player, session.chat_messages, name)
    except InvalidNameError as e:
        log(f"[Save] {e}", level="warning")
        await _send(ws, {"type": "error", "text": t("error.invalid_name")})
        return
    session.save_name = name
    await _send(ws, {"type": "status", "text": t("actions.saved")})


async def handle_load(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    if not session.player:
        return

    name = _text(msg, "name") or eng().persistence.default_save_name
    try:
        game, messages = load_game(session.player, name)
    except IncompatibleSaveError as e:
        log(f"[Load] {e}", level="warning")
        await _send(ws, {"type": "error", "text": t("actions.save_incompatible")})
        return
    if game is None:
        await _send(ws, {"type": "error", "text": t("actions.load_failed")})
        return
    session.game = game
    session.chat_messages = messages
    session.save_name = name
    await _send(ws, player_selected_message(session))


async def handle_delete_save(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    if not session.player:
        return
    name = await _require_str(ws, msg, "name", "error.no_player_name")
    if name is None:
        return
    delete_save(session.player, name)
    await handle_list_saves(session, ws, msg)


async def handle_recap(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game or session.processing:
        return
    session.processing = True
    try:
        await _send(ws, {"type": "status", "text": t("actions.recap_loading")})
        recap_text = await asyncio.to_thread(call_recap, get_provider(), session.game)
        await _send(ws, {"type": "recap", "text": recap_text})
    finally:
        session.processing = False


async def handle_status_query(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game:
        await _send(ws, {"type": "status", "text": t("status.no_game")})
        return
    text = build_narrative_status(session.game)
    await _send(ws, {"type": "status", "text": text})


async def handle_tracks_query(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game:
        await _send(ws, {"type": "status", "text": t("status.no_game")})
        return
    text = build_tracks_status(session.game)
    await _send(ws, {"type": "status", "text": text})


async def handle_threats_query(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game:
        await _send(ws, {"type": "status", "text": t("status.no_game")})
        return
    text = build_threats_status(session.game)
    await _send(ws, {"type": "status", "text": text})


async def handle_advance_asset(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    if not session.game:
        await _send(ws, {"type": "status", "text": t("status.no_game")})
        return

    kind = await _require_str(ws, msg, "kind", "advance.usage")
    if kind is None:
        return
    asset_id = await _require_str(ws, msg, "asset_id", "advance.usage")
    if asset_id is None:
        return
    if kind not in ("upgrade", "new"):
        await _send(ws, {"type": "status", "text": t("advance.usage")})
        return
    spent = advance_asset(session.game, asset_id, kind)
    if spent == 0:
        await _send(ws, {"type": "status", "text": t("advance.insufficient")})
        return

    save_game(session.game, session.player, session.chat_messages, session.save_name)
    msg_key = "advance.upgraded" if kind == "upgrade" else "advance.acquired"
    await _send(ws, {"type": "status", "text": t(msg_key, asset=asset_id, cost=spent)})


async def handle_generate_epilogue(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game or session.processing:
        return
    session.processing = True
    try:
        await _send(ws, {"type": "status", "text": t("epilogue.generating")})
        try:
            game, epilogue = await asyncio.to_thread(generate_epilogue, get_provider(), session.game)
        except Exception as e:
            await _report_failure(ws, "epilogue", e)
            return
        session.game = game
        session.append_chat("assistant", epilogue, epilogue=True)
        save_game(game, session.player, session.chat_messages, session.save_name)
        await _send(ws, {"type": "epilogue", "text": highlight_dialog(epilogue)})
    finally:
        session.processing = False


async def handle_dismiss_epilogue(session: Session, _ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game:
        return
    session.game.campaign.epilogue_dismissed = True
    save_game(session.game, session.player, session.chat_messages, session.save_name)


async def handle_new_chapter(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game or session.processing:
        return
    session.processing = True
    try:
        await _send(
            ws, {"type": "status", "text": t("epilogue.chapter_msg", n=session.game.campaign.chapter_number + 1)}
        )
        try:
            game, narration = await asyncio.to_thread(start_new_chapter, get_provider(), copy.deepcopy(session.game))
        except Exception as e:
            await _report_failure(ws, "new chapter", e)
            return
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
    finally:
        session.processing = False


async def handle_retire(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game or session.processing:
        return
    session.processing = True
    try:
        game = session.game
        if game.campaign.pending_succession:
            await _send(ws, {"type": "error", "text": t("succession.error_already_pending")})
            return
        game.game_over = True
        await asyncio.to_thread(prepare_succession, game, "retire")
        save_game(game, session.player, session.chat_messages, session.save_name)
        await _send(ws, {"type": "game_over", "succession": build_succession_summary(game)})
    finally:
        session.processing = False


async def handle_start_succession(session: Session, ws: WebSocket, msg: dict[str, Any]) -> None:
    if not session.game or session.processing:
        return
    if not session.game.campaign.pending_succession:
        await _send(ws, {"type": "error", "text": t("succession.error_no_pending")})
        return
    creation_data = msg.get("creation_data")
    if not isinstance(creation_data, dict):
        await _send(ws, {"type": "error", "text": t("succession.error_creation_data_malformed")})
        return

    session.processing = True
    try:
        await _send(ws, {"type": "status", "text": t("succession.starting")})
        try:
            game, narration = await asyncio.to_thread(
                start_succession_with_character, get_provider(), copy.deepcopy(session.game), creation_data
            )
        except Exception as e:
            await _report_failure(ws, "succession", e)
            return
        session.game = game
        session.chat_messages = [{"role": "assistant", "content": narration}]
        save_game(game, session.player, session.chat_messages, session.save_name)
        await _send(
            ws,
            {
                "type": "succession_started",
                "chapter": game.campaign.chapter_number,
                "narration": highlight_dialog(narration),
            },
        )
    finally:
        session.processing = False


async def handle_request_succession_creation(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game:
        await _send(ws, {"type": "error", "text": t("error.no_active_game")})
        return
    if not session.game.campaign.pending_succession:
        await _send(ws, {"type": "error", "text": t("succession.error_no_pending")})
        return
    await _send(
        ws,
        {
            "type": "succession_creation_options",
            "creation_options": build_creation_options(),
            "current_setting_id": session.game.setting_id,
        },
    )


async def handle_debug_state(session: Session, ws: WebSocket, _msg: dict[str, Any]) -> None:
    if not session.game:
        await _send(ws, {"type": "debug_state", "data": None})
        return
    await _send(ws, {"type": "debug_state", "data": session.game.to_dict()})
