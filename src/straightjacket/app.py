#!/usr/bin/env python3
"""
Edge Tales - Narrative Solo RPG Engine
========================================
NiceGUI server entry point — page skeleton and phase routing.
All rendering is delegated to modules in the ui/ subpackage.
Phase logic (login, user selection, main game) lives in ui/phases.py.
"""

from .ui.server import ensure_requirements

_dep_check = ensure_requirements()

import asyncio
import os
import threading
import time as _time
from pathlib import Path

from nicegui import Client, app, ui

from .engine import (
    cfg,
    log,
    setup_file_logging,
)
from .i18n import t
from .ui import settings as settings_module
from .ui.helpers import (
    S,
    init_session,
)
from .ui.helpers import (
    configure as configure_helpers,
)
from .ui.phases import (
    PageContext,
    show_login_phase,
    show_main_phase,
    show_user_selection_phase,
)
from .ui.server import (
    generate_self_signed_cert,
    generate_touch_icon,
    get_storage_secret,
    load_server_config,
)

# ── Server config ────────────────────────────────────────────

_server_cfg = load_server_config()
INVITE_CODE: str = _server_cfg["invite_code"]
SERVER_API_KEY: str = _server_cfg["api_key"]
ENABLE_HTTPS: bool = _server_cfg["enable_https"]
SSL_CERTFILE: str = _server_cfg["ssl_certfile"]
SSL_KEYFILE: str = _server_cfg["ssl_keyfile"]
SERVER_PORT: int = _server_cfg["port"]

configure_helpers(server_api_key=SERVER_API_KEY)
settings_module.configure(server_api_key=SERVER_API_KEY)

log(f"[Config] port={SERVER_PORT}, https={ENABLE_HTTPS}, "
    f"invite={'set' if INVITE_CODE else 'off'}, "
    f"api_key={'config' if SERVER_API_KEY else ('ENV' if os.environ.get(cfg().ai.api_key_env) else 'not set')}")

# Flush deferred dependency check results
import contextlib

if _dep_check:
    log(f"[Deps] Found: {', '.join(_dep_check['found'])}")
    if _dep_check["optional_found"]:
        log(f"[Deps] Optional: {', '.join(_dep_check['optional_found'])}")
    if _dep_check["optional_missing"]:
        log(f"[Deps] Optional (not installed): {', '.join(_dep_check['optional_missing'])}")
    if _dep_check["missing_installed"]:
        log(f"[Deps] Auto-installed: {', '.join(_dep_check['missing_installed'])}")
del _dep_check

# ── Invite rate limiter ──────────────────────────────────────

_ui_cfg = cfg().ui
RECONNECT_TIMEOUT_SEC = _ui_cfg.reconnect_timeout_sec
INVITE_MAX_ATTEMPTS = _ui_cfg.invite_max_attempts
INVITE_LOCKOUT_SEC = _ui_cfg.invite_lockout_sec
_invite_attempts: dict[str, list[float]] = {}
_invite_lock = threading.Lock()


def _check_invite_rate_limit(client_ip: str) -> bool:
    now = _time.time()
    with _invite_lock:
        attempts = _invite_attempts.get(client_ip, [])
        attempts = [t_val for t_val in attempts if now - t_val < INVITE_LOCKOUT_SEC]
        _invite_attempts[client_ip] = attempts
        return len(attempts) < INVITE_MAX_ATTEMPTS


def _record_invite_failure(client_ip: str) -> None:
    with _invite_lock:
        _invite_attempts.setdefault(client_ip, []).append(_time.time())


# ── CSS ──────────────────────────────────────────────────────

_CSS_FILE = Path(__file__).resolve().parent / "custom_head.html"
CUSTOM_CSS = _CSS_FILE.read_text(encoding="utf-8") if _CSS_FILE.exists() else ""

# ── WebSocket reconnection JS ────────────────────────────────

