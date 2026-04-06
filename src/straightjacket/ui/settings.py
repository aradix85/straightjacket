#!/usr/bin/env python3
"""Settings panel: API key, dice display, screen reader, narrator font."""

from nicegui import ui

from ..engine import (
    E,
    load_user_config,
    save_user_config,
    user_default,
)
from ..i18n import get_dice_display_options, t
from .helpers import S
import contextlib

# Module-level ref set by app.py
SERVER_API_KEY: str = ""

def configure(*, server_api_key: str = ""):
    global SERVER_API_KEY
    SERVER_API_KEY = server_api_key

def render_settings() -> None:
    s = S()
    username = s["current_user"]
    with ui.expansion(f"{E['gear']} {t('settings.title')}").classes("w-full"):
        if not SERVER_API_KEY:
            api_inp = ui.input(t("settings.api_key"), value=s.get("api_key", ""),
                               password=True, password_toggle_button=True).classes("w-full")
            ui.separator()

        # Dice display
        ui.separator()
        dice_opts = get_dice_display_options()
        dice_labels = dice_opts
        cur_dice_idx = s.get("dice_display", user_default("dice_display"))
        if isinstance(cur_dice_idx, str):
            from .helpers import dice_string_to_index
            cur_dice_idx = dice_string_to_index(cur_dice_idx)
        cur_dice_label = dice_labels[cur_dice_idx] if 0 <= cur_dice_idx < len(dice_labels) else dice_labels[0]
        dice_sel = ui.select(dice_labels, label=t("settings.dice"),
                             value=cur_dice_label).classes("w-full")

        # Screen reader chat
        with ui.row().classes("w-full items-center justify-between"):
            sr_sw = ui.switch(t("settings.sr_chat"), value=s.get("sr_chat", user_default("sr_chat")))
            _tip = t("settings.sr_tooltip")
            with ui.icon("info_outline").classes("text-gray-400 cursor-help").props(f'tabindex="0" role="img" aria-label="{_tip}"'):
                ui.tooltip(_tip)

        # Narrator font
        ui.separator()
        font_options = {
            "serif": t("settings.narrator_font_serif"),
            "sans": t("settings.narrator_font_sans"),
            "highlight": t("settings.narrator_font_design"),
        }
        cur_font = s.get("narrator_font", "serif")
        cur_font_label = font_options.get(cur_font, font_options["serif"])
        font_sel = ui.select(list(font_options.values()), label=t("settings.narrator_font"),
                             value=cur_font_label).classes("w-full")

        # Save
        ui.separator()

        async def save_cfg():
            if not SERVER_API_KEY:
                s["api_key"] = api_inp.value
            s["dice_display"] = dice_opts.index(dice_sel.value) if dice_sel.value in dice_opts else 0
            s["sr_chat"] = sr_sw.value
            # Narrator font: reverse-lookup from label to key
            _label_to_key = {v: k for k, v in font_options.items()}
            s["narrator_font"] = _label_to_key.get(font_sel.value, "serif")
            ucfg = load_user_config(username)
            if not SERVER_API_KEY:
                ucfg["api_key"] = s["api_key"]
            ucfg["dice_display"] = s["dice_display"]
            ucfg["sr_chat"] = s["sr_chat"]
            ucfg["narrator_font"] = s["narrator_font"]
            save_user_config(username, ucfg)
            # Live-switch narrator font via JS
            with contextlib.suppress(TimeoutError):
                await ui.run_javascript(
                    f'document.body.setAttribute("data-narrator-font","{s["narrator_font"]}")',
                    timeout=2.0)
            ui.notify(t("settings.saved"), type="positive")

        ui.button(f"{E['checkmark']} {t('settings.save')}", on_click=save_cfg,
                  color="primary").classes("w-full")
