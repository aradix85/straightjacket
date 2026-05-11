from __future__ import annotations

import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..config_loader import PROJECT_ROOT
from ..datasworn.cascade import roll_oracle_cascade
from ..datasworn.settings import active_package
from ..engine_config_dataclasses import PlotPointRanges
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, ThreatData
from ..models_story import (
    CharacterListEntry,
    KeyedScene,
    NarrativeState,
    PlotlineEntry,
    PossibleEnding,
    Revelation,
    StoryAct,
    StoryBlueprint,
)


_AC_DATA_PATH = PROJECT_ROOT / "data" / "adventure_crafter.json"

_ac_data: dict[str, Any] | None = None


def _load_ac_data() -> dict[str, Any]:
    global _ac_data
    if _ac_data is None:
        with open(_AC_DATA_PATH, encoding="utf-8") as f:
            _ac_data = json.load(f)
        log(f"[AdventureCrafter] Loaded {_AC_DATA_PATH}")
        _validate_random_themes(_ac_data)
    return _ac_data


def _validate_random_themes(data: dict[str, Any]) -> None:
    cfg = eng().adventure_crafter
    json_table: dict[int, str] = {}
    for entry in data["random_themes"]:
        for face in range(entry["min"], entry["max"] + 1):
            json_table[face] = entry["theme"]
    if json_table != cfg.theme_die_table:
        diff = sorted(set(json_table.items()) ^ set(cfg.theme_die_table.items()))
        raise ValueError(
            f"adventure_crafter.yaml theme_die_table does not match "
            f"data/adventure_crafter.json random_themes. Differing entries: {diff}"
        )

    yaml_theme_set = set(cfg.themes)
    json_theme_set = set(json_table.values())
    if yaml_theme_set != json_theme_set:
        raise ValueError(
            f"adventure_crafter.yaml themes {sorted(yaml_theme_set)} does not match "
            f"random_themes theme set {sorted(json_theme_set)}"
        )


@dataclass(frozen=True)
class PlotPointResult:
    name: str
    special_range: str | None


@dataclass(frozen=True)
class PlotPointHit:
    theme: str
    priority: int
    roll: int
    name: str
    special_range: str | None


@dataclass(frozen=True)
class TurningPoint:
    plotline_id: str
    plotline_was_new: bool
    plot_points: list[PlotPointHit]
    flips_to_conclusion: bool


@dataclass
class ThemeAlternation:
    next_is_4: bool = True


def assign_themes(rng: random.Random) -> list[str]:
    cfg = eng().adventure_crafter
    return [cfg.theme_die_table[rng.randint(1, 10)] for _ in range(cfg.theme_slots)]


def lookup_plot_point(theme: str, roll: int) -> PlotPointResult:
    cfg = eng().adventure_crafter
    if theme not in cfg.themes:
        raise KeyError(f"unknown theme {theme!r}; expected one of {cfg.themes}")
    if not 1 <= roll <= 100:
        raise ValueError(f"plot-point roll {roll} outside 1..100")

    data = _load_ac_data()
    for entry in data["plot_points"]:
        themes = entry["themes"]
        if theme not in themes:
            continue
        if themes[theme]["min"] <= roll <= themes[theme]["max"]:
            return PlotPointResult(name=entry["name"], special_range=_special_range_for(roll, cfg.special_ranges))
    raise LookupError(
        f"no plot_points entry covers theme={theme!r} roll={roll}; "
        f"data/adventure_crafter.json plot_points may be incomplete"
    )


def _special_range_for(roll: int, ranges: PlotPointRanges) -> str | None:
    if ranges.conclusion_min <= roll <= ranges.conclusion_max:
        return "conclusion"
    if ranges.none_min <= roll <= ranges.none_max:
        return "none"
    if ranges.meta_min <= roll <= ranges.meta_max:
        return "meta"
    return None


def lookup_meta_plot_point(roll: int) -> str:
    if not 1 <= roll <= 100:
        raise ValueError(f"meta-plot-point roll {roll} outside 1..100")
    data = _load_ac_data()
    for entry in data["meta_plot_points"]:
        if entry["min"] <= roll <= entry["max"]:
            return entry["name"]
    raise LookupError(
        f"no meta_plot_points entry covers roll={roll}; data/adventure_crafter.json meta_plot_points may be incomplete"
    )


