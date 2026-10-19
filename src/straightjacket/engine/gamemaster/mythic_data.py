from __future__ import annotations

import json
from typing import Any

from ..config_loader import PROJECT_ROOT
from ..logging_util import log

_MYTHIC_DATA_PATH = PROJECT_ROOT / "data" / "mythic_gme_2e.json"

_mythic: dict[str, Any] | None = None


def load_mythic() -> dict[str, Any]:
    global _mythic
    if _mythic is None:
        with _MYTHIC_DATA_PATH.open(encoding="utf-8") as f:
            _mythic = json.load(f)
        log(f"[Mythic] Loaded {_MYTHIC_DATA_PATH}")
    return _mythic
