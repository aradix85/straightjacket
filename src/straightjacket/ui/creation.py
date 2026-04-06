#!/usr/bin/env python3
"""Character creation: setting, name, pronouns, paths, backstory, vow, stats, wishes, confirm.

All choices are deterministic. No AI call during creation. The first AI call
is the opening scene narrator. Setting packages provide all options.
"""

import asyncio
from typing import Any

from nicegui import ui

from ..engine import (
    E,
    load_user_config,
    log,
    save_game,
    start_new_game,
)
from ..engine.ai.api_client import get_provider
from ..engine.datasworn.loader import _extract_title
from ..engine.datasworn.settings import list_packages, load_package
from ..i18n import t
from .helpers import S, get_engine_config, scroll_chat_bottom

_STAT_NAMES = ["edge", "heart", "iron", "shadow", "wits"]

def _validate_stats(stats: dict, target: int = 7) -> bool:
    values = [stats.get(s, 0) for s in _STAT_NAMES]
    return sum(values) == target and all(0 <= v <= 3 for v in values)

def _next(step: str, **updates):
    s = S()
    cr = s.get("creation") or {}
    cr.update(updates)
    cr["step"] = step
    s["creation"] = cr
    ui.navigate.reload()

def _back_btn(target_step: str):
    def go_back():
        s = S()
        if target_step == "_reset":
            s["creation"] = None
        else:
            s["creation"]["step"] = target_step
        ui.navigate.reload()
    ui.button(f"{E['arrow_l']} {t('creation.back')}", on_click=go_back).props(
        "flat dense no-caps").classes("text-xs mb-2")

# MAIN ENTRY

def render_creation_flow(chat_container) -> bool:
    s = S()
    creation = s.get("creation")
    game = s.get("game")

    if game is None and creation is None:
        _render_setting_choice()
        return True
    if creation is None:
        return False

    step = creation.get("step", "setting")
    renderers = {
        "setting": _render_setting_choice,
        "name": _render_name,
        "pronouns": _render_pronouns,
        "paths": _render_paths,
        "backstory": _render_backstory,
        "vow": _render_vow,
        "stats": _render_stats,
        "wishes": _render_wishes,
        "confirm": _render_confirm,
    }
    renderers.get(step, _render_setting_choice)()
    return True

def _render_setting_choice():
    ui.label("Choose your world").classes("text-lg font-bold mb-2")
    for pid in list_packages():
        try:
            pkg = load_package(pid)
        except Exception:
            continue
        if pid == "delve":
            continue
        def pick(sid=pid):
            _next("name", setting_id=sid)
        with ui.card().classes("w-full cursor-pointer mb-2").on("click", pick):
            ui.label(pkg.title).classes("font-bold")
            ui.label(pkg.description.strip()).classes("text-sm text-gray-500")

def _render_name():
    s = S()
    creation = s["creation"]
    _back_btn("_reset")
    ui.label(t("creation.name_question")).classes("text-lg font-bold mb-2")

    name_inp = ui.input(
        placeholder=t("creation.name_placeholder"),
        value=creation.get("player_name", ""),
    ).classes("w-full")

    # Name roll buttons from setting
    try:
        pkg = load_package(creation["setting_id"])
        names = pkg.data.name_tables()
        if names:
            with ui.row().classes("gap-2 mt-2"):
                for nid, table in names.items():
                    label = nid.replace("_", " ").title()
                    def roll(t=table):
                        name_inp.set_value(t.roll_text())
                    ui.button(f"{E['dice']} {label}", on_click=roll).props(
                        "flat dense no-caps").classes("text-xs")
    except Exception:
        pass

    def go():
        if name_inp.value.strip():
            _next("pronouns", player_name=name_inp.value.strip())
    name_inp.on("keydown.enter", go)
    ui.button(t("creation.next"), on_click=go, color="primary").classes("mt-3")

def _render_pronouns():
    _back_btn("name")
    ui.label("Pronouns").classes("text-lg font-bold mb-2")
    ui.label("How should the narrator refer to your character?").classes(
        "text-sm text-gray-500 mb-3")

    for opt in ["he/him", "she/her", "they/them"]:
        ui.button(opt, on_click=lambda o=opt: _next("paths", pronouns=o)).props(
            "flat unelevated").classes("w-full choice-btn mb-1")

    inp = ui.input(placeholder="Or type your own (e.g. xe/xem)").classes("w-full mt-2")
    def go_custom():
        if inp.value.strip():
            _next("paths", pronouns=inp.value.strip())
    inp.on("keydown.enter", go_custom)
    ui.button(t("creation.next"), on_click=go_custom, color="primary").classes("mt-2")