def lookup_theme_priority(roll: int, alternation: ThemeAlternation) -> int:
    if not 1 <= roll <= 10:
        raise ValueError(f"theme-priority roll {roll} outside 1..10")
    data = _load_ac_data()
    for entry in data["plot_point_theme_priority"]:
        if entry["min"] <= roll <= entry["max"]:
            priority = entry["priority"]
            if priority == "4_or_5":
                resolved = 4 if alternation.next_is_4 else 5
                alternation.next_is_4 = not alternation.next_is_4
                return resolved
            return int(priority)
    raise LookupError(f"no plot_point_theme_priority entry covers roll={roll}")


def _lookup_template_result(roll: int, template_key: str) -> str:
    if not 1 <= roll <= 100:
        raise ValueError(f"template roll {roll} outside 1..100")
    data = _load_ac_data()
    for entry in data[template_key]:
        if entry["min"] <= roll <= entry["max"]:
            return str(entry["result"])
    raise LookupError(f"no {template_key} entry covers roll={roll}")


def lookup_characters_template(roll: int) -> str:
    return _lookup_template_result(roll, "characters_list_template")


def lookup_plotlines_template(roll: int) -> str:
    return _lookup_template_result(roll, "plotlines_list_template")


def _ac_active_characters(narrative: NarrativeState) -> list[CharacterListEntry]:
    return [c for c in narrative.characters_list if c.ac_status in ("present", "returned", "upgraded", "downgraded")]


def _next_character_id(narrative: NarrativeState) -> str:
    n = 1
    while any(c.id == f"ac_char_{n}" for c in narrative.characters_list):
        n += 1
    return f"ac_char_{n}"


def _next_plotline_id(narrative: NarrativeState) -> str:
    n = 1
    while any(p.id == f"ac_plot_{n}" for p in narrative.plotlines_list):
        n += 1
    return f"ac_plot_{n}"


def _select_active_plotline(narrative: NarrativeState) -> PlotlineEntry | None:
    advancing = [p for p in narrative.plotlines_list if p.status == "advancement"]
    if not advancing:
        return None
    return min(advancing, key=lambda p: p.turning_point_count)


def _create_character(narrative: NarrativeState, name: str) -> CharacterListEntry:
    entry = CharacterListEntry(
        id=_next_character_id(narrative),
        name=name,
        entry_type="ac",
        weight=1,
        active=True,
        ac_status="present",
        ac_turning_point_count=0,
    )
    narrative.characters_list.append(entry)
    log(f"[AdventureCrafter] Created character '{name}' id={entry.id}")
    return entry


def _create_plotline(narrative: NarrativeState, name: str) -> PlotlineEntry:
    entry = PlotlineEntry(
        id=_next_plotline_id(narrative),
        name=name,
        status="advancement",
        turning_point_count=0,
    )
    narrative.plotlines_list.append(entry)
    log(f"[AdventureCrafter] Created plotline '{name}' id={entry.id}")
    return entry


def roll_turning_point(
    rng: random.Random,
    themes: list[str],
    narrative: NarrativeState,
) -> TurningPoint:
    cfg = eng().adventure_crafter
    if len(themes) != cfg.theme_slots:
        raise ValueError(f"themes length {len(themes)} != theme_slots {cfg.theme_slots}")

    plotline_roll = rng.randint(1, 100)
    plotline_template = lookup_plotlines_template(plotline_roll)
    existing_plotline = _select_active_plotline(narrative)

    if plotline_template == "new_plotline" or existing_plotline is None:
        plotline = _create_plotline(narrative, name=f"Plotline {len(narrative.plotlines_list) + 1}")
        plotline_was_new = True
    else:
        plotline = existing_plotline
        plotline_was_new = False

    rules = _load_ac_data()["turning_point_rules"]
    pp_min = rules["plot_points_per_turning_point"]["min"]
    pp_max = rules["plot_points_per_turning_point"]["max"]
    plot_point_count = rng.randint(pp_min, pp_max)

    alternation = ThemeAlternation()
    hits: list[PlotPointHit] = []
    flips_to_conclusion = False

    for _ in range(plot_point_count):
        priority_roll = rng.randint(1, 10)
        priority = lookup_theme_priority(priority_roll, alternation)
        theme_index = priority - 1
        if not 0 <= theme_index < len(themes):
            raise LookupError(f"theme priority {priority} outside themes list of length {len(themes)}")
        theme = themes[theme_index]

        plot_roll = rng.randint(1, 100)
        result = lookup_plot_point(theme, plot_roll)
        hits.append(
            PlotPointHit(
                theme=theme,
                priority=priority,
                roll=plot_roll,
                name=result.name,
                special_range=result.special_range,
            )
        )
        if result.special_range == "conclusion":
            flips_to_conclusion = True

    plotline.turning_point_count += 1
    if flips_to_conclusion and plotline.status == "advancement":
        plotline.status = "conclusion"
        log(f"[AdventureCrafter] Plotline '{plotline.name}' flipped to conclusion")

    return TurningPoint(
        plotline_id=plotline.id,
        plotline_was_new=plotline_was_new,
        plot_points=hits,
        flips_to_conclusion=flips_to_conclusion,
    )


