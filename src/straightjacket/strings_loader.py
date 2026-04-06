#!/usr/bin/env python3
"""Straightjacket string loader: yaml-driven UI strings.

Loads UI strings from YAML. Language is set in config.yaml (language.ui_language).
English strings live in strings.yaml (always loaded as fallback).
Other languages: create strings_{code}.yaml with the same keys.

Loading order: strings_{code}.yaml merged over strings.yaml.
Missing keys in the language file fall back to English automatically.
"""

from pathlib import Path

import yaml

from .engine.bootstrap_log import bootstrap_log as _log

_SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent  # straightjacket/ -> src/ -> project root
_STRINGS_DIR = _SCRIPT_DIR


class _DefaultDict(dict):
    """Dict that returns '{key}' for missing keys, allowing partial formatting."""
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


_strings: dict[str, str] | None = None


def _get_ui_language() -> str:
    """Read ui_language from config.yaml. Returns 'en' if unavailable."""
    try:
        cfg_path = _SCRIPT_DIR / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("language", {}).get("ui_language") or "en"
    except Exception:
        pass
    return "en"


def _ensure_loaded() -> dict:
    """Load strings on first access. English base + language overlay."""
    global _strings
    if _strings is None:
        base_path = _STRINGS_DIR / "strings.yaml"
        if not base_path.exists():
            raise FileNotFoundError(
                f"Strings file not found: {base_path}\n"
                f"strings.yaml ships with the repo — restore it from git."
            )
        with open(base_path, encoding="utf-8") as f:
            base = yaml.safe_load(f) or {}

        _strings = {k: v for k, v in base.items() if isinstance(v, str)}

        # Overlay language-specific file if it exists
        lang = _get_ui_language()
        if lang != "en":
            lang_path = _STRINGS_DIR / f"strings_{lang}.yaml"
            if lang_path.exists():
                with open(lang_path, encoding="utf-8") as f:
                    overlay = yaml.safe_load(f) or {}
                count = 0
                for k, v in overlay.items():
                    if isinstance(v, str):
                        _strings[k] = v
                        count += 1
                _log(f"[Strings] Loaded {count} overrides from {lang_path.name}")

        _log(f"[Strings] {len(_strings)} strings ready (lang={lang})")
    return _strings


def get_string(key: str, **variables) -> str:
    """Get a string by key, filling template variables.
    Returns the key itself if not found (visible placeholder, not a crash)."""
    strings = _ensure_loaded()
    template = strings.get(key)
    if template is None:
        return key
    if variables:
        return template.format_map(_DefaultDict(variables))
    return template


def get_strings_by_prefix(prefix: str) -> dict[str, str]:
    """Get all strings matching a prefix as {suffix: value} dict.
    Example: get_strings_by_prefix("genre.") returns {"dark_fantasy": "...", ...}
    """
    strings = _ensure_loaded()
    return {k[len(prefix):]: v for k, v in strings.items() if k.startswith(prefix)}


def reload_strings():
    """Force reload from disk. Use after config or file changes."""
    global _strings
    _strings = None
    _ensure_loaded()