_WS_RECONNECT_JS = """<script>
(function(){
    var _r = parseInt(sessionStorage.getItem('_wsRetry')||'0');
    var _ts = parseInt(sessionStorage.getItem('_wsRetryTs')||'0');
    if(_ts && Date.now()-_ts > 60000) _r = 0;
    if(_r < 5){
        window.__wsTimeout = setTimeout(function(){
            if(!window.__wsConnected){
                sessionStorage.setItem('_wsRetry', String(_r+1));
                sessionStorage.setItem('_wsRetryTs', String(Date.now()));
                location.reload();
            }
        }, 20000);
    } else {
        window.__wsTimeout = setTimeout(function(){
            if(!window.__wsConnected){
                sessionStorage.removeItem('_wsRetry');
                sessionStorage.removeItem('_wsRetryTs');
                location.reload();
            }
        }, 45000);
    }
    window.addEventListener('pageshow', function(e){
        if(e.persisted) location.reload();
    });
    var _healthCheckId = 0;
    function _pageHasContent(){
        var ca = document.querySelector('.max-w-4xl');
        return ca && ca.children.length > 0;
    }
    document.addEventListener('visibilitychange', function(){
        if(document.visibilityState==='hidden'){
            window.__hiddenAt = Date.now();
            clearInterval(_healthCheckId);
        } else {
            var elapsed = window.__hiddenAt ? Date.now()-window.__hiddenAt : 0;
            window.__hiddenAt = 0;
            if(elapsed > 5000){
                window.__recoveryTimeout = setTimeout(function(){
                    if(!_pageHasContent()){
                        sessionStorage.removeItem('_wsRetry');
                        sessionStorage.removeItem('_wsRetryTs');
                        location.reload();
                    }
                }, 3000);
                setTimeout(function(){
                    if(!_pageHasContent()){
                        sessionStorage.removeItem('_wsRetry');
                        sessionStorage.removeItem('_wsRetryTs');
                        location.reload();
                    }
                }, 12000);
            }
            var _checks = 0;
            _healthCheckId = setInterval(function(){
                _checks++;
                if(_checks > 6){clearInterval(_healthCheckId); return;}
                if(window.__wsConnected && !_pageHasContent()){
                    clearInterval(_healthCheckId);
                    sessionStorage.removeItem('_wsRetry');
                    sessionStorage.removeItem('_wsRetryTs');
                    location.reload();
                }
            }, 5000);
        }
    });
})();
</script>"""

# ── Main page ────────────────────────────────────────────────