MetaHandler = Callable[[NarrativeState, str | None], None]


def _apply_weight_delta(target: CharacterListEntry, delta: int) -> None:
    floor = eng().adventure_crafter.meta_handlers.weight_floor
    target.weight = max(floor, target.weight + delta)


def _meta_character_exits(narrative: NarrativeState, _active_plotline_id: str | None) -> None:
    rng = random.Random()
    active = _ac_active_characters(narrative)
    if not active:
        log("[AdventureCrafter] character_exits: no active character to exit")
        return
    target = rng.choice(active)
    target.ac_status = "exited"
    log(f"[AdventureCrafter] character_exits: '{target.name}' marked exited")


def _meta_character_returns(narrative: NarrativeState, _active_plotline_id: str | None) -> None:
    exited = [c for c in narrative.characters_list if c.ac_status == "exited"]
    if not exited:
        new_char = _create_character(narrative, name=f"Returning {len(narrative.characters_list) + 1}")
        new_char.ac_status = "returned"
        log(f"[AdventureCrafter] character_returns: no exited characters, created new '{new_char.name}'")
        return
    rng = random.Random()
    target = rng.choice(exited)
    target.ac_status = "returned"
    log(f"[AdventureCrafter] character_returns: '{target.name}' marked returned")


def _meta_character_steps_up(narrative: NarrativeState, _active_plotline_id: str | None) -> None:
    rng = random.Random()
    active = _ac_active_characters(narrative)
    if not active:
        log("[AdventureCrafter] character_steps_up: no active character")
        return
    target = rng.choice(active)
    _apply_weight_delta(target, eng().adventure_crafter.meta_handlers.weight_delta_step_up)
    log(f"[AdventureCrafter] character_steps_up: '{target.name}' weight → {target.weight}")


def _meta_character_steps_down(narrative: NarrativeState, _active_plotline_id: str | None) -> None:
    rng = random.Random()
    active = _ac_active_characters(narrative)
    if not active:
        log("[AdventureCrafter] character_steps_down: no active character")
        return
    target = rng.choice(active)
    _apply_weight_delta(target, eng().adventure_crafter.meta_handlers.weight_delta_step_down)
    log(f"[AdventureCrafter] character_steps_down: '{target.name}' weight → {target.weight}")


def _meta_character_downgrade(narrative: NarrativeState, _active_plotline_id: str | None) -> None:
    rng = random.Random()
    active = _ac_active_characters(narrative)
    if not active:
        log("[AdventureCrafter] character_downgrade: no active character")
        return
    target = rng.choice(active)
    target.ac_status = "downgraded"
    _apply_weight_delta(target, eng().adventure_crafter.meta_handlers.weight_delta_downgrade)
    log(f"[AdventureCrafter] character_downgrade: '{target.name}' downgraded weight → {target.weight}")


def _meta_character_upgrade(narrative: NarrativeState, _active_plotline_id: str | None) -> None:
    rng = random.Random()
    active = _ac_active_characters(narrative)
    if not active:
        log("[AdventureCrafter] character_upgrade: no active character")
        return
    target = rng.choice(active)
    target.ac_status = "upgraded"
    _apply_weight_delta(target, eng().adventure_crafter.meta_handlers.weight_delta_upgrade)
    log(f"[AdventureCrafter] character_upgrade: '{target.name}' upgraded weight → {target.weight}")


def _meta_plotline_combo(narrative: NarrativeState, active_plotline_id: str | None) -> None:
    advancing = [p for p in narrative.plotlines_list if p.status == "advancement"]
    if active_plotline_id is not None:
        advancing = [p for p in advancing if p.id != active_plotline_id]
    if len(advancing) < 2:
        log("[AdventureCrafter] plotline_combo: fewer than two advancing plotlines, skipped")
        return
    rng = random.Random()
    a, b = rng.sample(advancing, 2)
    a.name = f"{a.name} + {b.name}"
    b.status = "merged"
    log(f"[AdventureCrafter] plotline_combo: merged '{b.name}' into '{a.name}'")


