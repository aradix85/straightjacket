from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.config_binding import build_strict
from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.engine_config import EngineSettings
from straightjacket.engine.logging_util import log
from straightjacket.engine.yaml_merge import load_yaml_dir

if TYPE_CHECKING:
    from pathlib import Path

_CONFIG_DIR = PROJECT_ROOT / "engine"

_cache: dict[Path, EngineSettings] = {}


def eng() -> EngineSettings:
    if _CONFIG_DIR not in _cache:
        data = load_yaml_dir(_CONFIG_DIR, missing_dir_hint="The engine/ directory ships with the repo.")
        _cache[_CONFIG_DIR] = build_strict(EngineSettings, data, "engine")
        log(f"[Config] Loaded {_CONFIG_DIR} ({len(data)} sections)")
    return _cache[_CONFIG_DIR]
