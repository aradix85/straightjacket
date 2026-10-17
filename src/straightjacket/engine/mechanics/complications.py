from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import ClockData, GameState
from .clocks import count_emergent_clocks, unique_clock_name
from .spawn_sources import COMPLICATION_SOURCE_PREFIX


def is_complication(clock: ClockData) -> bool:
    return clock.creation_source.startswith(COMPLICATION_SOURCE_PREFIX)


def open_complications(game: GameState) -> list[ClockData]:
    return [c for c in game.world.clocks if is_complication(c) and not c.fired]


def spawn_complication_clock(game: GameState, kind: str, danger: str) -> ClockData | None:
    cfg = eng().clocks
    if len(open_complications(game)) >= cfg.complication.max_open:
        log(f"[Complication] {cfg.complication.max_open} complication clock(s) already open, no clock for '{danger}'")
        return None
    if count_emergent_clocks(game) >= cfg.max_clocks_per_chapter:
        log(f"[Complication] emergent clock cap {cfg.max_clocks_per_chapter} reached, no clock for '{danger}'")
        return None
    clock = ClockData(
        name=unique_clock_name(game, danger),
        clock_type="threat",
        segments=cfg.complication.segments,
        trigger_description=danger,
        owner_kind="world",
        creation_source=f"{COMPLICATION_SOURCE_PREFIX}{kind}:{game.narrative.scene_count}",
    )
    game.world.clocks.append(clock)
    log(f"[Complication] clock '{clock.name}' started from {kind} ({clock.segments} segments)")
    return clock


def avert_complication(game: GameState, name: str) -> bool:
    clock = next((c for c in open_complications(game) if c.name == name), None)
    if clock is None:
        return False
    game.world.clocks.remove(clock)
    log(f"[Complication] clock '{name}' averted at {clock.filled}/{clock.segments}")
    return True
