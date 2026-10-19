from collections.abc import Sequence

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, consequence
from .move_effects import apply_effects, parse_effects
from .outcome_result import OutcomeResult


def apply_boasts(game: GameState, boasts: Sequence[str], outcome: OutcomeResult) -> None:
    cfg = eng().boasts
    chosen = list(boasts)[: outcome.boast_slots]
    for name in chosen:
        option = cfg.options[name]
        effects = parse_effects([f"momentum +{cfg.momentum_per_boast}", *option.effects])
        applied = apply_effects(game, effects)
        outcome.consequences.append(consequence("told", text=option.description))
        outcome.consequences.extend(applied.consequences)
        outcome.follow_up_moves.extend(applied.follow_up_moves)
        if applied.combat_position:
            outcome.combat_position = applied.combat_position
    if chosen:
        log(f"[Boast] {', '.join(chosen)} ({len(chosen)} of {outcome.boast_slots} allowed)")
