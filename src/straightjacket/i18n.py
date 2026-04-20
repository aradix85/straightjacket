"""
Straightjacket i18n — UI string access layer.

All user-facing text lives in strings.yaml (loaded by strings_loader.py).
Language is set in config.yaml (language.ui_language). To add a language,
create strings_{code}.yaml with translated keys.
"""

from .strings_loader import get_string, get_strings_by_prefix


def t(key: str, **kwargs: str | int) -> str:
    return get_string(key, **kwargs)


def get_disposition_labels() -> dict[str, str]:
    return get_strings_by_prefix("disposition.")


def get_time_labels() -> dict[str, str]:
    return get_strings_by_prefix("time.")


def get_story_phase_labels() -> dict[str, str]:
    return get_strings_by_prefix("story.")
