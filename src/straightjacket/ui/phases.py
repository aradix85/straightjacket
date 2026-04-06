#!/usr/bin/env python3
"""UI phase functions: login, user selection, main game.

Extracted from app.py. Each phase function receives a PageContext
containing the shared UI elements (header, drawer, footer, content_area)
and callbacks. This breaks the monolithic _show_main_phase closure.
"""

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from nicegui import ui

from ..engine import (
    VERSION,
    E,
    create_user,
    delete_user,
    list_users,
    load_game,
    log,
    user_default,
)
from ..i18n import t
from .chat import render_chat_messages
from .creation import render_creation_flow
from .endgame import (
    render_epilogue,
    render_game_over,
    render_momentum_burn,
)
from .gameplay import process_player_input
from .helpers import (
    S,
    load_user_settings,
    scroll_chat_bottom,
    scroll_to_element,
)
from .sidebar import render_sidebar_actions, render_sidebar_status


@dataclass
class PageContext:
    """Shared UI elements and callbacks for phase functions.
    NiceGUI widget types are not stable across versions — Any is honest."""
    client: Any  # nicegui Client
    header: Any
    drawer: Any
    drawer_content: Any
    footer: Any
    footer_content: Any
    content_area: Any
    hamburger_btn: Any
    # Callbacks
    check_invite_rate_limit: Callable
    record_invite_failure: Callable
    invite_code: str = ""
    # Set by app.py for cross-phase navigation before any phase runs
    show_login: Callable = field(default=lambda: None, repr=False)
    show_user_selection: Callable = field(default=lambda: None, repr=False)
    show_main: Callable = field(default=lambda: None, repr=False)


def _focus_element(css_selector: str, delay_ms: int = 400):
    ui.run_javascript(
        f'setTimeout(() => {{ const el = document.querySelector(\'{css_selector}\');'
        f' if (el) {{ el.focus(); }} }}, {delay_ms});')


# ── Login phase ──────────────────────────────────────────────

def show_login_phase(ctx: PageContext):
    ctx.header.set_value(False)
    ctx.drawer.set_value(False)
    ctx.footer.set_value(False)
    ctx.content_area.clear()
    s = S()
    with ctx.content_area, ui.column().classes("w-full max-w-sm mx-auto mt-20 gap-4 items-center"):
        ui.label(f"{E['swords']} {t('login.title')}").classes(
            "text-2xl font-bold").props(f'aria-label="{t("login.title")}"')
        ui.label(t("user.subtitle")).classes("text-gray-400 italic")
        ui.label(t("login.subtitle")).classes("text-gray-400 text-sm")
        code_inp = ui.input(
            t("login.code_label"), password=True,
            password_toggle_button=True).classes("w-full")
        error_label = ui.label("").classes("text-red-400 text-sm")
        error_label.props('role="alert"')
        error_label.set_visibility(False)

        async def check_code():
            client_ip = ctx.client.ip or "unknown"
            if not ctx.check_invite_rate_limit(client_ip):
                error_label.text = t("login.rate_limited")
                error_label.set_visibility(True)
                return
            if code_inp.value and code_inp.value.strip() == ctx.invite_code:
                s["authenticated"] = True
                if s.get("current_user"):
                    await ctx.show_main()
                else:
                    ctx.show_user_selection()
            else:
                ctx.record_invite_failure(client_ip)
                error_label.text = t("login.error")
                error_label.set_visibility(True)

        code_inp.on("keydown.enter", check_code)
        ui.button(t("login.submit"), on_click=check_code,
                  color="primary").classes("w-full")
    _focus_element('.q-page input', delay_ms=500)


# ── User selection phase ─────────────────────────────────────

