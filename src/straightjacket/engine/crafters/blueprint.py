from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from ..engine_loader import eng
from ..gamemaster.config import gm
from ..gamemaster.keyed_scenes import has_keyed_scene_from
from ..models import GameState
from ..models_story import NarrativeState, PlotlineEntry, PossibleEnding, Revelation, StoryAct, StoryBlueprint
from .adventure_crafter import PlotPointHit, TurningPoint, assign_themes, roll_turning_point
from .config import crafter
from .turning_point_spawns import (
    plot_point_source,
    spawn_clocks_for_turning_point,
    spawn_dangers_for_turning_point,
    spawn_keyed_scenes_for_turning_point,
)


@dataclass(frozen=True)
class ActSeed:
    phase: str
    scene_range: list[int]
    turning_point: TurningPoint
    revelation_seed: PlotPointHit | None
    revelation_trigger: str


@dataclass(frozen=True)
class BlueprintSeed:
    themes: list[str]
    acts: list[ActSeed]
    ending_seeds: list[PlotlineEntry]


def _scene_ranges_evenly_split(total_range: list[int], act_count: int) -> list[list[int]]:
    if len(total_range) != 2:
        raise ValueError(f"scene_range_default must have length 2, got {total_range}")
    if act_count < 1:
        raise ValueError(f"act_count must be >= 1, got {act_count}")
    start, end = total_range[0], total_range[1]
    span = end - start + 1
    base = span // act_count
    remainder = span % act_count
    ranges: list[list[int]] = []
    cursor = start
    for i in range(act_count):
        size = base + (1 if i < remainder else 0)
        ranges.append([cursor, cursor + size - 1])
        cursor += size
    return ranges


def _revelation_seed(narrative: NarrativeState, turning_point: TurningPoint) -> tuple[PlotPointHit | None, str]:
    regular = [hit for hit in turning_point.plot_points if hit.special_range is None]
    for hit in regular:
        source = plot_point_source(hit.name)
        if has_keyed_scene_from(narrative, source):
            return hit, source
    return (regular[0] if regular else None), ""


def _ending_seeds(narrative: NarrativeState, limit: int) -> list[PlotlineEntry]:
    advancing = [p for p in narrative.plotlines_list if p.status == "advancement"]
    if len(advancing) >= limit:
        return advancing[:limit]
    return list(narrative.plotlines_list)[:limit]


def assemble_blueprint_seed_from_ac(
    rng: random.Random,
    game: GameState,
) -> BlueprintSeed:
    narrative = game.narrative
    bp_cfg = crafter().adventure_crafter.blueprint
    themes = assign_themes(rng)
    phases = bp_cfg.act_phases
    turning_points: list[TurningPoint] = []
    for _ in phases:
        tp = roll_turning_point(rng, themes, narrative)
        turning_points.append(tp)
        spawn_keyed_scenes_for_turning_point(narrative, tp)
        spawn_dangers_for_turning_point(game, tp)
        spawn_clocks_for_turning_point(game, tp)

    scene_ranges = _scene_ranges_evenly_split(list(eng().scene_range_default), len(phases))
    acts: list[ActSeed] = []
    for phase, scene_range, tp in zip(phases, scene_ranges, turning_points, strict=True):
        revelation_seed, revelation_trigger = _revelation_seed(narrative, tp)
        acts.append(
            ActSeed(
                phase=phase,
                scene_range=scene_range,
                turning_point=tp,
                revelation_seed=revelation_seed,
                revelation_trigger=revelation_trigger,
            )
        )

    return BlueprintSeed(
        themes=themes,
        acts=acts,
        ending_seeds=_ending_seeds(narrative, bp_cfg.possible_endings_per_blueprint),
    )


def materialize_blueprint(seed: BlueprintSeed, voicing: dict[str, Any]) -> StoryBlueprint:
    bp_cfg = crafter().adventure_crafter.blueprint
    weights = list(gm().enums.dramatic_weights)

    voicing_acts = list(voicing["acts"])
    if len(voicing_acts) != len(seed.acts):
        raise ValueError(f"voicing returned {len(voicing_acts)} acts, seed has {len(seed.acts)}")
    voicing_revelations = list(voicing["revelations"])
    if len(voicing_revelations) != len(seed.acts):
        raise ValueError(f"voicing returned {len(voicing_revelations)} revelations, seed has {len(seed.acts)} acts")
    acts: list[StoryAct] = []
    revelations: list[Revelation] = []
    for i, (act_seed, act, revelation) in enumerate(zip(seed.acts, voicing_acts, voicing_revelations, strict=True)):
        acts.append(
            StoryAct(
                phase=act_seed.phase,
                title=act["title"],
                goal=act["goal"],
                scene_range=list(act_seed.scene_range),
                mood=act["mood"],
                transition_trigger=act["transition_trigger"],
            )
        )
        revelations.append(
            Revelation(
                id=f"revelation_{i + 1}",
                content=revelation["content"],
                act_number=i + 1,
                keyed_scene_source=act_seed.revelation_trigger,
                dramatic_weight=weights[i % len(weights)],
            )
        )

    voicing_endings = list(voicing["possible_endings"])
    if len(voicing_endings) != bp_cfg.possible_endings_per_blueprint:
        raise ValueError(
            f"voicing returned {len(voicing_endings)} endings, expected {bp_cfg.possible_endings_per_blueprint}"
        )
    possible_endings: list[PossibleEnding] = []
    for v in voicing_endings:
        possible_endings.append(PossibleEnding(type=v["type"], description=v["description"]))

    return StoryBlueprint(
        central_conflict=voicing["central_conflict"],
        antagonist_force=voicing["antagonist_force"],
        thematic_thread=voicing["thematic_thread"],
        acts=acts,
        revelations=revelations,
        possible_endings=possible_endings,
        revealed=[],
        triggered_transitions=[],
        triggered_director_phases=[],
        story_complete=False,
    )
