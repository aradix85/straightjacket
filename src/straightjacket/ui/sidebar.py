#!/usr/bin/env python3
"""Sidebar: NPC status, stats, clocks, save/load, and action buttons."""

import asyncio

from nicegui import ui

from ..engine import (
    E, log, GameState, user_default,
    save_game, load_game, list_saves_with_info, delete_save,
    load_chapter_archive, list_chapter_archives,
    copy_chapter_archives,
    get_current_act, call_recap,
)
from ..engine.ai.api_client import get_provider
from ..i18n import (
    t, get_stat_labels, get_disposition_labels, get_time_labels,
    get_story_phase_labels,
)
from .helpers import S, get_engine_config, clean_narration


def render_sidebar_status(game: GameState, session=None) -> None:
    _ = session or S()  # reserved for future per-session sidebar state

    sl = get_stat_labels()
    dl = get_disposition_labels()
    tl = get_time_labels()
    pl = get_story_phase_labels()

    # Player name
    _name_aria = game.player_name.replace('"', '&quot;')
    ui.label(f"{E['mask']} {game.player_name}").classes("text-lg font-bold").props(f'aria-label="{_name_aria}"')
    ui.label(game.character_concept).classes("text-sm text-gray-400 italic")

    # Location & time
    if game.world.current_location:
        time_str = tl.get(game.world.time_of_day, "") if game.world.time_of_day else ""
        loc_text = f"{E['pin']} {game.world.current_location}"
        if time_str:
            loc_text += f" {E['dot']} {time_str}"
        _loc_aria = f"{t('aria.location')}: {game.world.current_location}"
        if time_str:
            _loc_aria += f" {E['dot']} {time_str}"
        _loc_aria = _loc_aria.replace('"', '&quot;')
        ui.label(loc_text).classes("text-sm w-full").style("color: var(--accent)").props(f'aria-label="{_loc_aria}"')

    # Story arc phase
    if game.narrative.story_blueprint and game.narrative.story_blueprint.acts:
        act = get_current_act(game)
        phase_label = pl.get(act.phase, act.phase)
        act_text = f"{E['book']} {t('sidebar.act', n=act.act_number, total=act.total_acts)} {E['dot']} {phase_label}"
        ui.label(act_text).classes("text-xs w-full").style("color: var(--text-secondary)")

    # Chapter
    if game.campaign.chapter_number > 1:
        ui.label(f"{E['book']} {t('sidebar.chapter', n=game.campaign.chapter_number)}").classes(
            "text-xs w-full").style("color: var(--text-secondary)")

    # Stats (grid with momentum)
    ui.separator()
    _stat_specs = [
        (sl['edge'],   game.get_stat('edge')),
        (sl['shadow'], game.get_stat('shadow')),
        (sl['heart'],  game.get_stat('heart')),
        (sl['wits'],   game.get_stat('wits')),
        (sl['iron'],   game.get_stat('iron')),
        (t('sidebar.momentum'), f"{game.resources.momentum}/{game.resources.max_momentum}"),
    ]
    with ui.element('div').classes('stat-grid w-full'):
        for _lbl, _val in _stat_specs:
            with ui.element('div').classes('stat-item'):
                ui.html(str(_lbl)).classes('stat-label').props('aria-hidden="true"')
                ui.html(str(_val)).classes('stat-value').props('aria-hidden="true"')
    ui.separator()

    # Tracks (health, spirit, supply with progress bars)
    for track, label, cls in [
        ("health", f"{E['heart_red']} {t('sidebar.health')}", "health"),
        ("spirit", f"{E['heart_blue']} {t('sidebar.spirit')}", "spirit"),
        ("supply", f"{E['yellow_dot']} {t('sidebar.supply')}", "supply"),
    ]:
        val = int(getattr(game.resources, track))
        pct = max(0, val / 5 * 100)
        ui.label(f"{label}: {val}/5").classes("text-sm font-semibold")
        with ui.element('div').classes('track-bar w-full').props('aria-hidden="true"'):
            ui.element('div').classes(f'track-fill {cls}').style(f'width:{pct:.0f}%')

    # Chaos
    chaos = int(game.world.chaos_factor)
    pct = max(0, chaos / 9 * 100)
    ui.label(f"{E['tornado']} {t('sidebar.chaos')}: {chaos}/9").classes(
        "text-sm font-semibold w-full")
    with ui.element('div').classes('track-bar w-full').props('aria-hidden="true"'):
        ui.element('div').classes('track-fill chaos').style(f'width:{pct:.0f}%')
    if game.crisis_mode:
        ui.label(f"{E['skull']} {t('sidebar.crisis')}").classes(
            "text-xs w-full font-bold").style("color: var(--error)")

    # Design mode JS: chaos ambient + letter pulse + health vignette
    _chaos_js = ("document.body.setAttribute('data-chaos-high','')"
                 if chaos >= 7 else "document.body.removeAttribute('data-chaos-high')")
    _chaos_js += "; _etLetterPulse(" + ("true" if chaos >= 8 else "false") + ");"
    ui.run_javascript(_chaos_js)
    _hv = {5: 0, 4: 0, 3: 0.18, 2: 0.40, 1: 0.62, 0: 0.82}.get(int(game.resources.health), 0)
    ui.run_javascript(f"document.body.style.setProperty('--health-vignette','{_hv}')")

    # Clocks
    active_clocks = [c for c in game.world.clocks
                     if not c.fired]
    if active_clocks:
        ui.separator()
        ui.label(f"{E['clock']} {t('sidebar.clocks')}").classes("text-sm font-semibold w-full")
        for clock in active_clocks:
            filled = int(clock.filled)
            segments = int(clock.segments)
            p = filled / segments * 100
            em = E.get('red_circle', '') if clock.clock_type == "threat" else E.get('purple_circle', '')
            ui.label(f"{em} {clock.name}: {filled}/{segments}").classes("text-xs")
            with ui.element('div').classes('track-bar w-full').props('aria-hidden="true"'):
                ui.element('div').classes('track-fill progress').style(f'width:{p:.0f}%')

    # NPCs
    active_npcs = [n for n in game.npcs if n.status == "active" and n.introduced]
    background_npcs = [n for n in game.npcs if n.status in ("background", "lore") and n.introduced]
    deceased_npcs = [n for n in game.npcs if n.status == "deceased"]

    def _npc_sort_key(n):
        last_scene = max((m.scene for m in n.memory), default=0)
        return (-n.bond, -last_scene)

    def _display_aliases(aliases):
        return [a for a in aliases if len(a) >= 2]

    if active_npcs or background_npcs or deceased_npcs:
        ui.separator()
        bond_label = t("sidebar.bond")
        aka_label = t("sidebar.npc_aka")

        if active_npcs:
            active_npcs.sort(key=_npc_sort_key)
            ui.label(f"{E['people']} {t('sidebar.persons')}").classes("text-sm font-semibold")
            for npc in active_npcs:
                disp = dl.get(npc.disposition, npc.disposition)
                bond_max = npc.bond_max
                with ui.expansion(f"{disp} {E['dash']} {npc.name}").classes("w-full"):
                    _da = _display_aliases(npc.aliases)
                    alias_str = f"{aka_label} {', '.join(_da)}" if _da else ""
                    with ui.element('div').classes('npc-card'):
                        ui.label(f"{bond_label}: {npc.bond}/{bond_max}").classes('npc-meta')
                        if alias_str:
                            ui.label(alias_str).classes('npc-meta').style('font-style:italic')
                        if npc.description:
                            ui.label(npc.description).classes('npc-desc')

        if background_npcs:
            background_npcs.sort(key=_npc_sort_key)
            with ui.expansion(f"{E['people']} {t('sidebar.known_persons')} ({len(background_npcs)})").classes("w-full"):
                for npc in background_npcs:
                    disp = dl.get(npc.disposition, npc.disposition)
                    bond_max = npc.bond_max
                    with ui.expansion(f"{disp} {E['dash']} {npc.name}").classes("w-full").style("opacity:0.75"):
                        _da = _display_aliases(npc.aliases)
                        alias_str = f"{aka_label} {', '.join(_da)}" if _da else ""
                        with ui.element('div').classes('npc-card'):
                            ui.label(f"{bond_label}: {npc.bond}/{bond_max}").classes('npc-meta')
                            if alias_str:
                                ui.label(alias_str).classes('npc-meta').style('font-style:italic')
                            if npc.description:
                                ui.label(npc.description).classes('npc-desc')

        if deceased_npcs:
            with ui.expansion(f"\u2620\ufe0f {t('sidebar.deceased_persons')} ({len(deceased_npcs)})").classes("w-full"):
                for npc in deceased_npcs:
                    ui.label(f"\u2620\ufe0f {npc.name}").classes("text-xs").style(
                        "opacity: 0.4; text-decoration: line-through; padding: 0.15rem 0.5rem")


