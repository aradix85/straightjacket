from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.engine_config import parse_engine_yaml
from straightjacket.engine.logging_util import log
from straightjacket.engine.yaml_merge import load_yaml_dir

if TYPE_CHECKING:
    from straightjacket.engine.engine_config import EngineSettings

_CONFIG_DIR = PROJECT_ROOT / "engine"

_eng: EngineSettings | None = None


def eng() -> EngineSettings:
    global _eng
    if _eng is None:
        data = load_yaml_dir(_CONFIG_DIR, missing_dir_hint="The engine/ directory ships with the repo.")
        _eng = parse_engine_yaml(data)
        log(f"[Config] Loaded {_CONFIG_DIR} ({len(data)} sections)")
    return _eng
