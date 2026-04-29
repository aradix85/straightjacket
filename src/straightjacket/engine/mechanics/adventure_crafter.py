from __future__ import annotations

import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..config_loader import PROJECT_ROOT
from ..engine_config_dataclasses import PlotPointRanges
from ..engine_loader import eng
from ..logging_util import log
from ..models_story import CharacterListEntry, NarrativeState, PlotlineEntry


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
