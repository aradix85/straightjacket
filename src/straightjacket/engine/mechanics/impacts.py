from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState


def recalc_max_momentum(game: GameState) -> None:
    base_max = eng().momentum.max
    new_max = max(0, base_max - len(game.impacts))
    game.resources.max_momentum = new_max
    if game.resources.momentum > new_max:
        game.resources.momentum = new_max


def apply_impact(game: GameState, key: str) -> bool:
    if key in game.impacts:
        return False
    if key not in eng().impacts:
        raise KeyError(f"Unknown impact {key!r}; configured: {sorted(eng().impacts)}")
    game.impacts.append(key)
    recalc_max_momentum(game)
    log(f"[Impact] {key} applied — max_momentum → {game.resources.max_momentum}")
    return True


def clear_impact(game: GameState, key: str) -> bool:
    if key not in game.impacts:
        return False
    if eng().impacts[key].permanent:
        log(f"[Impact] Cannot clear permanent impact: {key}")
        return False
    game.impacts.remove(key)
    recalc_max_momentum(game)
    log(f"[Impact] {key} cleared — max_momentum → {game.resources.max_momentum}")
    return True


def blocks_recovery(game: GameState, track: str) -> str:
    for key in game.impacts:
        if eng().impacts[key].blocks_recovery == track:
            return key
    return ""


def impact_label(key: str) -> str:
    return eng().impacts[key].label
