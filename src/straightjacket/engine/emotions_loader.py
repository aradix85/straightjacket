from dataclasses import dataclass
from pathlib import Path

from straightjacket.engine.config_binding import build_strict
from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.logging_util import log
from straightjacket.engine.yaml_merge import load_yaml_dir

_EMOTIONS_DIR = PROJECT_ROOT / "emotions"


@dataclass
class EmotionSettings:
    importance: dict[str, int]
    keyword_boosts: dict[int, list[str]]


_cache: dict[Path, EmotionSettings] = {}


def _ensure_loaded() -> EmotionSettings:
    if _EMOTIONS_DIR not in _cache:
        data = load_yaml_dir(_EMOTIONS_DIR, missing_dir_hint="The emotions/ directory ships with the repo.")
        _cache[_EMOTIONS_DIR] = build_strict(EmotionSettings, data, "emotions")
        log(f"[Emotions] Loaded {_EMOTIONS_DIR} ({len(data)} sections)")
    return _cache[_EMOTIONS_DIR]


def importance_map() -> dict[str, int]:
    return _ensure_loaded().importance


def keyword_boosts() -> dict[int, list[str]]:
    return _ensure_loaded().keyword_boosts
