from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Any

from ..config_loader import PROJECT_ROOT
from ..ids import next_id
from ..logging_util import log
from ..models_story import NarrativeState, PlotlineEntry
from .config import PlotPointRanges, crafter

_AC_DATA_PATH = PROJECT_ROOT / "data" / "adventure_crafter.json"
_PLOTLINE_ID_PREFIX = "ac_plot_"

_ac_data: dict[str, Any] | None = None


def load_ac_data() -> dict[str, Any]:
    global _ac_data
    if _ac_data is None:
        with _AC_DATA_PATH.open(encoding="utf-8") as f:
            _ac_data = json.load(f)
        log(f"[AdventureCrafter] Loaded {_AC_DATA_PATH}")
        _validate_random_themes(_ac_data)
    return _ac_data


def _validate_random_themes(data: dict[str, Any]) -> None:
    cfg = crafter().adventure_crafter
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
    name: str
    special_range: str | None


@dataclass(frozen=True)
class TurningPoint:
    plot_points: list[PlotPointHit]
    plotline: str
    opens_plotline: bool
    concludes_plotline: bool


@dataclass
class ThemeAlternation:
    next_is_4: bool


def _table_roll(rng: random.Random) -> int:
    return rng.randint(1, crafter().adventure_crafter_dice.table_die)


def assign_themes(rng: random.Random) -> list[str]:
    cfg = crafter().adventure_crafter
    die = crafter().adventure_crafter_dice.theme_die
    return [cfg.theme_die_table[rng.randint(1, die)] for _ in range(cfg.theme_slots)]


def lookup_plot_point(theme: str, roll: int) -> PlotPointResult:
    cfg = crafter().adventure_crafter
    data = load_ac_data()
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
    data = load_ac_data()
    for entry in data["meta_plot_points"]:
        if entry["min"] <= roll <= entry["max"]:
            result: str = entry["name"]
            return result
    raise LookupError(
        f"no meta_plot_points entry covers roll={roll}; data/adventure_crafter.json meta_plot_points may be incomplete"
    )


def lookup_theme_priority(roll: int, alternation: ThemeAlternation) -> int:
    data = load_ac_data()
    for entry in data["plot_point_theme_priority"]:
        if entry["min"] <= roll <= entry["max"]:
            priority = str(entry["priority"])
            if "_or_" in priority:
                first, second = (int(p) for p in priority.split("_or_"))
                resolved = first if alternation.next_is_4 else second
                alternation.next_is_4 = not alternation.next_is_4
                return resolved
            return int(priority)
    raise LookupError(f"no plot_point_theme_priority entry covers roll={roll}")


def _lookup_template_result(roll: int, template_key: str) -> str:
    data = load_ac_data()
    for entry in data[template_key]:
        if entry["min"] <= roll <= entry["max"]:
            return str(entry["result"])
    raise LookupError(f"no {template_key} entry covers roll={roll}")


def lookup_characters_template(roll: int) -> str:
    return _lookup_template_result(roll, "characters_list_template")


def lookup_plotlines_template(roll: int) -> str:
    return _lookup_template_result(roll, "plotlines_list_template")


def _select_active_plotline(narrative: NarrativeState) -> PlotlineEntry | None:
    advancing = [p for p in narrative.plotlines_list if p.status == "advancement"]
    if not advancing:
        return None
    return min(advancing, key=lambda p: p.turning_point_count)


def _create_plotline(narrative: NarrativeState, name: str) -> PlotlineEntry:
    entry = PlotlineEntry(
        id=next_id(_PLOTLINE_ID_PREFIX, (p.id for p in narrative.plotlines_list)),
        name=name,
        status="advancement",
        turning_point_count=0,
    )
    narrative.plotlines_list.append(entry)
    log(f"[AdventureCrafter] Created plotline '{name}' id={entry.id}")
    return entry


def _roll_plot_point(
    rng: random.Random, themes: list[str], alternation: ThemeAlternation, conclusion_counts_as_none: bool
) -> PlotPointHit:
    priority = lookup_theme_priority(rng.randint(1, crafter().adventure_crafter_dice.theme_die), alternation)
    theme_index = priority - 1
    if not 0 <= theme_index < len(themes):
        raise LookupError(f"theme priority {priority} outside themes list of length {len(themes)}")
    theme = themes[theme_index]
    plot_roll = _table_roll(rng)
    result = lookup_plot_point(theme, plot_roll)
    if result.special_range == "conclusion" and conclusion_counts_as_none:
        special_ranges = crafter().adventure_crafter.special_ranges
        none_roll = next(
            r
            for r in range(1, crafter().adventure_crafter_dice.table_die + 1)
            if _special_range_for(r, special_ranges) == "none"
        )
        return PlotPointHit(theme=theme, name=lookup_plot_point(theme, none_roll).name, special_range="none")
    return PlotPointHit(theme=theme, name=result.name, special_range=result.special_range)


def roll_turning_point(
    rng: random.Random,
    themes: list[str],
    narrative: NarrativeState,
) -> TurningPoint:
    cfg = crafter().adventure_crafter
    if len(themes) != cfg.theme_slots:
        raise ValueError(f"themes length {len(themes)} != theme_slots {cfg.theme_slots}")

    plotline_roll = _table_roll(rng)
    plotline_template = lookup_plotlines_template(plotline_roll)
    existing_plotline = _select_active_plotline(narrative)

    if plotline_template == "new_plotline" or existing_plotline is None:
        plotline = _create_plotline(
            narrative,
            name=crafter().adventure_crafter.plotline_name_template.format(n=len(narrative.plotlines_list) + 1),
        )
        plotline_was_new = True
    else:
        plotline = existing_plotline
        plotline_was_new = False

    rules = load_ac_data()["turning_point_rules"]
    slots = rules["plot_points_per_turning_point"]["max"]
    none_limit = slots - rules["plot_points_per_turning_point"]["min"]
    conclusion_counts_as_none = plotline_was_new or plotline.status == "conclusion"

    alternation = ThemeAlternation(next_is_4=True)
    hits: list[PlotPointHit] = []
    none_count = 0
    while len(hits) < slots:
        hit = _roll_plot_point(rng, themes, alternation, conclusion_counts_as_none)
        if hit.special_range == "none":
            if none_count == none_limit:
                continue
            none_count += 1
        hits.append(hit)
    flips_to_conclusion = any(h.special_range == "conclusion" for h in hits)

    plotline.turning_point_count += 1
    if flips_to_conclusion and plotline.status == "advancement":
        plotline.status = "conclusion"
        log(f"[AdventureCrafter] Plotline '{plotline.name}' flipped to conclusion")

    return TurningPoint(
        plot_points=hits,
        plotline=plotline.name,
        opens_plotline=plotline_was_new,
        concludes_plotline=flips_to_conclusion,
    )
