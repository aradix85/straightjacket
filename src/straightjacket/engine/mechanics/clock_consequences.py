from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import ClockData, ClockFillResult, GameState
from .spawn_sources import CLOCK_KEYED_SOURCE_PREFIX


def _has_pending_keyed_scene_for_clock(game: GameState, clock_name: str) -> bool:
    target_prefix = f"{CLOCK_KEYED_SOURCE_PREFIX}{clock_name}:"
    return any(ks.source.startswith(target_prefix) for ks in game.narrative.keyed_scenes)


def resolve_clock_fill(game: GameState, clock: ClockData) -> ClockFillResult | None:
    cfg = eng().clocks.fill_consequences
    if clock.clock_type not in cfg:
        log(f"[ClockFill] no fill-consequence entry for clock_type='{clock.clock_type}', skipping")
        return None

    if _has_pending_keyed_scene_for_clock(game, clock.name):
        log(f"[ClockFill] '{clock.name}' has attached keyed-scene, default suppressed")
        return None

    entry = cfg[clock.clock_type]
    tag_text = entry.tag_template.format(clock_name=clock.name)
    track_completed = False

    if clock.clock_type == "progress":
        track_completed = _try_complete_linked_track(game, clock)

    log(f"[ClockFill] '{clock.name}' (type={clock.clock_type}) fired → tag emitted")
    return ClockFillResult(
        clock_name=clock.name,
        clock_type=clock.clock_type,
        tag_text=tag_text,
        track_completed=track_completed,
    )


def _try_complete_linked_track(game: GameState, clock: ClockData) -> bool:
    from ..game.tracks import complete_track  # circular-break: game/__init__ → ai → prompt_blocks → mechanics

    for track in game.progress_tracks:
        if track.name == clock.name and track.status == "active":
            complete_track(game, track.id, "completed")
            log(f"[ClockFill] linked progress track '{track.name}' completed")
            return True
    return False
