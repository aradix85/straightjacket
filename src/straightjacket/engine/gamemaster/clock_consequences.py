from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import ClockData, ClockFillResult, GameState
from ..ruleset.tracks import complete_track
from .spawn_sources import CLOCK_KEYED_SOURCE_PREFIX


def _has_pending_keyed_scene_for_clock(game: GameState, clock_name: str) -> bool:
    target_prefix = f"{CLOCK_KEYED_SOURCE_PREFIX}{clock_name}:"
    return any(ks.source.startswith(target_prefix) for ks in game.narrative.keyed_scenes)


def resolve_clock_fill(game: GameState, clock: ClockData) -> ClockFillResult | None:
    if _has_pending_keyed_scene_for_clock(game, clock.name):
        log(f"[ClockFill] '{clock.name}' has attached keyed-scene, default suppressed")
        return None

    tag_text = eng().clocks.fill_consequences[clock.clock_type].tag_template.format(clock_name=clock.name)

    if clock.clock_type == "progress":
        _complete_linked_track(game, clock)

    log(f"[ClockFill] '{clock.name}' (type={clock.clock_type}) fired → tag emitted")
    return ClockFillResult(clock_name=clock.name, clock_type=clock.clock_type, tag_text=tag_text)


def _complete_linked_track(game: GameState, clock: ClockData) -> None:
    for track in game.progress_tracks:
        if track.name == clock.name and track.status == "active":
            complete_track(game, track.id, "completed")
            log(f"[ClockFill] linked progress track '{track.name}' completed")
            return
