#!/usr/bin/env python3
"""Straightjacket config loader: yaml-driven configuration.

config.yaml is the single source of truth for all engine settings.
The file ships with the repo. If it's missing, the engine does not start.
Config path can be overridden via EDGETALES_CONFIG environment variable.
"""

import os
from pathlib import Path
from typing import Any

import yaml


from .bootstrap_log import bootstrap_log as _log

# Project root: config.yaml, engine.yaml, data/, users/, logs/ all live here.
# Single source of truth — every module imports PROJECT_ROOT from here.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # engine/ -> straightjacket/ -> src/ -> project root
_CONFIG_PATH = Path(os.environ.get("EDGETALES_CONFIG", str(PROJECT_ROOT / "config.yaml")))

def _read_version() -> str:
    """Read version from pyproject.toml — single source of truth."""
    import re as _re
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if pyproject.exists():
        m = _re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), _re.MULTILINE)
        if m:
            return m.group(1)
    return "0.0.0"

VERSION = _read_version()

# PATHS (used by logging_util, persistence, etc.)

USERS_DIR = PROJECT_ROOT / "users"
USERS_DIR.mkdir(exist_ok=True)
GLOBAL_CONFIG_FILE = _CONFIG_PATH

# CONFIG OBJECT — dot-access wrapper

class _ConfigNode:
    """Recursive dot-access wrapper over a dict.
    cfg.ai.brain_model works like cfg["ai"]["brain_model"].
    Tracks access path for clear error messages on typos.
    """
    def __init__(self, data: dict, _path: str = "config"):
        self._data = data
        self._path = _path

    def __getattr__(self, key: str) -> Any:
        if key in ("_data", "_path"):
            return super().__getattribute__(key)
        try:
            val = self._data[key]
        except KeyError:
            available = ", ".join(sorted(self._data.keys()))
            raise AttributeError(
                f"{self._path}.{key} does not exist. "
                f"Available keys at {self._path}: {available}"
            ) from None
        if isinstance(val, dict):
            return _ConfigNode(val, f"{self._path}.{key}")
        return val

    def __getitem__(self, key: str) -> Any:
        try:
            val = self._data[key]
        except KeyError:
            available = ", ".join(sorted(self._data.keys()))
            raise KeyError(
                f"{self._path}['{key}'] does not exist. "
                f"Available keys: {available}"
            ) from None
        if isinstance(val, dict):
            return _ConfigNode(val, f"{self._path}.{key}")
        return val

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"Config({self._path}, keys={list(self._data.keys())})"

    def get(self, key: str, default: Any = None) -> Any:
        val = self._data.get(key, default)
        if isinstance(val, dict):
            return _ConfigNode(val, f"{self._path}.{key}")
        return val

    def to_dict(self) -> dict:
        return self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

def _load_config_file() -> dict:
    """Load config.yaml. Raises if missing or unreadable."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config file not found: {_CONFIG_PATH}\n"
            f"The config.yaml file ships with the repo — if you deleted it, restore it from git.\n"
            f"To use a different config file, set the EDGETALES_CONFIG environment variable."
        )
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Config file is not a valid YAML dict: {_CONFIG_PATH}")
    _log(f"[Config] Loaded {_CONFIG_PATH}")
    return data

_cfg: _ConfigNode | None = None

def cfg() -> _ConfigNode:
    """Get the global config object. Loads on first access."""
    global _cfg
    if _cfg is None:
        data = _load_config_file()
        _cfg = _ConfigNode(data)
    return _cfg

def reload_config() -> _ConfigNode:
    """Force reload from disk. Use after external edits."""
    global _cfg
    _cfg = None
    return cfg()

# CONVENIENCE ACCESSORS — single source of truth for defaults
# These exist so that no module ever hardcodes "English",
# "Unnamed", etc. as a fallback. Every default comes from config.

def narration_language() -> str:
    """Narration language for AI prompts (English name, e.g. 'English', 'German')."""
    return cfg().language.narration_language

def default_player_name() -> str:
    """Default player name when none is provided."""
    return cfg().language.default_player_name

def user_default(key: str) -> Any:
    """Get a user preference default from config.

    Single access point for all per-user defaults. Every s.get("key", fallback)
    in the codebase should use this instead of a hardcoded fallback:
        s.get("dice_display", user_default("dice_display"))

    All defaults live in config.yaml under "user_defaults" and can be
    changed there without touching code.
    """
    return cfg().user_defaults.get(key, None)

def sampling_params(role: str) -> dict:
    """Get sampling parameters (temperature, top_p) for an AI role.

    Returns a dict suitable for unpacking into create_with_retry():
        create_with_retry(provider, ..., **sampling_params("narrator"))

    Reads from config.yaml ai.temperature.<role> and ai.top_p.<role>.
    Returns None for any param not configured, which means provider default.
    """
    _c = cfg()
    params = {}
    try:
        params["temperature"] = getattr(_c.ai.temperature, role)
    except AttributeError:
        params["temperature"] = None
    try:
        val = getattr(_c.ai.top_p, role)
        params["top_p"] = float(val) if val is not None else None
    except AttributeError:
        params["top_p"] = None
    return params
