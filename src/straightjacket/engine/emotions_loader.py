from pathlib import Path
from typing import Any

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.logging_util import log
from straightjacket.engine.yaml_merge import load_yaml_dir

_EMOTIONS_DIR = PROJECT_ROOT / "emotions"

_cache: dict[Path, dict[str, Any]] = {}


def _ensure_loaded() -> dict[str, Any]:
    if _EMOTIONS_DIR not in _cache:
        data = load_yaml_dir(_EMOTIONS_DIR, missing_dir_hint="The emotions/ directory ships with the repo.")
        _cache[_EMOTIONS_DIR] = data
        log(f"[Emotions] Loaded {_EMOTIONS_DIR} ({len(data)} sections)")
    return _cache[_EMOTIONS_DIR]


def importance_map() -> dict[str, int]:
    result: dict[str, int] = _ensure_loaded()["importance"]
    return result


def keyword_boosts() -> dict[int, list[str]]:
    raw = _ensure_loaded()["keyword_boosts"]
    return {int(k): v for k, v in raw.items()}
