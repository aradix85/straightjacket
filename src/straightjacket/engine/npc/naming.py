from __future__ import annotations

import random

from ..datasworn.settings import active_package
from ..engine_loader import eng
from ..models import GameState


def roll_oracle_name(game: GameState) -> str:
    if active_package(game) is None:
        return ""
    from ..mechanics import generate_entity

    naming = eng().naming
    parts = generate_entity(game, naming.category).results
    callsign = parts.pop(naming.callsign_role, "")
    if callsign and random.random() < naming.callsign_probability:
        return callsign.strip()
    return " ".join(parts.values()).strip()
