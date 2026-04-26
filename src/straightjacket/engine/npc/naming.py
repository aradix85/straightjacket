from __future__ import annotations

import random

from ..datasworn.settings import active_package
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState


def roll_oracle_name(game: GameState) -> str:
    pkg = active_package(game)
    if pkg is None:
        return ""

    paths = pkg.oracle_paths.names
    if not paths:
        return ""

    def roll(path: str) -> str:
        data = pkg.oracle_data_for(path)
        if data is None:
            raise KeyError(f"Oracle '{path}' not found in setting chain for {pkg.id}")
        return data.roll_oracle(path)

    try:
        if len(paths) == 1:
            name = roll(paths[0])
        elif len(paths) == 2:
            name = f"{roll(paths[0])} {roll(paths[1])}"
        else:
            if random.random() < eng().naming.callsign_probability:
                name = roll(paths[-1])
            else:
                name = f"{roll(paths[0])} {roll(paths[1])}"
    except KeyError as e:
        log(f"[NPC name] Oracle roll failed: {e}", level="warning")
        return ""

    return name.strip()
