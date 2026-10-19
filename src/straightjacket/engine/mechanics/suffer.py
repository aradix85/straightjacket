from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import ClockData, GameState, consequence
from .impacts import apply_impact
from .outcome_result import OutcomeResult, move_outcome_config


def suffer(game: GameState, meter: str, amount: int, result: OutcomeResult) -> None:
    _e = eng()
    lost = game.resources.damage(meter, amount)
    if lost:
        result.consequences.append(consequence("track_loss", track=meter, n=lost))
    remaining = amount - lost
    if remaining:
        game.resources.adjust_momentum(-remaining, floor=_e.momentum.floor, ceiling=_e.momentum.max)
        result.consequences.append(consequence("momentum_change", n=-remaining))
    at_zero = getattr(game.resources, meter) == 0
    if meter in _e.suffer.exhausted_impacts:
        impact = _e.suffer.exhausted_impacts[meter]
        if at_zero and apply_impact(game, impact):
            result.consequences.append(consequence("mark_impact", impact=impact))
        return
    endure = _e.suffer.endure_moves[meter]
    if at_zero or move_outcome_config(game, endure)["params"]["endure_always"]:
        result.follow_up_moves.append(endure)


def _dying_clock(game: GameState) -> ClockData | None:
    clock_type = eng().suffer.dying_clock.clock_type
    return next((c for c in game.world.clocks if c.clock_type == clock_type), None)


def start_dying_clock(game: GameState) -> None:
    if _dying_clock(game) is not None:
        return
    _e = eng()
    cfg = _e.suffer.dying_clock
    game.world.clocks.append(
        ClockData(
            name=cfg.name,
            clock_type=cfg.clock_type,
            segments=cfg.segments,
            trigger_description=cfg.trigger_description,
            owner_kind=_e.clocks.default_owner_kind,
            creation_source=cfg.clock_type,
        )
    )
    log(f"[Suffer] {cfg.name}: {cfg.segments} turns to raise {cfg.meter} above 0")


def tick_dying_clock(game: GameState, result: OutcomeResult) -> None:
    clock = _dying_clock(game)
    if clock is None:
        return
    _e = eng()
    cfg = _e.suffer.dying_clock
    if getattr(game.resources, cfg.meter) > 0:
        game.world.clocks.remove(clock)
        log(f"[Suffer] {clock.name} ends: {cfg.meter} above 0")
        return
    clock.filled += 1
    if clock.filled < clock.segments:
        log(f"[Suffer] {clock.name} {clock.filled}/{clock.segments}")
        return
    game.world.clocks.remove(clock)
    result.consequences.append(consequence("out_of_time", clock=clock.name))
    endure = _e.suffer.endure_moves[cfg.meter]
    result.follow_up_moves.append(move_outcome_config(game, endure)["params"]["threshold_move"])
    log(f"[Suffer] {clock.name} full: Face Death")
