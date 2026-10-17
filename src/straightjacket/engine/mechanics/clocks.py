from __future__ import annotations

from ..engine_loader import eng
from ..models import GameState
from .spawn_sources import EMERGENT_SOURCE_PREFIXES


def unique_clock_name(game: GameState, base_name: str) -> str:
    existing = {c.name for c in game.world.clocks}
    if base_name not in existing:
        return base_name
    template = eng().clocks.duplicate_name_template
    n = 2
    while template.format(name=base_name, n=n) in existing:
        n += 1
    return template.format(name=base_name, n=n)


def count_emergent_clocks(game: GameState) -> int:
    return sum(1 for c in game.world.clocks if c.creation_source.startswith(EMERGENT_SOURCE_PREFIXES))
