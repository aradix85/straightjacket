from collections.abc import Sequence

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState
from .move_effects import OutcomeResult, apply_effects, parse_effects


def apply_boasts(game: GameState, boasts: Sequence[str], outcome: OutcomeResult) -> None:
    cfg = eng().boasts
    chosen = list(boasts)[: outcome.boast_slots]
    for name in chosen:
        option = cfg.options[name]
        effects = parse_effects([f"momentum +{cfg.momentum_per_boast}", *option.effects])
        applied = apply_effects(game, effects)
        outcome.consequences.append(option.description)
        outcome.consequences.extend(applied.consequences)
        if applied.combat_position:
            outcome.combat_position = applied.combat_position
    if chosen:
        log(f"[Boast] {', '.join(chosen)} ({len(chosen)} of {outcome.boast_slots} allowed)")