def _render_paths():
    s = S()
    creation = s["creation"]
    _back_btn("pronouns")
    ui.label("Choose two paths").classes("text-lg font-bold mb-2")
    ui.label("Paths define what your character can do.").classes(
        "text-sm text-gray-500 mb-3")

    try:
        pkg = load_package(creation["setting_id"])
        all_paths = pkg.data.paths()
    except Exception:
        all_paths = []

    selected = set(creation.get("paths", []))

    def toggle(pid):
        cr = s["creation"]
        current = set(cr.get("paths", []))
        if pid in current:
            current.discard(pid)
        elif len(current) < 2:
            current.add(pid)
        cr["paths"] = list(current)
        s["creation"] = cr
        ui.navigate.reload()

    for p in all_paths:
        pid = p.get("_id", "").rsplit("/", 1)[-1] if p.get("_id") else ""
        if not pid:
            continue
        title = _extract_title(p, pid)
        is_sel = pid in selected
        ui.button(
            f"{'[x] ' if is_sel else ''}{title}",
            on_click=lambda _p=pid: toggle(_p),
        ).props("flat unelevated").classes(
            f"w-full choice-btn mb-1 {'ring-2 ring-primary' if is_sel else ''}")

    ui.label(f"Selected: {len(selected)}/2").classes("text-sm text-gray-500 mt-2")
    if len(selected) == 2:
        ui.button(f"{t('creation.next')} {E['arrow_r']}",
                  on_click=lambda: _next("backstory"),
                  color="primary").classes("mt-2")

def _render_backstory():
    s = S()
    creation = s["creation"]
    _back_btn("paths")
    ui.label("Backstory").classes("text-lg font-bold mb-2")

    inp = ui.textarea(
        placeholder="Who were you before? What happened? (Optional)",
        value=creation.get("backstory", ""),
    ).props("rows=3").classes("w-full")

    try:
        pkg = load_package(creation["setting_id"])
        bp = pkg.data.backstory_prompts()
        if bp:
            def roll():
                inp.set_value(bp.roll_text())
            ui.button(f"{E['dice']} Roll backstory", on_click=roll).props(
                "flat dense no-caps").classes("text-xs mt-1")
    except Exception:
        pass

    def go():
        _next("vow", backstory=inp.value.strip() if inp.value else "")
    ui.button(t("creation.next"), on_click=go, color="primary").classes("mt-3")

def _render_vow():
    s = S()
    creation = s["creation"]
    _back_btn("backstory")
    ui.label("Background vow").classes("text-lg font-bold mb-2")
    ui.label("What drives your character? What have they sworn to do?").classes(
        "text-sm text-gray-500 mb-3")

    inp = ui.input(
        placeholder="e.g. Find the lost colony ship, avenge my mentor...",
        value=creation.get("background_vow", ""),
    ).classes("w-full")

    def go():
        _next("stats", background_vow=inp.value.strip() if inp.value else "")
    inp.on("keydown.enter", go)
    ui.button(t("creation.next"), on_click=go, color="primary").classes("mt-3")

def _render_stats():
    s = S()
    creation = s["creation"]
    _back_btn("vow")
    ui.label("Allocate stats").classes("text-lg font-bold mb-2")
    ui.label("Distribute 7 points. Each stat: 0-3.").classes(
        "text-sm text-gray-500 mb-3")

    stats = creation.get("stats", {"edge": 1, "heart": 2, "iron": 1, "shadow": 2, "wits": 1})
    labels = {
        "edge": "Edge (speed, stealth)",
        "heart": "Heart (empathy, charm)",
        "iron": "Iron (force, endurance)",
        "shadow": "Shadow (cunning, deception)",
        "wits": "Wits (knowledge, observation)",
    }

    sliders: dict[str, Any] = {}
    total_label = ui.label("").classes("text-sm font-bold mb-2")

    def update_total():
        total = sum(int(sl.value) for sl in sliders.values())
        color = "text-green-600" if total == 7 else "text-red-600"
        total_label.set_text(f"Total: {total}/7")
        total_label.classes(replace=f"text-sm font-bold mb-2 {color}")

    for stat in _STAT_NAMES:
        with ui.row().classes("w-full items-center gap-2"):
            ui.label(labels[stat]).classes("w-48 text-sm")
            sl = ui.slider(min=0, max=3, step=1, value=stats.get(stat, 1)).classes("flex-grow")
            val_lbl = ui.label(str(stats.get(stat, 1))).classes("w-6 text-center")
            sl.on("update:model-value", lambda e, vl=val_lbl: vl.set_text(str(int(e.args))))
            sl.on("update:model-value", lambda e: update_total())
            sliders[stat] = sl

    update_total()

    def go():
        final = {s: int(sliders[s].value) for s in _STAT_NAMES}
        if not _validate_stats(final):
            ui.notify("Stats must total exactly 7, each 0-3.", type="warning")
            return
        _next("wishes", stats=final)
    ui.button(t("creation.next"), on_click=go, color="primary").classes("mt-4")

