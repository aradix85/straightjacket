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

# UNICODE CONSTANTS (shared across all modules)

E = {
    "dash": "\u2014",
}

# STRING LOOKUP


def t(key: str, **kwargs: str | int) -> str:
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
        result = re.sub(rf"\b{re.escape(key)}\b", translated, result)
    return result