_META_HANDLERS: dict[str, MetaHandler] = {
    "Character Exits The Adventure": _meta_character_exits,
    "Character Returns": _meta_character_returns,
    "Character Steps Up": _meta_character_steps_up,
    "Character Steps Down": _meta_character_steps_down,
    "Character Downgrade": _meta_character_downgrade,
    "Character Upgrade": _meta_character_upgrade,
    "Plotline Combo": _meta_plotline_combo,
}


def dispatch_meta(roll: int, narrative: NarrativeState, active_plotline_id: str | None) -> None:
    meta_name = lookup_meta_plot_point(roll)
    if meta_name not in _META_HANDLERS:
        raise KeyError(
            f"meta plot-point {meta_name!r} has no handler in _META_HANDLERS; "
            f"data/adventure_crafter.json meta_plot_points and "
            f"mechanics/adventure_crafter.py _META_HANDLERS have drifted"
        )
    _META_HANDLERS[meta_name](narrative, active_plotline_id)


def get_meta_handler_names() -> tuple[str, ...]:
    return tuple(_META_HANDLERS.keys())


@dataclass(frozen=True)
class CharacterTraits:
    special_trait: str
    identities: list[str]
    descriptors: list[str]


_IDENTITY_FLAG_MAX = 33
_DESCRIPTOR_FLAG_MAX = 21


def lookup_character_special_trait(roll: int) -> str:
    if not 1 <= roll <= 100:
        raise ValueError(f"character-special-trait roll {roll} outside 1..100")
    data = _load_ac_data()
    for entry in data["character_special_trait"]:
        if entry["min"] <= roll <= entry["max"]:
            return str(entry["trait"])
    raise LookupError(
        f"no character_special_trait entry covers roll={roll}; "
        f"data/adventure_crafter.json character_special_trait may be incomplete"
    )


def lookup_character_identity(roll: int) -> str:
    if not 1 <= roll <= 100:
        raise ValueError(f"character-identity roll {roll} outside 1..100")
    data = _load_ac_data()
    for entry in data["character_identity"]:
        if entry["min"] <= roll <= entry["max"]:
            return str(entry["identity"])
    raise LookupError(
        f"no character_identity entry covers roll={roll}; "
        f"data/adventure_crafter.json character_identity may be incomplete"
    )


def lookup_character_descriptor(roll: int) -> str:
    if not 1 <= roll <= 100:
        raise ValueError(f"character-descriptor roll {roll} outside 1..100")
    data = _load_ac_data()
    for entry in data["character_descriptors"]:
        if entry["min"] <= roll <= entry["max"]:
            return str(entry["descriptor"])
    raise LookupError(
        f"no character_descriptors entry covers roll={roll}; "
        f"data/adventure_crafter.json character_descriptors may be incomplete"
    )


def roll_character_traits(rng: random.Random) -> CharacterTraits:
    special_trait = lookup_character_special_trait(rng.randint(1, 100))

    identity_roll = rng.randint(1, 100)
    if identity_roll <= _IDENTITY_FLAG_MAX:
        identities = [
            lookup_character_identity(rng.randint(_IDENTITY_FLAG_MAX + 1, 100)),
            lookup_character_identity(rng.randint(_IDENTITY_FLAG_MAX + 1, 100)),
        ]
    else:
        identities = [lookup_character_identity(identity_roll)]

    descriptor_roll = rng.randint(1, 100)
    if descriptor_roll <= _DESCRIPTOR_FLAG_MAX:
        descriptors = [
            lookup_character_descriptor(rng.randint(_DESCRIPTOR_FLAG_MAX + 1, 100)),
            lookup_character_descriptor(rng.randint(_DESCRIPTOR_FLAG_MAX + 1, 100)),
        ]
    else:
        descriptors = [lookup_character_descriptor(descriptor_roll)]

    return CharacterTraits(
        special_trait=special_trait,
        identities=identities,
        descriptors=descriptors,
    )


_AC_SOURCE_PREFIX = "ac:"


def _ac_keyed_scene_count(narrative: NarrativeState) -> int:
    return sum(1 for ks in narrative.keyed_scenes if ks.source.startswith(_AC_SOURCE_PREFIX))


def _ac_already_spawned(narrative: NarrativeState, plot_point_name: str) -> bool:
    target = f"{_AC_SOURCE_PREFIX}{plot_point_name}"
    return any(ks.source == target for ks in narrative.keyed_scenes)


