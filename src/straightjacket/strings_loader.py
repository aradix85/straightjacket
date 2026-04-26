from pathlib import Path

import yaml

from .engine.bootstrap_log import bootstrap_log as _log
from .engine.config_loader import PROJECT_ROOT
from .engine.format_utils import PartialFormatDict

_STRINGS_DIR = PROJECT_ROOT / "strings"

_strings: dict[str, str] | None = None


def _ensure_loaded() -> dict[str, str]:
    global _strings
    if _strings is None:
        if not _STRINGS_DIR.is_dir():
            raise FileNotFoundError(
                f"Strings directory not found: {_STRINGS_DIR}\nstrings/ ships with the repo — restore it from git."
            )
        files = sorted(_STRINGS_DIR.glob("*.yaml"))
        if not files:
            raise FileNotFoundError(f"No yaml files found in {_STRINGS_DIR}")
        _strings = {}
        origin: dict[str, Path] = {}
        for path in files:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ValueError(f"{path} is not a valid YAML dict")
            for key, val in data.items():
                if not isinstance(val, str):
                    raise ValueError(f"{path}: key '{key}' must be a string, got {type(val).__name__}")
                if key in _strings:
                    raise ValueError(f"Duplicate string key '{key}' in {path} — already defined in {origin[key]}")
                _strings[key] = val
                origin[key] = path
        _log(f"[Strings] {len(_strings)} strings ready")
    return _strings


def get_string(key: str, **variables: str | int) -> str:
    strings = _ensure_loaded()
    if key not in strings:
        raise KeyError(f"Unknown UI string key: '{key}'")
    template = strings[key]
    if variables:
        return template.format_map(PartialFormatDict(variables))
    return template


def get_strings_by_prefix(prefix: str) -> dict[str, str]:
    strings = _ensure_loaded()
    return {k[len(prefix) :]: v for k, v in strings.items() if k.startswith(prefix)}


def all_strings() -> dict[str, str]:
    return dict(_ensure_loaded())