def show_user_selection_phase(ctx: PageContext):
    ctx.header.set_value(False)
    ctx.drawer.set_value(False)
    ctx.footer.set_value(False)
    ctx.content_area.clear()
    s = S()

    async def _select_user(name: str):
        s["current_user"] = name
        load_user_settings(name)
        s["user_config_loaded"] = True
        if not s.get("game"):
            loaded, hist = load_game(name, "autosave")
            if loaded:
                s["game"] = loaded
                s["messages"] = hist
                s["active_save"] = "autosave"
        await ctx.show_main()

    with ctx.content_area, ui.column().classes("w-full items-center mt-12"):
        ui.label(t("user.title")).classes("text-3xl font-bold")
        ui.label(t("user.subtitle")).classes("text-gray-400 italic mb-2")
        ui.label(t("user.who_plays")).classes(
            "text-lg mb-8").style("color: var(--text-secondary)")
        users = list_users()
        if users:
            with ui.row().classes("gap-4 flex-wrap justify-center"):
                for user in users:
                    name = user["name"]
                    ui.button(name, on_click=lambda n=name: _select_user(n),
                              color="primary").classes("px-8 py-4 text-lg")
            ui.separator().classes("my-4 w-96")
        with ui.expansion(f"{E['plus']} {t('user.new_player')}",
                          value=len(users) == 0).classes("w-96"):
            inp = ui.input(t("user.name"),
                           placeholder=t("user.name_placeholder")
                           ).props("maxlength=30").classes("w-full")

            async def create():
                n = inp.value.strip()
                if n:
                    if create_user(n):
                        await _select_user(n)
                    else:
                        ui.notify(t("user.exists", name=n), type="negative")

            ui.button(f"{E['checkmark']} {t('user.create')}",
                      on_click=create, color="primary").classes("w-full mt-2")
        if users:
            with ui.expansion(f"{E['gear']} {t('user.manage')}").classes("w-96"):
                names = [u["name"] for u in users]
                sel = ui.select(names, label=t("user.remove_label"),
                                value=names[0]).classes("w-full")

                async def del_user():
                    with ui.dialog() as dlg, ui.card():
                        ui.label(t("user.confirm_delete", name=sel.value))
                        with ui.row():
                            async def _do_delete():
                                delete_user(sel.value)
                                dlg.close()
                                await asyncio.sleep(0.1)
                                ctx.show_user_selection()
                            ui.button(t("user.yes"), on_click=_do_delete,
                                      color="negative")
                            ui.button(t("user.no"), on_click=dlg.close)
                    dlg.open()

                ui.button(f"{E['trash']} {t('user.remove_label')}",
                          on_click=del_user, color="red").classes("w-full mt-2")
        if not s.get("api_key"):
            ui.separator().classes("my-4 w-96")
            ui.label(f"{E['gear']} {t('user.api_hint')}").classes(
                "text-sm text-gray-400 w-96 text-center")
    with contextlib.suppress(RuntimeError):
        _focus_element('.q-page .q-btn', delay_ms=500)


# ── Main game phase ──────────────────────────────────────────

async def show_main_phase(ctx: PageContext):
    s = S()
    if not s.get("user_config_loaded"):
        load_user_settings(s["current_user"])
        s["user_config_loaded"] = True
    with contextlib.suppress(TimeoutError):
        await ui.run_javascript('document.documentElement.lang="en"', timeout=3.0)
    _nf = s.get("narrator_font", "serif")
    with contextlib.suppress(TimeoutError):
        await ui.run_javascript(
            f'document.body.setAttribute("data-narrator-font","{_nf}")', timeout=2.0)
    ctx.hamburger_btn.props(f'aria-label="{t("aria.menu_open")}"')
    ctx.drawer.props(f'aria-label="{t("aria.sidebar")}"')
    ctx.footer.props(f'aria-label="{t("aria.input_area")}"')
    ctx.content_area.props(f'role="main" aria-label="{t("aria.main_content")}"')

    # --- Sidebar ---
    _build_sidebar(ctx, s)

    # --- Content ---
    chat_container, last_scene_id = await _build_content(ctx, s, _nf)

    # --- Footer ---
    _build_footer(ctx, s, chat_container)

    await scroll_chat_bottom(delay_ms=300)
    if last_scene_id:
        await scroll_to_element(last_scene_id)

    ui.run_javascript('''
        setTimeout(() => {
            const targets = ['.q-footer input', '.q-page .choice-btn',
                '.q-page .q-card .q-btn', '.q-page input', '.q-page textarea'];
            for (const sel of targets) {
                const el = document.querySelector(sel);
                if (el && el.offsetParent !== null) { el.focus(); return; }
            }
        }, 600);
    ''')