def _next_keyed_scene_id(narrative: NarrativeState) -> str:
    n = 1
    while any(ks.id == f"ks_ac_{n}" for ks in narrative.keyed_scenes):
        n += 1
    return f"ks_ac_{n}"


def spawn_keyed_scenes_for_turning_point(narrative: NarrativeState, turning_point: TurningPoint) -> int:
    cfg = eng().adventure_crafter
    mapping = cfg.keyed_scene_mapping
    cap = cfg.max_keyed_scenes_per_chapter

    spawned = 0
    for hit in turning_point.plot_points:
        if hit.special_range is not None:
            continue
        if hit.name not in mapping:
            continue
        if _ac_already_spawned(narrative, hit.name):
            continue
        if _ac_keyed_scene_count(narrative) >= cap:
            log(f"[AdventureCrafter] keyed-scene cap {cap} reached, skipping '{hit.name}'")
            break

        entry = mapping[hit.name]
        scene_id = _next_keyed_scene_id(narrative)
        scene = KeyedScene(
            id=scene_id,
            trigger_type=entry.trigger_type,
            trigger_value=entry.trigger_value,
            priority=entry.priority,
            narrative_hint=entry.narrative_hint,
            source=f"{_AC_SOURCE_PREFIX}{hit.name}",
        )
        narrative.keyed_scenes.append(scene)
        spawned += 1
        log(
            f"[AdventureCrafter] spawned keyed-scene '{scene_id}' from plot-point '{hit.name}' "
            f"(trigger {entry.trigger_type}={entry.trigger_value!r}, priority={entry.priority})"
        )
    return spawned


def _ac_threat_already_spawned(game: GameState, plot_point_name: str) -> bool:
    target = f"{_AC_SOURCE_PREFIX}{plot_point_name}"
    return any(t.creation_source == target for t in game.threats)


def _count_emergent_threats(game: GameState) -> int:
    return sum(1 for t in game.threats if t.creation_source.startswith(("random_event:", _AC_SOURCE_PREFIX)))


def _next_threat_id(game: GameState, prefix: str) -> str:
    n = 1
    while any(t.id == f"{prefix}{n}" for t in game.threats):
        n += 1
    return f"{prefix}{n}"


def spawn_threats_for_turning_point(game: GameState, turning_point: TurningPoint) -> int:
    cfg = eng().adventure_crafter
    mapping = cfg.threat_creation_mapping
    cap = cfg.max_threats_per_chapter

    pkg = active_package(game)
    if pkg is None:
        return 0

    spawned = 0
    for hit in turning_point.plot_points:
        if hit.special_range is not None:
            continue
        if hit.name not in mapping:
            continue
        if _ac_threat_already_spawned(game, hit.name):
            continue
        if _count_emergent_threats(game) >= cap:
            log(f"[AdventureCrafter] threat cap {cap} reached, skipping plot-point '{hit.name}'")
            break

        entry = mapping[hit.name]
        cascade = roll_oracle_cascade(pkg, pkg.oracle_paths.threats)
        name = cascade[-1].label
        description = " — ".join(step.text for step in cascade)
        threat_id = _next_threat_id(game, "threat_ac_")
        creation_source = f"{_AC_SOURCE_PREFIX}{hit.name}"

        threat = ThreatData.new(
            id=threat_id,
            name=name,
            category=entry.category,
            linked_vow_id=None,
            rank=entry.rank,
            description=description,
            creation_source=creation_source,
        )
        game.threats.append(threat)
        spawned += 1
        log(
            f"[AdventureCrafter] spawned threat '{name}' (id={threat_id}, rank={entry.rank}, "
            f"category={entry.category}) from plot-point '{hit.name}'"
        )
    return spawned


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
    return seeds[:limit]


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
    bp_cfg = eng().adventure_crafter.blueprint
    themes = assign_themes(rng)
    pre_rolled_count = bp_cfg.turning_points_pre_rolled
    turning_points: list[TurningPoint] = []
    for _ in range(pre_rolled_count):
        tp = roll_turning_point(rng, themes, narrative)
        turning_points.append(tp)
        spawn_keyed_scenes_for_turning_point(narrative, tp)
        spawn_threats_for_turning_point(game, tp)

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
    bp_cfg = eng().adventure_crafter.blueprint
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
    bp_cfg = eng().adventure_crafter.blueprint
    weights = list(eng().enums.dramatic_weights)

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
    earliest = seed.acts[0].scene_range[0] if seed.acts else 1
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
