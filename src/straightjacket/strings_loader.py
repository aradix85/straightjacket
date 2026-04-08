#!/usr/bin/env python3
"""Straightjacket string loader: yaml-driven UI strings.

All UI strings live in strings.yaml. Loaded once on first access.
"""

import yaml

from .engine.bootstrap_log import bootstrap_log as _log
from .engine.config_loader import PROJECT_ROOT
from .engine.format_utils import PartialFormatDict

_STRINGS_PATH = PROJECT_ROOT / "strings.yaml"

_strings: dict[str, str] | None = None


def _ensure_loaded() -> dict:
    """Load strings on first access."""
    global _strings
    if _strings is None:
        if not _STRINGS_PATH.exists():
            raise FileNotFoundError(
                f"Strings file not found: {_STRINGS_PATH}\nstrings.yaml ships with the repo — restore it from git."
            )
        with open(_STRINGS_PATH, encoding="utf-8") as f:
            base = yaml.safe_load(f) or {}

        _strings = {k: v for k, v in base.items() if isinstance(v, str)}
        _log(f"[Strings] {len(_strings)} strings ready")
    return _strings


def get_string(key: str, **variables: str | int) -> str:
    """Get a string by key, filling template variables.
    Returns the key itself if not found (visible placeholder, not a crash)."""
    strings = _ensure_loaded()
    template = strings.get(key)
    if template is None:
        return key
    if variables:
        return template.format_map(PartialFormatDict(variables))
    return template


def get_strings_by_prefix(prefix: str) -> dict[str, str]:
    """Get all strings matching a prefix as {suffix: value} dict."""
    strings = _ensure_loaded()
    return {k[len(prefix) :]: v for k, v in strings.items() if k.startswith(prefix)}


def reload_strings() -> None:
    """Force reload from disk."""
    global _strings
    _strings = None
    _ensure_loaded()


def all_strings() -> dict[str, str]:
    """Return all loaded strings. Used by the web layer to send UI strings to clients."""
    return dict(_ensure_loaded())
