from __future__ import annotations

import random
from typing import TYPE_CHECKING

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.generation import generate_entity

if TYPE_CHECKING:
    from straightjacket.engine.models import GameState


def roll_oracle_name(game: GameState) -> str:
    naming = gm().naming
    parts = generate_entity(game, naming.category).results
    callsign = parts.pop(naming.callsign_role, "")
    if callsign and random.random() < naming.callsign_probability:
        return callsign.strip()
    return " ".join(parts.values()).strip()