def _build_sidebar(ctx: PageContext, s):
    """Populate the drawer with sidebar content."""

    async def _handle_switch_user():
        ctx.drawer.set_value(False)
        ctx.footer.set_value(False)
        ctx.header.set_value(False)
        if ctx.invite_code and not s.get("authenticated"):
            ctx.show_login()
        else:
            ctx.show_user_selection()

    ctx.drawer_content.clear()
    with ctx.drawer_content:
        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label(s["current_user"]).classes("text-lg font-semibold")
            ui.button(icon="chevron_left", on_click=ctx.drawer.hide).props(
                f'flat round dense aria-label="{t("aria.menu_close")}"'
            ).classes("text-gray-500 hover:text-white").style(
                "min-width: 44px; min-height: 44px")
        sidebar_status_container = ui.column().classes("w-full")
        game = s.get("game")
        if game:
            with sidebar_status_container:
                render_sidebar_status(game)
        render_sidebar_actions(on_switch_user=_handle_switch_user)
        ui.label(f"v{VERSION}").classes(
            "w-full text-center text-xs mt-4"
        ).style("color: var(--text-secondary); opacity: 0.5")
    ctx.drawer.set_value(False)
    ctx.header.set_value(True)

    # Store refresh callback on session for footer to use
    def _refresh_sidebar(game_obj):
        try:
            sidebar_status_container.clear()
            with sidebar_status_container:
                render_sidebar_status(game_obj, session=s)
        except Exception as e:
            log(f"[Sidebar] Refresh failed: {e}", level="warning")

    s["_sidebar_refresh"] = _refresh_sidebar