def render_sidebar_actions(on_switch_user=None) -> None:
    s = S()
    game = s.get("game")
    username = s["current_user"]
    ui.separator()

    # Recap
    recap_status = None

    async def do_recap():
        nonlocal recap_status
        if s.get("processing", False):
            return
        if s["api_key"] and game and len(game.narrative.session_log) >= 2:
            s["processing"] = True
            if recap_status:
                recap_status.text = f"{E['scroll']} {t('actions.recap_loading')}"
                recap_status.set_visibility(True)
            try:
                provider = get_provider(s["api_key"])
                ecfg = get_engine_config()
                recap = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: call_recap(provider, game, ecfg))

                recap_clean = clean_narration(recap)

                s.setdefault("messages", []).append({
                    "role": "assistant",
                    "content": f"{t('actions.recap_prefix')}\n\n{recap_clean}",
                    "recap": True,
                })
                s["_turn_gen"] = s.get("_turn_gen", 0) + 1

                if recap_status:
                    _sr_prefix = (f'<span class="sr-only">{t("aria.recap_says")}</span>'
                                  if s.get("sr_chat", user_default("sr_chat")) else "")
                    recap_status.text = f"{E['scroll']} {_sr_prefix}{recap_clean}"
                    recap_status.set_visibility(True)

            except Exception as e:
                log(f"[Recap] Error: {e}", level="warning")
                if recap_status:
                    recap_status.set_visibility(False)
                ui.notify(t("creation.error", error=e), type="negative")
            finally:
                s["processing"] = False

    ui.button(f"{E['scroll']} {t('actions.recap')}", on_click=do_recap).props(
        "flat dense").classes("w-full")
    recap_status = ui.label("").classes("text-xs text-gray-400 w-full")
    recap_status.set_visibility(False)

    # Save / Load
    ui.separator()
    active = s.get("active_save", "autosave")
    if active:
        active_display = t("actions.autosave") if active == "autosave" else active
        ui.label(t("actions.active_save", name=active_display)).classes("text-xs text-gray-400 w-full")

    # Quick Save
    async def quick_save():
        if game and username:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: save_game(game, username, s.get("messages"), name=active))
            ui.notify(t("actions.saved"), type="positive")

    ui.button(f"{E['floppy']} {t('actions.quick_save')}", on_click=quick_save).props(
        "flat dense").classes("w-full")

    # Save As
    with ui.expansion(f"{E['floppy']} {t('actions.save_as')}").classes("w-full"):
        with ui.row().classes("w-full items-center gap-1"):
            sa_inp = ui.input(t("actions.save_name")).classes("w-full")

            async def save_as():
                name = sa_inp.value.strip()
                if name and game and username:
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: save_game(game, username, s.get("messages"), name=name))
                    if active != "autosave":
                        copy_chapter_archives(username, active, name)
                    s["active_save"] = name
                    ui.notify(t("actions.saved"), type="positive")
                    ui.navigate.reload()

            ui.button(t("actions.save_as_btn"), on_click=save_as).props("flat dense")

    # Load
    saves = list_saves_with_info(username) if username else []
    if saves:
        with ui.expansion(f"{E['floppy']} {t('actions.load_label')}").classes("w-full"):
            ui.label(t("actions.load_title")).classes("text-xs font-semibold w-full")
            for sv in saves:
                sn = sv["name"]
                display = t("actions.autosave") if sn == "autosave" else sn
                is_active = sn == active

                with ui.row().classes("w-full items-center gap-1"):
                    async def load_save(name=sn, is_act=is_active, disp=display):
                        if is_act or not game:
                            await _do_load(name)
                            return
                        with ui.dialog() as dlg, ui.card():
                            ui.label(t("actions.load_confirm", name=disp))
                            with ui.row().classes("gap-4 mt-2"):
                                async def _confirm(n=name):
                                    dlg.close()
                                    await _do_load(n)
                                ui.button(t("user.yes"), on_click=_confirm, color="positive")
                                ui.button(t("user.no"), on_click=dlg.close)
                        dlg.open()

                    async def _do_load(name):
                        loaded, hist = load_game(username, name)
                        if loaded:
                            s["game"] = loaded
                            s["messages"] = hist
                            s["active_save"] = name
                            s["pending_burn"] = None
                            s["viewing_chapter"] = None
                            s["chapter_view_messages"] = None
                            s["_turn_gen"] = s.get("_turn_gen", 0) + 1
                            ui.navigate.reload()
                        else:
                            ui.notify(t("actions.load_failed"), type="negative")

                    btn = ui.button(f"{E['floppy']} {display}", on_click=load_save).props(
                        "flat dense no-caps").classes("flex-grow text-left")
                    if is_active:
                        btn.style("color: var(--success)")

                    # Save info tooltip
                    _si = sv
                    _has_info = any([_si.get("setting_id"), _si.get("setting_genre"),
                                     _si.get("character_concept"),
                                     _si.get("backstory"), _si.get("player_wishes"),
                                     _si.get("content_lines")])
                    if _has_info:
                        import html as html_mod
                        _lines = []
                        if _si.get("setting_id"):
                            _lines.append(f'<b>Setting:</b> {html_mod.escape(str(_si["setting_id"]))}')
                        elif _si.get("setting_genre"):
                            _lines.append(f'<b>{t("save_info.genre")}:</b> {html_mod.escape(str(_si["setting_genre"]))}')
                        if _si.get("character_concept"):
                            _lines.append(f'<b>{t("save_info.concept")}:</b> {html_mod.escape(str(_si["character_concept"]))}')
                        if _si.get("backstory"):
                            _lines.append(f'<b>{t("save_info.backstory")}:</b> {html_mod.escape(str(_si["backstory"])[:120])}')
                        if _si.get("player_wishes"):
                            _lines.append(f'<b>{t("save_info.wishes")}:</b> {html_mod.escape(str(_si["player_wishes"])[:120])}')
                        if _si.get("content_lines"):
                            _lines.append(f'<b>{t("save_info.boundaries")}:</b> {html_mod.escape(str(_si["content_lines"])[:120])}')
                        with ui.button(icon="info_outline").props(
                            f'flat round dense size=sm aria-label="{t("aria.save_info")}"'
                        ).classes("text-gray-400"), ui.menu().props("anchor='top middle' self='bottom middle'"):
                            ui.html('<br>'.join(_lines)).style(
                                "max-width:280px;max-height:320px;overflow-y:auto;"
                                "padding:8px 12px;font-size:0.82rem;line-height:1.45")

                    if sn != "autosave":
                        async def del_save(name=sn):
                            delete_save(username, name)
                            ui.navigate.reload()
                        ui.button(icon="delete_outline", on_click=del_save).props(
                            "flat dense round").classes("text-gray-500")

    # Chapter archives
    if game and game.campaign.chapter_number > 1:
        archives = list_chapter_archives(username, s.get("active_save", "autosave"))
        if archives:
            with ui.expansion(f"{E['book']} {t('actions.chapters')}").classes("w-full"):
                for arch in archives:
                    ch_n = arch.get("chapter", "?")
                    ch_title = arch.get("title", "")
                    ch_label = f"{t('actions.chapter_n', n=ch_n)}"
                    if ch_title:
                        ch_label += f": {ch_title}"

                    def view_chapter(n=ch_n):
                        active_save = s.get("active_save", "autosave")
                        ch_messages, ch_title_loaded = load_chapter_archive(username, active_save, n)
                        if ch_messages:
                            s["viewing_chapter"] = n
                            s["chapter_view_messages"] = ch_messages
                            s["chapter_view_title"] = ch_title_loaded
                            ui.navigate.reload()

                    ui.button(f"{E['book']} {ch_label}", on_click=view_chapter).props(
                        "flat dense no-caps").classes("w-full text-left")

    # New Game
    ui.separator()

    async def new_game():
        if game:
            with ui.dialog() as dlg, ui.card():
                ui.label(t("actions.new_game_confirm"))
                with ui.row().classes("gap-4 mt-2"):
                    async def confirm_new():
                        dlg.close()
                        from ..engine import delete_chapter_archives
                        delete_chapter_archives(username, s.get("active_save", "autosave"))
                        s["game"] = None
                        s["creation"] = None
                        s["pending_burn"] = None
                        s["messages"] = []
                        s["active_save"] = "autosave"
                        s["processing"] = False
                        s["_turn_gen"] = s.get("_turn_gen", 0) + 1
                        s["viewing_chapter"] = None
                        s["chapter_view_messages"] = None
                        ui.navigate.reload()
                    ui.button(t("user.yes"), on_click=confirm_new, color="positive")
                    ui.button(t("user.no"), on_click=dlg.close)
            dlg.open()
        else:
            s["game"] = None
            s["creation"] = None
            s["pending_burn"] = None
            s["messages"] = []
            s["active_save"] = "autosave"
            s["processing"] = False
            s["_turn_gen"] = s.get("_turn_gen", 0) + 1
            s["viewing_chapter"] = None
            s["chapter_view_messages"] = None
            ui.navigate.reload()

    ui.button(t("actions.new_game"), on_click=new_game, color="red").props(
        "flat").classes("w-full")

    # Settings & Help
    from .settings import render_settings
    from .help import render_help
    render_settings()
    render_help()

    # Switch user
    if on_switch_user:
        ui.separator()
        ui.button(f"{E['people']} {t('actions.switch_user')}",
                  on_click=on_switch_user).props("flat dense").classes("w-full")
