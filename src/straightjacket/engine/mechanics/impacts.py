"""Impact mechanics: apply, clear, max_momentum adjustment, move blocking.

Impacts are persistent conditions that reduce max_momentum by 1 each.
Some block specific recovery moves (wounded blocks heal, etc.).
Permanent impacts never clear naturally — only via narrative events.

Data-driven from engine.yaml `impacts` section (typed as ImpactConfig).
"""

from __future__ import annotations

from ..engine_config import ImpactConfig
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState


def impact_config(key: str) -> ImpactConfig | None:
    """Get config for an impact key. Returns None if unknown."""
    return eng().impacts.get(key)


def recalc_max_momentum(game: GameState) -> None:
    """Set resources.max_momentum = base_max - len(impacts). Clamps current momentum."""
    base_max = eng().momentum.max
    new_max = max(0, base_max - len(game.impacts))
    game.resources.max_momentum = new_max
    if game.resources.momentum > new_max:
        game.resources.momentum = new_max


def apply_impact(game: GameState, key: str) -> bool:
    """Add impact if not already active. Returns True if applied."""
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
    """Remove impact if active and not permanent. Returns True if cleared."""
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
    """Return the impact key that blocks recovery on the given track, or ''."""
    for key in game.impacts:
        cfg = impact_config(key)
        if cfg and cfg.blocks_recovery == track:
            return key
    return ""


def impact_label(key: str) -> str:
    """Narrative label for UI/status display."""
    cfg = impact_config(key)
    return cfg.label if cfg else key
