#!/usr/bin/env python3
"""Endgame UI: momentum burn, epilogue, game over."""

import asyncio
import contextlib

from nicegui import ui

from ..engine import (
    E,
    RollResult,
    delete_chapter_archives,
    generate_epilogue,
    log,
    process_momentum_burn,
    save_chapter_archive,
    save_game,
    start_new_chapter,
)
from ..engine.ai.api_client import get_provider
from ..i18n import t
from .helpers import (
    S,
    build_roll_data,
    get_engine_config,
    scroll_chat_bottom,
)


def render_momentum_burn() -> bool:
    s = S()
    bd = s.get("pending_burn")
    if not bd:
        return False
    rd_raw = bd["roll"]
    roll = RollResult(**rd_raw) if isinstance(rd_raw, dict) else rd_raw
    nr = bd["new_result"]
    pre_momentum = bd.get("pre_snapshot", {}).get("momentum", bd["cost"])
    rl = t("momentum.weak_hit") if nr == "WEAK_HIT" else t("momentum.strong_hit")
    with ui.card().classes("w-full p-4").style(
        "background: var(--accent-dim); border: 1px solid var(--accent)") as burn_card:
        burn_card.props('role="alertdialog"')
        ui.markdown(t("momentum.question", cost=pre_momentum, result=rl))
        with ui.row().classes("gap-4 mt-4") as btn_row:
            async def burn():
                try:
                    btn_row.set_visibility(False)
                    with burn_card:
                        burn_spinner = ui.row().classes("w-full items-center gap-2")
                        burn_spinner.props('role="status"')
                        with burn_spinner:
                            ui.spinner("dots", size="lg")
                            ui.label(t("momentum.gathering")).classes("text-sm").style(
                                "color: var(--text-secondary)")
                    await scroll_chat_bottom()
                    config = get_engine_config()
                    username = s["current_user"]
                    provider = get_provider(api_key=s["api_key"])
                    game, narration = await asyncio.to_thread(
                        process_momentum_burn, provider, s["game"], roll, nr, bd["brain"],
                        player_words=bd.get("player_words", ""), config=config,
                        pre_snapshot=bd.get("pre_snapshot"),
                        chaos_interrupt=bd.get("chaos_interrupt"))
                    s["game"] = game
                    s["pending_burn"] = None
                    ur = RollResult(roll.d1, roll.d2, roll.c1, roll.c2, roll.stat_name,
                                    roll.stat_value, roll.action_score, nr, roll.move,
                                    getattr(roll, "match", roll.c1 == roll.c2))
                    ll = game.narrative.session_log[-1] if game.narrative.session_log else None
                    rd = build_roll_data(ur,
                                         consequences=ll.consequences if ll else [],
                                         clock_events=ll.clock_events if ll else [],
                                         brain=bd["brain"],
                                         chaos_interrupt=ll.chaos_interrupt if ll else "")
                    msgs = s["messages"]
                    if msgs and msgs[-1].get("role") == "assistant":
                        msgs[-1] = {
                            "role": "assistant",
                            "content": f"*{E['fire']} {t('momentum.gathering')}*\n\n{narration}",
                            "roll_data": rd,
                        }
                    save_game(game, username, s["messages"], s.get("active_save", "autosave"))
                    # VHS rewind effect (Design mode)
                    if s.get("narrator_font") == "highlight":
                        try:
                            await ui.run_javascript('''
                                (function(){
                                    var style = document.createElement('style');
                                    style.textContent =
                                        '@keyframes _rw_lines{0%{background-position:0 0;opacity:0.85}40%{opacity:1}100%{background-position:0 -300px;opacity:0}}' +
                                        '@keyframes _rw_flash{0%,100%{opacity:0}8%{opacity:0.9}20%{opacity:0.3}50%{opacity:0.6}80%{opacity:0.15}}' +
                                        '@keyframes _rw_chrom{0%{opacity:0;transform:translateY(0)}15%{opacity:1}100%{opacity:0;transform:translateY(-8px)}}' +
                                        '._rw_wrap{position:fixed;inset:0;z-index:99999;pointer-events:none;overflow:hidden}' +
                                        '._rw_lines{position:absolute;inset:0;background:repeating-linear-gradient(to bottom,transparent 0px,transparent 3px,rgba(255,255,255,0.045) 3px,rgba(255,255,255,0.045) 4px);background-size:100% 4px;animation:_rw_lines 0.6s linear forwards}' +
                                        '._rw_flash{position:absolute;inset:0;background:linear-gradient(180deg,rgba(220,180,80,0) 0%,rgba(220,180,80,0.55) 40%,rgba(220,180,80,0) 100%);animation:_rw_flash 0.55s ease forwards}' +
                                        '._rw_chrom{position:absolute;inset:0;background:linear-gradient(180deg,transparent 30%,rgba(150,220,255,0.12) 50%,rgba(255,200,100,0.1) 52%,transparent 70%);animation:_rw_chrom 0.55s ease forwards}';
                                    document.head.appendChild(style);
                                    var wrap = document.createElement('div');
                                    wrap.className = '_rw_wrap';
                                    wrap.innerHTML = '<div class="_rw_lines"></div><div class="_rw_flash"></div><div class="_rw_chrom"></div>';
                                    document.body.appendChild(wrap);
                                    setTimeout(function(){ wrap.remove(); style.remove(); }, 750);
                                })();
                            ''', timeout=3.0)
                            await asyncio.sleep(0.55)
                        except Exception:
                            pass
                    ui.navigate.reload()
                except Exception as e:
                    btn_row.set_visibility(True)
                    with contextlib.suppress(Exception):
                        burn_spinner.delete()
                    ui.notify(t("game.error", error=e), type="negative")

            ui.button(f"{E['fire']} {t('momentum.yes')}", on_click=burn, color="primary")

            def decline():
                s["pending_burn"] = None
                ui.navigate.reload()
            ui.button(t("momentum.no"), on_click=decline)
    return True


