from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.logging_util import log

if TYPE_CHECKING:
    from pathlib import Path

_MYTHIC_DATA_PATH = PROJECT_ROOT / "data" / "mythic_gme_2e.json"

_cache: dict[Path, dict[str, Any]] = {}


def load_mythic() -> dict[str, Any]:
    if _MYTHIC_DATA_PATH not in _cache:
        with _MYTHIC_DATA_PATH.open(encoding="utf-8") as f:
            _cache[_MYTHIC_DATA_PATH] = json.load(f)
        log(f"[Mythic] Loaded {_MYTHIC_DATA_PATH}")
    return _cache[_MYTHIC_DATA_PATH]