async def _build_content(ctx: PageContext, s, narrator_font: str):
    """Build the main content area. Returns (chat_container, last_scene_id)."""
    ctx.content_area.clear()
    chat_container = None
    last_scene_id = None

    with ctx.content_area:
        if not s.get("api_key"):
            ui.label(t("user.api_missing")).classes(
                "text-gray-400 text-center mt-8")
            ctx.footer.set_value(False)
            return None, None

        chat_container = ui.column().classes("chat-scroll w-full")
        _sr_chat = s.get("sr_chat", user_default("sr_chat"))
        _chat_aria_props = f'id="chat-log" aria-label="{t("aria.chat_log")}"'
        if _sr_chat:
            _chat_aria_props += ' role="log" aria-live="polite"'
        chat_container.props(_chat_aria_props)
        s["_chat_container"] = chat_container

        with chat_container:
            viewing_chapter = s.get("viewing_chapter")
            if viewing_chapter:
                ch_title = s.get("chapter_view_title", "")
                banner_text = (
                    t("chapters.viewing_title", n=viewing_chapter, title=ch_title)
                    if ch_title
                    else t("chapters.viewing", n=viewing_chapter))
                with ui.card().classes("w-full mb-2").style(
                        "background: rgba(106,76,147,0.15); "
                        "border: 1px solid var(--accent); border-radius: 8px"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(banner_text).classes("text-sm font-semibold")

                        def _exit_view():
                            s["viewing_chapter"] = None
                            s["chapter_view_messages"] = None
                            s["chapter_view_title"] = None
                            ui.navigate.reload()

                        ui.button(t("chapters.back"), icon="arrow_back",
                                  on_click=_exit_view).props(
                            "flat dense size=sm no-caps").classes("text-xs")

            last_scene_id = render_chat_messages(chat_container)

            # Entity highlighting on page load (Design mode)
            if narrator_font == "highlight" and s.get("game"):
                import json as _json

                from .helpers import build_entity_data
                _ent_data = build_entity_data(s["game"])
                if _ent_data["entities"]:
                    with contextlib.suppress(TimeoutError):
                        await ui.run_javascript(
                            f'setTimeout(()=>_etHighlight('
                            f'{_json.dumps(_ent_data)},false),200)',
                            timeout=3.0)

            if not viewing_chapter:
                if render_momentum_burn():
                    ctx.footer.set_value(False)
                    await scroll_chat_bottom(delay_ms=300)
                    return chat_container, last_scene_id
                if render_game_over():
                    ctx.footer.set_value(False)
                    await scroll_chat_bottom(delay_ms=300)
                    return chat_container, last_scene_id
                if render_epilogue():
                    ctx.footer.set_value(False)
                    await scroll_chat_bottom(delay_ms=300)
                    return chat_container, last_scene_id
                game = s.get("game")
                creation = s.get("creation")
                if (game is None or creation is not None) and render_creation_flow(chat_container):
                    ctx.footer.set_value(False)
                    return chat_container, last_scene_id

                # Orphaned input retry
                _msgs = s.get("messages", [])
                if (game and _msgs and _msgs[-1].get("role") == "user"
                        and not s.get("processing")):
                    _orphan_text = _msgs[-1].get("content", "")
                    if _orphan_text:
                        _sr_ref = s.get("_sidebar_refresh")
                        with ui.card().classes("w-full p-3 mt-2").style(
                                "background: rgba(217,119,6,0.08); "
                                "border: 1px solid var(--accent-border)"):
                            ui.label(t("game.retry_orphan")).classes("text-sm")
                            _ot = _orphan_text
                            _cc_ref = chat_container

                            async def _retry_orphan():
                                await process_player_input(
                                    _ot, _cc_ref,
                                    sidebar_refresh=_sr_ref, is_retry=True)

                            ui.button(
                                f"{E['refresh']} {t('game.retry_btn')}",
                                on_click=_retry_orphan,
                                color="primary").classes("mt-1")

    return chat_container, last_scene_id


def _build_footer(ctx: PageContext, s, chat_container):
    """Build the footer: chapter nav, game input, or hidden."""
    viewing_chapter = s.get("viewing_chapter")
    game = s.get("game")
    _refresh_sidebar = s.get("_sidebar_refresh")

    if viewing_chapter and chat_container:
        ctx.footer_content.clear()
        with ctx.footer_content, ui.row().classes(
                "w-full items-center justify-center gap-3 rpg-input-bar"
        ).style("padding: 0.5rem 1rem"):
            ch_title = s.get("chapter_view_title", "")
            if ch_title:
                ui.label(ch_title).classes("text-sm").style(
                    "color: var(--text-secondary); opacity: 0.7")

            def _exit_view_footer():
                s["viewing_chapter"] = None
                s["chapter_view_messages"] = None
                s["chapter_view_title"] = None
                ui.navigate.reload()

            ui.button(f"{t('chapters.back')}", icon="arrow_back",
                      on_click=_exit_view_footer).props(
                "flat dense no-caps").classes("text-sm")
        ctx.footer.set_value(True)
        ui.run_javascript(
            'setTimeout(() => { window._rpgAlignFooter && '
            'window._rpgAlignFooter(); }, 200)')

    elif game and not game.game_over and chat_container:
        ctx.footer_content.clear()
        with ctx.footer_content, ui.row().classes(
                "w-full items-center gap-2 rpg-input-bar"
        ).style("padding: 0.5rem 1rem"):
            inp = ui.input(
                placeholder=t("game.input_placeholder")
            ).classes("flex-grow").props(
                f'outlined dense dark '
                f'aria-label="{t("game.input_placeholder")}"')
            _cc = chat_container
            _sr = _refresh_sidebar

            async def send():
                txt = inp.value
                if txt and txt.strip():
                    inp.value = ""
                    await process_player_input(
                        txt.strip(), _cc, sidebar_refresh=_sr)

            inp.on("keydown.enter", send)
            ui.button(icon="send", on_click=send).props(
                f'flat dense aria-label="{t("aria.send_message")}"'
            ).classes("text-gray-400 hover:text-white").style(
                "border: 1px solid var(--border-light); "
                "border-radius: 8px; min-width: 44px; height: 44px")
        ctx.footer.set_value(True)
        _inject_footer_alignment_js()
    else:
        ctx.footer.set_value(False)


def _inject_footer_alignment_js():
    """Inject JS that aligns the input bar to the content column width."""
    ui.run_javascript('''
        window._rpgAlignFooter = function() {
            const pageCol = document.querySelector('.q-page .max-w-4xl');
            const inputBars = document.querySelectorAll('.rpg-input-bar');
            if (pageCol && inputBars.length) {
                const rect = pageCol.getBoundingClientRect();
                inputBars.forEach(bar => {
                    const parentRect = bar.parentElement.getBoundingClientRect();
                    bar.style.maxWidth = rect.width + 'px';
                    bar.style.marginLeft = (rect.left - parentRect.left) + 'px';
                });
            }
        };
        setTimeout(window._rpgAlignFooter, 200);
        if (!window._rpgFooterListeners) {
            window._rpgFooterListeners = true;
            window.addEventListener('resize',
                () => window._rpgAlignFooter && window._rpgAlignFooter());
            if (window.visualViewport) {
                window.visualViewport.addEventListener('resize',
                    () => { window._rpgAlignFooter && window._rpgAlignFooter(); });
                window.visualViewport.addEventListener('scroll',
                    () => { window._rpgAlignFooter && window._rpgAlignFooter(); });
            }
            new MutationObserver(
                () => setTimeout(
                    () => window._rpgAlignFooter && window._rpgAlignFooter(), 350))
                .observe(document.querySelector('.q-layout') || document.body,
                         {attributes: true, attributeFilter: ['style']});
        }
    ''')