def _make_chapter_action(game, chapter_msg_key: str):
    """Create async new-chapter and sync full-restart callbacks."""
    s = S()

    async def new_ch():
        if not s.get("api_key", "").strip():
            ui.notify(t("game.invalid_api_key"), type="negative")
            return
        loading_dlg = ui.dialog().props("persistent")
        with loading_dlg, ui.card().classes("items-center p-6").style(
            "background: var(--bg-surface); min-width: 260px"):
            ui.spinner("dots", size="lg", color="primary")
            ui.label(t(chapter_msg_key, n=game.campaign.chapter_number + 1)).classes(
                "text-sm mt-2").style("color: var(--text-secondary)")
        loading_dlg.open()
        try:
            config = get_engine_config()
            username = s["current_user"]
            provider = get_provider(api_key=s["api_key"])
            g, n = await asyncio.to_thread(start_new_chapter, provider, game, config, username)
            loading_dlg.close()
            completed_ch = g.campaign.chapter_number - 1
            ch_title = ""
            if g.campaign.campaign_history:
                ch_title = g.campaign.campaign_history[-1].title
            active_save = s.get("active_save", "autosave")
            try:
                save_chapter_archive(username, active_save, completed_ch, s["messages"],
                                     title=ch_title)
            except Exception as arch_e:
                log(f"[ChapterArchive] Failed to archive chapter {completed_ch}: {arch_e}",
                    level="warning")
            s["viewing_chapter"] = None
            s["chapter_view_messages"] = None
            s["game"] = g
            s["pending_burn"] = None
            ch = g.campaign.chapter_number
            s["messages"] = [
                {"scene_marker": t("game.scene_marker", n=1,
                                    location=g.world.current_location)},
                {"role": "assistant",
                 "content": f"*{E['book']} {t(chapter_msg_key, n=ch)}*\n\n{n}"},
            ]
            save_game(g, username, s["messages"], s.get("active_save", "autosave"))
            ui.navigate.reload()
        except Exception as e:
            loading_dlg.close()
            log(f"[Chapter] Error starting new chapter: {e}", level="warning")
            ui.notify(t("game.error", error=e), type="negative")

    def full_new():
        delete_chapter_archives(s["current_user"], s.get("active_save", "autosave"))
        s["game"] = None
        s["creation"] = None
        s["messages"] = []
        s["active_save"] = "autosave"
        s["viewing_chapter"] = None
        s["chapter_view_messages"] = None
        ui.navigate.reload()

    return new_ch, full_new


