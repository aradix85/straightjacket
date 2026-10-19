from __future__ import annotations

import random

from ...models import GameState
from ..config import gm


def roll_oracle_name(game: GameState) -> str:
    from ..generation import generate_entity

    naming = gm().naming
    parts = generate_entity(game, naming.category).results
    callsign = parts.pop(naming.callsign_role, "")
    if callsign and random.random() < naming.callsign_probability:
        return callsign.strip()
    return " ".join(parts.values()).strip()
