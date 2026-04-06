#!/usr/bin/env python3
"""Gameplay: turn processing UI (input → engine → render)."""

import asyncio
from dataclasses import asdict

from nicegui import ui

from ..engine import (
    E,
    GameState,
    log,
    process_correction,
    process_turn,
    reset_stale_reflection_flags,
    run_deferred_director,
    save_game,
    user_default,
)
from ..engine.ai.api_client import get_provider
from ..i18n import t
from .chat import render_chat_messages, render_dice_display
from .helpers import (
    S,
    build_entity_data,
    build_roll_data,
    clean_narration,
    get_engine_config,
    highlight_dialog,
    scroll_chat_bottom,
    scroll_to_element,
)
import contextlib


async def process_player_input(text: str, chat_container, sidebar_container=None,
                               sidebar_refresh=None, is_retry: bool = False) -> None:
    s = S()
    game = s.get("game")
    if not game or not text.strip():
        return
    assert isinstance(game, GameState)
    if s.get("processing", False):
        ui.notify(t("game.still_processing"), type="warning", position="top")
        return
    s["processing"] = True
    turn_gen = s.get("_turn_gen", 0)
    config = get_engine_config()
    username = s["current_user"]

    if not is_retry:
        _is_corr_input = text.startswith("##")
        display_text = text[2:].strip() if _is_corr_input else text
        msg_entry: dict[str, str | bool] = {"role": "user", "content": display_text}
        if _is_corr_input:
            msg_entry["correction_input"] = True
        s["messages"].append(msg_entry)
        with chat_container:
            css_corr = " correction" if _is_corr_input else ""
            _user_col = ui.column().classes(f"chat-msg user{css_corr} w-full")
            if not s.get("sr_chat", user_default("sr_chat")):
                _user_col.props('aria-hidden="true"')
            with _user_col:
                _sr_prefix = (f'<span class="sr-only">{t("aria.player_says")}</span>'
                              if s.get("sr_chat", user_default("sr_chat")) else "")
                ui.markdown(f"{_sr_prefix}{display_text}")

    try:
        with chat_container:
            spinner = ui.spinner("dots", size="lg")
            spinner.props('role="status" aria-label="{}"'.format(t("aria.loading")))
        await scroll_chat_bottom()
        with contextlib.suppress(TimeoutError):
            await ui.run_javascript(
                'document.querySelectorAll("audio").forEach(a=>{a.pause();a.currentTime=0})',
                timeout=3.0)
        provider = get_provider(api_key=s["api_key"])

        if text.startswith("##"):
            if not game.last_turn_snapshot:
                with contextlib.suppress(Exception):
                    spinner.delete()
                ui.notify(t("correction.no_snapshot"), type="warning", position="top")
                s["processing"] = False
                return
            correction_text = text[2:].strip()
            game, narration, director_ctx = await asyncio.to_thread(
                process_correction, provider, game, correction_text, config)
            roll, burn_info = None, None
            _is_correction = True
        else:
            game, narration, roll, burn_info, director_ctx = await asyncio.to_thread(
                process_turn, provider, game, text, config)
            _is_correction = False

        if s.get("_turn_gen", 0) != turn_gen:
            log(f"[Turn] Discarding stale response (gen {turn_gen} -> {s.get('_turn_gen', 0)})")
            with contextlib.suppress(Exception):
                spinner.delete()
            return

        assert isinstance(game, GameState)  # Narrowing for mypy — engine calls always return GameState
        s["game"] = game
        spinner.delete()

        if sidebar_refresh is not None:
            try:
                sidebar_refresh(game)
            except Exception as e:
                log(f"[Sidebar] Full refresh failed: {e}", level="warning")

        if not _is_correction and game.narrative.scene_count > 1:
            s["messages"].append({"scene_marker": t("game.scene_marker", n=game.narrative.scene_count,
                                                     location=game.world.current_location)})

        roll_data = None
        if roll:
            ll = game.narrative.session_log[-1] if game.narrative.session_log else None
            roll_data = build_roll_data(
                roll,
                consequences=ll.consequences if ll else [],
                clock_events=ll.clock_events if ll else [],
                brain={"position": ll.position if ll else "risky",
                       "effect": ll.effect if ll else "standard"},
                chaos_interrupt=ll.chaos_interrupt if ll else "")

        if _is_correction:
            # Sync scene marker if location changed during correction
            for i in range(len(s["messages"]) - 1, -1, -1):
                if s["messages"][i].get("scene_marker"):
                    s["messages"][i]["scene_marker"] = t(
                        "game.scene_marker",
                        n=game.narrative.scene_count,
                        location=game.world.current_location)
                    break
            for i in range(len(s["messages"]) - 1, -1, -1):
                if s["messages"][i].get("role") == "assistant":
                    s["messages"][i] = {"role": "assistant", "content": narration,
                                        "roll_data": roll_data, "corrected": True}
                    break
            for i in range(len(s["messages"]) - 1, -1, -1):
                if s["messages"][i].get("correction_input"):
                    s["messages"].pop(i)
                    break
        else:
            s["messages"].append({"role": "assistant", "content": narration,
                                  "roll_data": roll_data})

        if _is_correction:
            with contextlib.suppress(TimeoutError):
                await ui.run_javascript('''
                    const msgs = document.querySelectorAll('.chat-msg.user.correction');
                    const last = msgs[msgs.length - 1];
                    if (last) {
                        last.style.transition = 'opacity 0.5s ease-out';
                        last.style.opacity = '0';
                    }
                ''', timeout=3.0)
            await asyncio.sleep(0.6)
            chat_container.clear()
            with chat_container:
                scroll_target_id = render_chat_messages(chat_container)
        else:
            scroll_target_id = f"msg-{len(s['messages'])}"
            _is_highlight = s.get("narrator_font") == "highlight"
            with chat_container:
                if game.narrative.scene_count > 1:
                    ui.html(f'<h2 id="{scroll_target_id}" class="scene-marker">'
                            f'{E["dash"]} {t("game.scene_marker", n=game.narrative.scene_count, location=game.world.current_location)} '
                            f'{E["dash"]}</h2>')
                else:
                    ui.html(f'<div id="{scroll_target_id}"></div>')
                _et_new = " et-new" if _is_highlight else ""
                _chaos_cls = " et-chaos" if (not _is_correction and game.narrative.session_log
                                             and game.narrative.session_log[-1].chaos_interrupt) else ""
                msg_col = ui.column().classes(f"chat-msg assistant{_et_new}{_chaos_cls} w-full")
                if not s.get("sr_chat", user_default("sr_chat")):
                    msg_col.props('aria-hidden="true"')
                with msg_col:
                    _sr_prefix = (f'<span class="sr-only">{t("aria.narrator_says")}</span>'
                                  if s.get("sr_chat", user_default("sr_chat")) else "")
                    _display = clean_narration(narration)
                    if _is_highlight:
                        _display = highlight_dialog(_display)
                    ui.markdown(f"{_sr_prefix}{_display}")
                    if roll_data:
                        render_dice_display(roll_data)
            # Entity highlighting (Design mode): inject after markdown render
            if _is_highlight:
                import json as _json
                _ent_data = build_entity_data(game)
                if _ent_data["entities"]:
                    with contextlib.suppress(TimeoutError):
                        await ui.run_javascript(
                            f'_etHighlight({_json.dumps(_ent_data)}, true)',
                            timeout=3.0)

        await scroll_chat_bottom()
        if scroll_target_id:
            await scroll_to_element(scroll_target_id)

        save_game(game, username, s["messages"], s.get("active_save", "autosave"))

        # Director — awaited inline (not background task) to prevent race condition.
        # Processing flag is still active, so the send button stays disabled.
        if director_ctx and not burn_info:
            try:
                await asyncio.to_thread(run_deferred_director, provider, game, director_ctx)
                # Guard: if user switched games during the ~1s Director call, don't save
                if s.get("_turn_gen", 0) == turn_gen:
                    save_game(game, username, s["messages"], s.get("active_save", "autosave"))
                    log("[Director] Inline save complete")
            except Exception as e:
                log(f"[Director] Inline call failed: {e}", level="warning")
        elif director_ctx and burn_info:
            # Burn pending — Director skipped (turn will be re-narrated).
            # Reset reflection flags so they don't accumulate.
            reset_stale_reflection_flags(game)
            log("[Director] Skipped (burn pending), reflection flags reset")

        # Burn or story completion reload
        if burn_info:
            burn_info["roll"] = asdict(burn_info["roll"])
            s["pending_burn"] = burn_info
            ui.navigate.reload()
        else:
            bp = game.narrative.story_blueprint
            if game.game_over or (bp is not None and bp.story_complete
                                  and not game.campaign.epilogue_dismissed
                                  and not game.campaign.epilogue_shown):
                ui.navigate.reload()

    except Exception as e:
        # Check for authentication errors from any provider
        is_auth_error = (
            "authentication" in type(e).__name__.lower()
            or "auth" in type(e).__name__.lower()
            or getattr(e, "status_code", None) == 401
        )
        if is_auth_error:
            with contextlib.suppress(Exception):
                spinner.delete()
            ui.notify(t("game.invalid_api_key"), type="negative")
            return
        with contextlib.suppress(Exception):
            spinner.delete()
        _retry_text = text
        _retry_cc = chat_container
        _retry_sr = sidebar_refresh
        with chat_container:
            retry_row = ui.row().classes("w-full items-center gap-2 py-1 px-3").style(
                "background: rgba(255,80,80,0.1); border: 1px solid rgba(255,80,80,0.3); "
                "border-radius: 8px; margin: 0.25rem 0")
            retry_row.props('role="alert"')
            with retry_row:
                err_short = str(e)[:120]
                ui.label(f"{E['warn']} {err_short}").classes(
                    "text-xs text-red-300 flex-grow").style("word-break: break-word")

                async def _do_retry(rr=retry_row, rt=_retry_text, rc=_retry_cc, rs=_retry_sr):
                    with contextlib.suppress(Exception):
                        rr.delete()
                    await process_player_input(rt, rc, sidebar_refresh=rs, is_retry=True)
                ui.button(icon="refresh", on_click=_do_retry).props(
                    f'flat dense round aria-label="{t("aria.retry")}"').classes(
                    "text-red-300 hover:text-white").style(
                    "min-width: 40px; min-height: 40px").tooltip(t("game.retry_tooltip"))
    finally:
        if s.get("_turn_gen", 0) == turn_gen:
            s["processing"] = False