def render_epilogue() -> bool:
    s = S()
    game = s.get("game")
    if not game or game.game_over:
        return False
    bp = game.narrative.story_blueprint

    if game.campaign.epilogue_shown:
        with ui.card().classes("w-full p-4").style(
            "background: rgba(217,119,6,0.1); border: 1px solid rgba(217,119,6,0.4)"):
            ui.markdown(f"{E['star']} **{t('epilogue.done_title')}**")
            ui.label(t("epilogue.done_text")).classes("text-sm mt-1")
            with ui.row().classes("gap-4 mt-4"):
                new_ch, full_new = _make_chapter_action(game, "epilogue.chapter_msg")
                ui.button(f"{E['refresh']} {t('epilogue.new_chapter')}",
                          on_click=new_ch, color="primary")
                ui.button(f"{E['trash']} {t('epilogue.restart')}", on_click=full_new)
        return True

    if bp is not None and bp.story_complete and not game.campaign.epilogue_dismissed:
        with ui.card().classes("w-full p-4").style(
            "background: rgba(217,119,6,0.08); border: 1px solid rgba(217,119,6,0.3)"):
            ui.markdown(f"{E['star']} **{t('epilogue.offer_title')}**")
            ui.label(t("epilogue.offer_text")).classes("text-sm mt-1")
            btn_row = ui.row().classes("gap-4 mt-4")
            with btn_row:
                async def gen_epilogue():
                    btn_row.clear()
                    with btn_row:
                        ui.spinner(size="sm")
                        ui.label(t("epilogue.generating")).classes("text-sm")
                    try:
                        config = get_engine_config()
                        username = s["current_user"]
                        provider = get_provider(api_key=s["api_key"])
                        g, epilogue_text = await asyncio.to_thread(
                            generate_epilogue, provider, game, config)
                        s["game"] = g
                        s["messages"].append(
                            {"scene_marker": f"{E['star']} {t('epilogue.marker')}"})
                        s["messages"].append({"role": "assistant", "content": epilogue_text})
                        save_game(g, username, s["messages"], s.get("active_save", "autosave"))
                        ui.navigate.reload()
                    except Exception as e:
                        btn_row.clear()
                        with btn_row:
                            ui.button(f"{E['star']} {t('epilogue.generate')}",
                                      on_click=gen_epilogue, color="primary")

                            def dismiss():
                                game.campaign.epilogue_dismissed = True
                                save_game(game, s["current_user"], s["messages"],
                                          s.get("active_save", "autosave"))
                                ui.navigate.reload()
                            ui.button(t("epilogue.continue"), on_click=dismiss).props("flat")
                        ui.notify(t("game.error", error=e), type="negative")

                ui.button(f"{E['star']} {t('epilogue.generate')}",
                          on_click=gen_epilogue, color="primary")

                def dismiss():
                    game.campaign.epilogue_dismissed = True
                    save_game(game, s["current_user"], s["messages"],
                              s.get("active_save", "autosave"))
                    ui.navigate.reload()
                ui.button(t("epilogue.continue"), on_click=dismiss).props("flat")
    return False


def render_game_over() -> bool:
    s = S()
    game = s.get("game")
    if not game or not game.game_over:
        return False
    if s.get("narrator_font") == "highlight":
        _icon = E.get("skull", "\U0001f480")
        _sub = game.player_name
        _flavor = t("gameover.flavor")
        ui.run_javascript(f'''
            if (!document.querySelector('._go_overlay')) {{
                var d = document.createElement('div');
                d.className = '_go_overlay';
                d.innerHTML = '<span class="_go_skull">{_icon}</span>'
                    + '<span class="_go_title">GAME OVER</span>'
                    + '<span class="_go_sub">{_sub}</span>'
                    + '<div class="_go_line"></div>'
                    + '<span class="_go_flavor">{_flavor}</span>';
                document.body.appendChild(d);
            }}
        ''')
    with ui.card().classes("w-full p-4").style(
        "background: rgba(220,38,38,0.1); border: 1px solid rgba(220,38,38,0.4)"):
        ui.markdown(f"{t('gameover.title')} {t('gameover.dark')}")
        with ui.row().classes("gap-4 mt-4"):
            new_ch, full_new = _make_chapter_action(game, "gameover.chapter_msg")
            ui.button(f"{E['refresh']} {t('gameover.new_chapter')}",
                      on_click=new_ch, color="primary")
            ui.button(f"{E['trash']} {t('gameover.restart')}", on_click=full_new)
    return True