@ui.page("/", response_timeout=30)
async def main_page(client: Client):
    ui.colors(primary='#D97706', secondary='#92400E', accent='#F59E0B')
    ui.add_head_html(CUSTOM_CSS)

    # Loading spinner
    loading = ui.column().classes("w-full items-center mt-20 gap-4")
    with loading:
        ui.spinner("dots", size="lg", color="primary")
        ui.label(t("conn.loading")).classes("text-gray-400")

    ui.add_head_html(_WS_RECONNECT_JS)

    # Wait for WebSocket
    try:
        await client.connected(timeout=20)
    except TimeoutError:
        return
    with contextlib.suppress(TimeoutError):
        await ui.run_javascript(
            "window.__wsConnected=true;"
            "clearTimeout(window.__wsTimeout);"
            "clearTimeout(window.__recoveryTimeout);"
            "sessionStorage.removeItem('_wsRetry');"
            "sessionStorage.removeItem('_wsRetryTs');",
            timeout=5.0)

    # Init session
    for _attempt in range(5):
        try:
            init_session()
            break
        except RuntimeError:
            await asyncio.sleep(0.5)
    else:
        log("[Session] app.storage.tab not available after retries",
            level="warning")
        return
    loading.delete()
    setup_file_logging()
    s = S()

    with contextlib.suppress(TimeoutError):
        await ui.run_javascript(
            'document.documentElement.lang="en"', timeout=3.0)

    # ── Page skeleton ────────────────────────────────────────

    ui.html(
        f'<a href="#chat-log" class="skip-link">'
        f'{t("aria.skip_to_content")}</a>')

    with ui.left_drawer(value=False).props(
            f'width=320 breakpoint=768 '
            f'aria-label="{t("aria.sidebar")}"') as drawer:
        drawer_content = ui.column().classes("w-full")

    with ui.header(fixed=True).classes(
            "rpg-slim-header items-center").style(
            "padding: 0 0.5rem") as header:
        hamburger_btn = ui.button(
            icon="menu", on_click=lambda: drawer.toggle()
        ).props(
            f'flat round dense aria-label="{t("aria.menu_open")}"'
        ).classes("text-gray-400 hover:text-white").style(
            "min-width: 44px; min-height: 44px")
    header.set_value(False)

    drawer.on('show', lambda: ui.run_javascript(
        'if (window.innerWidth < 768) { '
        "document.querySelector('.q-page')"
        "?.setAttribute('aria-hidden','true'); "
        "document.querySelector('.q-footer')"
        "?.setAttribute('aria-hidden','true'); }"))
    drawer.on('hide', lambda: ui.run_javascript(
        "document.querySelector('.q-page')"
        "?.removeAttribute('aria-hidden'); "
        "document.querySelector('.q-footer')"
        "?.removeAttribute('aria-hidden');"))

    with ui.footer(fixed=True).classes("q-pa-none").style(
            "background: var(--bg-primary); "
            "border-top: 1px solid var(--border)") as footer:
        footer.props(f'aria-label="{t("aria.input_area")}"')
        footer_content = ui.column().classes("w-full")
    footer.set_value(False)

    content_area = ui.column().classes(
        "w-full max-w-4xl mx-auto px-4 sm:px-0")
    content_area.props(
        f'role="main" aria-label="{t("aria.main_content")}"')

    # ── Build context and route ──────────────────────────────

    ctx = PageContext(
        client=client,
        header=header,
        drawer=drawer,
        drawer_content=drawer_content,
        footer=footer,
        footer_content=footer_content,
        content_area=content_area,
        hamburger_btn=hamburger_btn,
        check_invite_rate_limit=_check_invite_rate_limit,
        record_invite_failure=_record_invite_failure,
        invite_code=INVITE_CODE,
    )
    ctx.show_login = lambda: show_login_phase(ctx)
    ctx.show_user_selection = lambda: show_user_selection_phase(ctx)
    ctx.show_main = lambda: show_main_phase(ctx)

    if INVITE_CODE and not s.get("authenticated"):
        show_login_phase(ctx)
    elif not s.get("current_user"):
        show_user_selection_phase(ctx)
    else:
        await show_main_phase(ctx)


# ── Static files & SSL ───────────────────────────────────────

_touch_icon = generate_touch_icon()
for _icon_url in ("/apple-touch-icon.png",
                   "/apple-touch-icon-precomposed.png",
                   "/apple-touch-icon-120x120.png",
                   "/apple-touch-icon-120x120-precomposed.png"):
    app.add_static_file(url_path=_icon_url, local_file=str(_touch_icon))

_ssl_kwargs = {}
if SSL_CERTFILE and SSL_KEYFILE:
    _ssl_kwargs = {"ssl_certfile": SSL_CERTFILE, "ssl_keyfile": SSL_KEYFILE}
    log(f"[SSL] Using custom certificate: {SSL_CERTFILE}")
elif ENABLE_HTTPS:
    _cert, _key = generate_self_signed_cert()
    if _cert and _key:
        _ssl_kwargs = {"ssl_certfile": _cert, "ssl_keyfile": _key}

if _ssl_kwargs:
    log(f"[SSL] HTTPS enabled on port {SERVER_PORT}")

ui.run(
    title="Straightjacket",
    port=SERVER_PORT,
    dark=True,
    storage_secret=get_storage_secret(_server_cfg),
    favicon="\u2694\uFE0F",
    reload=False,
    show=False,
    reconnect_timeout=RECONNECT_TIMEOUT_SEC,
    **_ssl_kwargs,  # type: ignore[arg-type]
)