def _render_wishes():
    s = S()
    creation = s["creation"]
    _back_btn("stats")

    if "content_lines" not in creation:
        cfg = load_user_config(s["current_user"])
        creation["content_lines"] = cfg.get("content_lines", "")

    ui.label("Story wishes and boundaries").classes("text-lg font-bold mb-2")

    ui.label(f"{E['star']} What do you want in your story? (Optional)").classes("text-sm mt-2")
    w_inp = ui.textarea(
        placeholder="A mystery to solve, a rival who becomes an ally, space pirates...",
        value=creation.get("wishes", ""),
    ).props("rows=2").classes("w-full")

    ui.label(f"{E['shield']} What must not appear? (Optional)").classes("text-sm mt-3")
    l_inp = ui.textarea(
        placeholder="Violence against children, body horror, spiders...",
        value=creation.get("content_lines", ""),
    ).props("rows=2").classes("w-full")
    ui.label("Boundaries are saved for next time.").classes("text-xs text-gray-500")

    def go():
        _next("confirm",
              wishes=w_inp.value.strip() if w_inp.value else "",
              content_lines=l_inp.value.strip() if l_inp.value else "")
    ui.button(t("creation.next"), on_click=go, color="primary").classes("mt-4")

def _render_confirm():
    s = S()
    creation = s["creation"]
    _back_btn("wishes")

    try:
        pkg = load_package(creation["setting_id"])
    except Exception:
        ui.label("Setting not found.")
        return

    ui.label("Your character").classes("text-lg font-bold mb-3")

    path_names = []
    for pid in creation.get("paths", []):
        asset = pkg.data.asset("path", pid)
        if asset:
            path_names.append(_extract_title(asset, pid))

    stats = creation.get("stats", {})
    info = [
        ("Setting", pkg.title),
        ("Name", creation.get("player_name", "?")),
        ("Pronouns", creation.get("pronouns", "?")),
        ("Paths", ", ".join(path_names) if path_names else "(none)"),
    ]
    if creation.get("backstory"):
        info.append(("Backstory", creation["backstory"][:80]))
    if creation.get("background_vow"):
        info.append(("Vow", creation["background_vow"]))
    if stats:
        info.append(("Stats", " / ".join(f"{s.title()}:{stats.get(s, 0)}" for s in _STAT_NAMES)))

    for label, value in info:
        ui.label(f"{label}: {value}").classes("text-sm")

    ui.separator().classes("my-4")

    _busy = {"active": False}

    async def start():
        if _busy["active"]:
            return
        _busy["active"] = True
        if not s.get("api_key", "").strip():
            ui.notify("API key required.", type="negative")
            _busy["active"] = False
            return
        with ui.row().classes("w-full items-center gap-3").props('role="status"'):
            ui.spinner("dots", size="md", color="primary")
            ui.label("Creating your world...").classes("text-sm").style(
                "color: var(--text-secondary)")
        await scroll_chat_bottom()
        try:
            provider = get_provider(api_key=s["api_key"])
            config = get_engine_config()
            username = s["current_user"]
            game, narration = await asyncio.to_thread(
                start_new_game, provider, creation, config, username)
            s["game"] = game
            s["creation"] = None
            s["active_save"] = "autosave"
            s["messages"].append({"scene_marker": t("game.scene_marker", n=1, location=game.world.current_location)})
            s["messages"].append({"role": "assistant", "content": narration})
            save_game(game, username, s["messages"], s["active_save"])
            ui.navigate.reload()
        except Exception as e:
            log(f"[Creation] Error: {e}", level="error")
            ui.notify(f"Error: {e}", type="negative")
            _busy["active"] = False

    ui.button(f"{E['swords']} Begin Adventure!", on_click=start,
              color="primary").classes("text-lg px-8")
