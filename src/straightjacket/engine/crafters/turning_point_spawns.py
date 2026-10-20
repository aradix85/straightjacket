from __future__ import annotations

from ..gamemaster.clocks import spawn_emergent_clock
from ..gamemaster.keyed_scenes import add_keyed_scene, has_keyed_scene_from
from ..gamemaster.questions import answers
from ..gamemaster.spawn_sources import AC_SOURCE_PREFIX
from ..logging_util import log
from ..models import GameState
from ..models_story import NarrativeState
from .adventure_crafter import TurningPoint
from .config import crafter


def plot_point_source(plot_point: str) -> str:
    return f"{AC_SOURCE_PREFIX}{plot_point}"


def _ac_keyed_scene_count(narrative: NarrativeState) -> int:
    return sum(1 for ks in narrative.keyed_scenes if ks.source.startswith(AC_SOURCE_PREFIX))


def spawn_keyed_scenes_for_turning_point(narrative: NarrativeState, turning_point: TurningPoint) -> None:
    cfg = crafter().adventure_crafter
    mapping = cfg.keyed_scene_mapping
    cap = cfg.max_keyed_scenes_per_chapter

    for hit in turning_point.plot_points:
        if hit.special_range is not None:
            continue
        if hit.name not in mapping:
            continue
        source = plot_point_source(hit.name)
        if has_keyed_scene_from(narrative, source):
            continue
        if _ac_keyed_scene_count(narrative) >= cap:
            log(f"[AdventureCrafter] keyed-scene cap {cap} reached, skipping '{hit.name}'")
            break

        entry = mapping[hit.name]
        scene = add_keyed_scene(
            narrative,
            trigger_type=entry.trigger_type,
            trigger_value=entry.trigger_value,
            priority=entry.priority,
            narrative_hint=entry.narrative_hint,
            source=source,
        )
        log(
            f"[AdventureCrafter] spawned keyed-scene '{scene.id}' from plot-point '{hit.name}' "
            f"(trigger {entry.trigger_type}={entry.trigger_value!r}, priority={entry.priority})"
        )


def spawn_dangers_for_turning_point(game: GameState, turning_point: TurningPoint) -> None:
    danger_plot_points = crafter().adventure_crafter.danger_plot_points
    for hit in turning_point.plot_points:
        if hit.special_range is None and hit.name in danger_plot_points:
            answers().add_danger(game, hit.name, plot_point_source(hit.name), None)


def spawn_clocks_for_turning_point(game: GameState, turning_point: TurningPoint) -> None:
    mapping = crafter().adventure_crafter.clock_creation_mapping
    for hit in turning_point.plot_points:
        if hit.special_range is None and hit.name in mapping:
            spawn_emergent_clock(
                game,
                base_name=hit.name,
                clock_type=mapping[hit.name].clock_type,
                trigger_description=hit.name,
                source=plot_point_source(hit.name),
            )
