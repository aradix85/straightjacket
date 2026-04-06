#!/usr/bin/env python3
"""Chat rendering: message history and dice display."""


from nicegui import ui

from ..engine import E, user_default
from ..i18n import (
    get_effect_labels,
    get_move_labels,
    get_position_labels,
    get_result_labels,
    get_stat_labels,
    t,
    translate_consequence,
)
from .helpers import S, clean_narration, dice_string_to_index, highlight_dialog


def render_chat_messages(container) -> str | None:
    """Render chat history. Returns the ID of the last scene marker (for scroll targeting)."""
    s = S()
    _sr_chat = s.get("sr_chat", user_default("sr_chat"))
    _is_highlight = s.get("narrator_font") == "highlight"
    viewing = s.get("viewing_chapter")
    messages = s.get("chapter_view_messages", []) if viewing else s.get("messages", [])
    last_scene_marker_id = None
    for i, msg in enumerate(messages):
        if msg.get("scene_marker"):
            marker_id = f"msg-{i}"
            last_scene_marker_id = marker_id
            ui.html(f'<h2 id="{marker_id}" class="scene-marker">'
                     f'{E["dash"]} {msg["scene_marker"]} {E["dash"]}</h2>').classes("w-full")
            continue
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        css = "recap" if msg.get("recap") else role
        if msg.get("correction_input"):
            css += " correction"
        prefix = (f"{E['scroll']} **{t('actions.recap_prefix')}**\n\n"
                  if msg.get("recap") else "")
        _msg_col = ui.column().classes(f"chat-msg {css} w-full")
        if not _sr_chat:
            _msg_col.props('aria-hidden="true"')
        with _msg_col:
            _sr_prefix = ""
            if _sr_chat:
                if msg.get("recap"):
                    _sr_prefix = f'<span class="sr-only">{t("aria.recap_says")}</span>'
                elif role == "user":
                    _sr_prefix = f'<span class="sr-only">{t("aria.player_says")}</span>'
                else:
                    _sr_prefix = f'<span class="sr-only">{t("aria.narrator_says")}</span>'
            if msg.get("corrected"):
                with ui.element('div').classes('correction-badge').props(
                    f'aria-label="{t("aria.correction_badge")}"'):
                    ui.label(t("correction.badge"))
            _display = clean_narration(content)
            if _is_highlight and role == "assistant" and not msg.get("recap"):
                _display = highlight_dialog(_display)
            ui.markdown(f"{_sr_prefix}{prefix}{_display}")
            rd = msg.get("roll_data")
            if rd:
                render_dice_display(rd)
    return last_scene_marker_id


def render_dice_display(rd: dict) -> None:
    if not rd:
        return
    s = S()
    setting = s.get("dice_display", user_default("dice_display"))
    if isinstance(setting, str):
        setting = dice_string_to_index(setting)
    if setting == 0:
        return
    rl = get_result_labels()
    ml = get_move_labels()
    sl = get_stat_labels()
    result_label, severity = rl.get(rd.get("result", ""), (rd.get("result_label", "?"), "info"))
    stat_label = sl.get(rd.get("stat_name", ""), rd.get("stat_label", "?"))
    move_label = ml.get(rd.get("move", ""), rd.get("move_label", "?"))
    is_match = rd.get("match", rd.get("c1") == rd.get("c2"))
    if setting == 1:  # Simple
        pos = rd.get("position", "")
        pl = get_position_labels()
        ph = f" {E['dot']} {pl.get(pos, '')}" if pos and pos != "risky" else ""
        match_txt = f" {E['dot']} {t('dice.match_short')}" if is_match else ""
        chaos_txt = (f" {E['dot']} {t('dice.chaos_short')}"
                     if rd.get("chaos_interrupt") else "")
        with ui.element('div').classes(f'dice-simple {severity} w-full'):
            ui.label(f'{result_label} {E["dot"]} {stat_label}{ph}{match_txt}{chaos_txt}')
    elif setting == 2:  # Detailed
        header = f"{E['dice']} {result_label} \u2014 {move_label} ({stat_label})"
        if is_match:
            header += f" {E['comet']}"
        if rd.get("chaos_interrupt"):
            header += f" {E['dot']} {t('dice.chaos_short')}"
        with ui.expansion(header).classes("w-full"):
            ui.markdown(t("dice.action", d1=rd['d1'], d2=rd['d2'],
                          stat_value=rd['stat_value'], score=rd['action_score'],
                          c1=rd['c1'], c2=rd['c2']))
            if is_match:
                ui.markdown(t("dice.match", value=rd['c1']))
            pl = get_position_labels()
            el = get_effect_labels()
            ui.markdown(t("dice.position", position=pl.get(rd.get('position', 'risky'), '?'),
                          effect=el.get(rd.get('effect', 'standard'), '?')))
            if rd.get("consequences"):
                cons_text = ', '.join(translate_consequence(c)
                                      for c in rd['consequences'])
                ui.markdown(t("dice.consequences", text=cons_text))
            for ce in rd.get("clock_events", []):
                if ce.clock:
                    ui.markdown(f"{E['clock']} **{ce.clock}**: {ce.trigger}")
