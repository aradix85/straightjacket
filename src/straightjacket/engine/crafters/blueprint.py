from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from ..engine_loader import eng
from ..gamemaster.config import gm
from ..models import GameState
from ..models_story import NarrativeState, PlotlineEntry, PossibleEnding, Revelation, StoryAct, StoryBlueprint
from .adventure_crafter import PlotPointHit, TurningPoint, assign_themes, roll_turning_point
from .config import crafter
from .turning_point_spawns import (
    spawn_clocks_for_turning_point,
    spawn_dangers_for_turning_point,
    spawn_keyed_scenes_for_turning_point,
)


@dataclass(frozen=True)
class ActSeed:
    phase: str
    scene_range: list[int]
    turning_point: TurningPoint | None


@dataclass(frozen=True)
class BlueprintSeed:
    structure_type: str
    themes: list[str]
    acts: list[ActSeed]
    revelation_seeds: list[PlotPointHit]
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


def _flatten_revelation_seeds(turning_points: list[TurningPoint], limit: int) -> list[PlotPointHit]:
    seeds: list[PlotPointHit] = []
    for tp in turning_points:
        for hit in tp.plot_points:
            if hit.special_range is None and len(seeds) < limit:
                seeds.append(hit)
    return seeds


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
    pre_rolled_count = bp_cfg.turning_points_pre_rolled
    turning_points: list[TurningPoint] = []
    for _ in range(pre_rolled_count):
        tp = roll_turning_point(rng, themes, narrative)
        turning_points.append(tp)
        spawn_keyed_scenes_for_turning_point(narrative, tp)
        spawn_dangers_for_turning_point(game, tp)
        spawn_clocks_for_turning_point(game, tp)

    act_count = bp_cfg.acts_three_act
    phases = bp_cfg.three_act_phases
    if len(phases) != act_count:
        raise ValueError(f"three_act_phases length {len(phases)} does not match acts_three_act {act_count}")
    scene_ranges = _scene_ranges_evenly_split(list(eng().scene_range_default), act_count)
    acts: list[ActSeed] = []
    for i in range(act_count):
        tp_for_act = turning_points[i] if i < len(turning_points) else None
        acts.append(ActSeed(phase=phases[i], scene_range=scene_ranges[i], turning_point=tp_for_act))

    revelation_seeds = _flatten_revelation_seeds(turning_points, bp_cfg.revelations_per_blueprint)
    ending_seeds = _ending_seeds(narrative, bp_cfg.possible_endings_per_blueprint)

    return BlueprintSeed(
        structure_type="3act",
        themes=themes,
        acts=acts,
        revelation_seeds=revelation_seeds,
        ending_seeds=ending_seeds,
    )


def assemble_blueprint_seed_kishotenketsu(
    rng: random.Random,
    game: GameState,
) -> BlueprintSeed:
    narrative = game.narrative
    bp_cfg = crafter().adventure_crafter.blueprint
    themes = assign_themes(rng)

    act_count = bp_cfg.acts_kishotenketsu
    phases = bp_cfg.kishotenketsu_phases
    if len(phases) != act_count:
        raise ValueError(f"kishotenketsu_phases length {len(phases)} does not match acts_kishotenketsu {act_count}")
    scene_ranges = _scene_ranges_evenly_split(list(eng().scene_range_default), act_count)
    acts = [ActSeed(phase=phases[i], scene_range=scene_ranges[i], turning_point=None) for i in range(act_count)]

    revelation_seeds: list[PlotPointHit] = []
    ending_seeds = _ending_seeds(narrative, bp_cfg.possible_endings_per_blueprint)

    return BlueprintSeed(
        structure_type="kishotenketsu",
        themes=themes,
        acts=acts,
        revelation_seeds=revelation_seeds,
        ending_seeds=ending_seeds,
    )


def materialize_blueprint(seed: BlueprintSeed, voicing: dict[str, Any]) -> StoryBlueprint:
    bp_cfg = crafter().adventure_crafter.blueprint
    weights = list(gm().enums.dramatic_weights)

    voicing_acts = list(voicing["acts"])
    if len(voicing_acts) != len(seed.acts):
        raise ValueError(f"voicing returned {len(voicing_acts)} acts, seed has {len(seed.acts)}")
    acts: list[StoryAct] = []
    for i, act_seed in enumerate(seed.acts):
        v = voicing_acts[i]
        acts.append(
            StoryAct(
                phase=act_seed.phase,
                title=v["title"],
                goal=v["goal"],
                scene_range=list(act_seed.scene_range),
                mood=v["mood"],
                transition_trigger=v["transition_trigger"],
            )
        )

    voicing_revelations = list(voicing["revelations"])
    if len(voicing_revelations) != bp_cfg.revelations_per_blueprint:
        raise ValueError(
            f"voicing returned {len(voicing_revelations)} revelations, expected {bp_cfg.revelations_per_blueprint}"
        )
    earliest = seed.acts[0].scene_range[0]
    revelations: list[Revelation] = []
    for i, v in enumerate(voicing_revelations):
        weight = weights[i % len(weights)]
        revelations.append(
            Revelation(
                id=f"revelation_{i + 1}",
                content=v["content"],
                earliest_scene=earliest,
                dramatic_weight=weight,
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
        structure_type=seed.structure_type,
        acts=acts,
        revelations=revelations,
        possible_endings=possible_endings,
        revealed=[],
        triggered_transitions=[],
        triggered_director_phases=[],
        story_complete=False,
    )
