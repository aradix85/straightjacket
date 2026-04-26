from __future__ import annotations

from ..engine_config import ImpactConfig
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState


def impact_config(key: str) -> ImpactConfig | None:
    return eng().impacts.get(key)


def recalc_max_momentum(game: GameState) -> None:
    base_max = eng().momentum.max
    new_max = max(0, base_max - len(game.impacts))
    game.resources.max_momentum = new_max
    if game.resources.momentum > new_max:
        game.resources.momentum = new_max


def apply_impact(game: GameState, key: str) -> bool:
    if key in game.impacts:
        return False
    if impact_config(key) is None:
        log(f"[Impact] Unknown impact key: {key!r}", level="warning")
        return False
    game.impacts.append(key)
    recalc_max_momentum(game)
    log(f"[Impact] {key} applied — max_momentum → {game.resources.max_momentum}")
    return True


def clear_impact(game: GameState, key: str) -> bool:
    if key not in game.impacts:
        return False
    cfg = impact_config(key)
    if cfg is None:
        return False
    if cfg.permanent:
        log(f"[Impact] Cannot clear permanent impact: {key}")
        return False
    game.impacts.remove(key)
    recalc_max_momentum(game)
    log(f"[Impact] {key} cleared — max_momentum → {game.resources.max_momentum}")
    return True


def blocks_recovery(game: GameState, track: str) -> str:
    for key in game.impacts:
        cfg = impact_config(key)
        if cfg and cfg.blocks_recovery == track:
            return key
    return ""


def impact_label(key: str) -> str:
    cfg = impact_config(key)
    return cfg.label if cfg else key
