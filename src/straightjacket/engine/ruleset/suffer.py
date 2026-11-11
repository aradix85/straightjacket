from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.gamemaster.clocks import new_clock
from straightjacket.engine.logging_util import log
from straightjacket.engine.models import consequence
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.impacts import apply_impact, impact_consequence
from straightjacket.engine.ruleset.meters import adjust_momentum, lose
from straightjacket.engine.ruleset.outcome_result import suffer_params

if TYPE_CHECKING:
    from straightjacket.engine.models import ClockData, GameState
    from straightjacket.engine.ruleset.outcome_result import OutcomeResult


def suffer(game: GameState, meter: str, amount: int, result: OutcomeResult) -> None:
    lost = lose(game, meter, amount)
    if lost:
        result.consequences.append(consequence("track_loss", track=meter, n=lost))
    remaining = amount - lost
    if remaining:
        adjust_momentum(game, -remaining)
        result.consequences.append(consequence("momentum_change", n=-remaining))
    at_zero = game.resources.meters[meter] == 0
    if meter in rules().suffer.exhausted_impacts:
        impact = rules().suffer.exhausted_impacts[meter]
        if at_zero and apply_impact(game, impact):
            result.consequences.append(impact_consequence(game, "mark_impact", impact))
        return
    endure = rules().suffer.endure_moves[meter]
    if at_zero or suffer_params(game, endure).endure_always:
        result.follow_up_moves.append(endure)


def _dying_clock(game: GameState) -> ClockData | None:
    clock_type = rules().suffer.dying_clock.clock_type
    return next((c for c in game.world.clocks if c.clock_type == clock_type), None)


def start_dying_clock(game: GameState) -> None:
    if _dying_clock(game) is not None:
        return
    cfg = rules().suffer.dying_clock
    game.world.clocks.append(
        new_clock(
            name=cfg.name,
            clock_type=cfg.clock_type,
            segments=cfg.segments,
            filled=0,
            trigger_description=cfg.trigger_description,
            creation_source=cfg.clock_type,
        )
    )
    log(f"[Suffer] {cfg.name}: {cfg.segments} turns to raise {cfg.meter} above 0")


def tick_dying_clock(game: GameState, result: OutcomeResult) -> None:
    clock = _dying_clock(game)
    if clock is None:
        return
    cfg = rules().suffer.dying_clock
    if game.resources.meters[cfg.meter] > 0:
        game.world.clocks.remove(clock)
        log(f"[Suffer] {clock.name} ends: {cfg.meter} above 0")
        return
    clock.filled += 1
    if clock.filled < clock.segments:
        log(f"[Suffer] {clock.name} {clock.filled}/{clock.segments}")
        return
    game.world.clocks.remove(clock)
    result.consequences.append(consequence("out_of_time", clock=clock.name))
    endure = rules().suffer.endure_moves[cfg.meter]
    result.follow_up_moves.append(suffer_params(game, endure).threshold_move)
    log(f"[Suffer] {clock.name} full: Face Death")
