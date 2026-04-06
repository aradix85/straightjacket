#!/usr/bin/env python3
"""
Straightjacket i18n — UI string access layer.

All user-facing text lives in strings.yaml (loaded by strings_loader.py).
Language is set in config.yaml (language.ui_language). To add a language,
create strings_{code}.yaml with translated keys.

This module provides t() for string lookup and getter helpers for label dicts.
Emoji constants (E dict) are code constants, not translatable.
"""

from .strings_loader import get_string, get_strings_by_prefix

# EMOJI / UNICODE CONSTANTS (shared across all modules)

E = {
    "gear": "\u2699\uFE0F", "swords": "\u2694\uFE0F",
    "dice": "\U0001F3B2", "skull": "\U0001F480",
    "shield": "\U0001F6E1\uFE0F", "pen": "\u270D\uFE0F",
    "red_circle": "\U0001F534",
    "orange_circle": "\U0001F7E0",
    "green_circle": "\U0001F7E2", "green_heart": "\U0001F49A",
    "heart_red": "\u2764\uFE0F",
    "heart_blue": "\U0001F499", "yellow_dot": "\U0001F7E1",
    "lightning": "\u26A1", "dark_moon": "\U0001F311", "brain": "\U0001F9E0",
    "mask": "\U0001F3AD", "pin": "\U0001F4CD", "warn": "\u26A0\uFE0F",
    "clock": "\u23F0", "book": "\U0001F4D6", "check": "\u2705",
    "scroll": "\U0001F4DC", "people": "\U0001F465",
    "floppy": "\U0001F4BE", "trash": "\U0001F5D1\uFE0F",
    "question": "\u2753",
    "fire": "\U0001F525", "refresh": "\U0001F504", "x_mark": "\u274C",
    "arrow_r": "\u2192", "arrow_l": "\u2190", "checkmark": "\u2713",
    "dot": "\u00B7", "dash": "\u2014",
    "tornado": "\U0001F32A\uFE0F", "plus": "\u2795", "star": "\u2728",
    "comet": "\u2604\uFE0F",
}

# UI LANGUAGE — English only

UI_LANGUAGES = {"English": "en"}

# STRING LOOKUP

def t(key: str, **kwargs) -> str:
    """Look up a UI string by key."""
    return get_string(key, **kwargs)

# LABEL GETTERS — build dicts from strings.yaml prefix conventions

def get_stat_labels() -> dict:
    return get_strings_by_prefix("stat.")

def get_disposition_labels() -> dict:
    return get_strings_by_prefix("disposition.")

def get_move_labels() -> dict:
    return get_strings_by_prefix("move.")

def get_result_labels() -> dict:
    """Returns {code: (label, severity)} for result display."""
    raw = get_strings_by_prefix("result.")
    results = {}
    codes = set()
    for key in raw:
        code = key.rsplit(".", 1)[0] if "." in key else key
        codes.add(code)
    for code in codes:
        label = raw.get(f"{code}.label", code)
        severity = raw.get(f"{code}.severity", "info")
        results[code] = (label, severity)
    return results

def get_position_labels() -> dict:
    return get_strings_by_prefix("position.")

def get_effect_labels() -> dict:
    return get_strings_by_prefix("effect.")

def get_time_labels() -> dict:
    return get_strings_by_prefix("time.")

def get_dice_display_options() -> list:
    raw = get_strings_by_prefix("dice_option.")
    return [raw[str(i)] for i in range(len(raw))]

def get_story_phase_labels() -> dict:
    return {
        "setup": t("story.setup"),
        "confrontation": t("story.confrontation"),
        "climax": t("story.climax"),
        "ki_introduction": t("story.ki_introduction"),
        "sho_development": t("story.sho_development"),
        "ten_twist": t("story.ten_twist"),
        "ketsu_resolution": t("story.ketsu_resolution"),
    }

def translate_consequence(text: str) -> str:
    """Translate consequence keys to display labels."""
    import re
    terms = get_strings_by_prefix("consequence.")
    if not terms:
        return text
    result = text
    for key, translated in terms.items():
        result = re.sub(rf'\b{re.escape(key)}\b', translated, result)
    return result
