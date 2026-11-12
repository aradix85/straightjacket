from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.ids import next_id
from straightjacket.engine.logging_util import log
from straightjacket.engine.models_story import PlotlineEntry
from straightjacket.engine.serialization import build_strict

if TYPE_CHECKING:
    import random
    from pathlib import Path

    from straightjacket.engine.crafters.config import PlotPointRanges
    from straightjacket.engine.models_story import NarrativeState

_AC_DATA_PATH = PROJECT_ROOT / "data" / "adventure_crafter.json"
_PLOTLINE_ID_PREFIX = "ac_plot_"


@dataclass(frozen=True)
class RollRange:
    min: int
    max: int


@dataclass(frozen=True)
class ThemeRow:
    min: int
    max: int
    theme: str


@dataclass(frozen=True)
class ThemePriorityRow:
    min: int
    max: int
    priority: int | str


@dataclass(frozen=True)
class MetaPlotPointRow:
    name: str
    min: int
    max: int


@dataclass(frozen=True)
class PlotPointRow:
    name: str
    themes: dict[str, RollRange]


@dataclass(frozen=True)
class SpecialTraitRow:
    min: int
    max: int
    trait: str


@dataclass(frozen=True)
class IdentityRow:
    min: int
    max: int
    identity: str


@dataclass(frozen=True)
class DescriptorRow:
    min: int
    max: int
    descriptor: str


@dataclass(frozen=True)
class TemplateRow:
    min: int
    max: int
    result: str


@dataclass(frozen=True)
class TurningPointRules:
    plot_points_per_turning_point: RollRange
    plotline_selection: str
    advancement_vs_conclusion: str
    rolling_method: str
    theme_4_5_alternation: str
    max_entries_per_list_item: int
    conclusion_plot_point_range: str
    none_plot_point_range: str


@dataclass(frozen=True)
class AdventureCrafterData:
    random_themes: list[ThemeRow]
    plot_point_theme_priority: list[ThemePriorityRow]
    theme_translation: dict[str, str]
    meta_plot_points: list[MetaPlotPointRow]
    plot_points: list[PlotPointRow]
    character_special_trait: list[SpecialTraitRow]
    character_identity: list[IdentityRow]
    character_descriptors: list[DescriptorRow]
    characters_list_template: list[TemplateRow]
    plotlines_list_template: list[TemplateRow]
    turning_point_rules: TurningPointRules


_cache: dict[Path, AdventureCrafterData] = {}


def load_ac_data() -> AdventureCrafterData:
    if _AC_DATA_PATH not in _cache:
        with _AC_DATA_PATH.open(encoding="utf-8") as f:
            data = build_strict(AdventureCrafterData, json.load(f), _AC_DATA_PATH.name)
        log(f"[AdventureCrafter] Loaded {_AC_DATA_PATH}")
        _validate_random_themes(data)
        _cache[_AC_DATA_PATH] = data
    return _cache[_AC_DATA_PATH]


def _validate_random_themes(data: AdventureCrafterData) -> None:
    cfg = crafter().adventure_crafter
    json_table: dict[int, str] = {}
    for entry in data.random_themes:
        for face in range(entry.min, entry.max + 1):
            json_table[face] = entry.theme
    if json_table != cfg.theme_die_table:
        diff = sorted(set(json_table.items()) ^ set(cfg.theme_die_table.items()))
        msg = (
            f"adventure_crafter.yaml theme_die_table does not match "
            f"data/adventure_crafter.json random_themes. Differing entries: {diff}"
        )
        raise ValueError(msg)

    yaml_theme_set = set(cfg.themes)
    json_theme_set = set(json_table.values())
    if yaml_theme_set != json_theme_set:
        msg = (
            f"adventure_crafter.yaml themes {sorted(yaml_theme_set)} does not match "
            f"random_themes theme set {sorted(json_theme_set)}"
        )
        raise ValueError(msg)


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
    for entry in load_ac_data().plot_points:
        if theme in entry.themes and entry.themes[theme].min <= roll <= entry.themes[theme].max:
            return PlotPointResult(name=entry.name, special_range=_special_range_for(roll, cfg.special_ranges))
    msg = (
        f"no plot_points entry covers theme={theme!r} roll={roll}; "
        f"data/adventure_crafter.json plot_points may be incomplete"
    )
    raise LookupError(msg)


def _special_range_for(roll: int, ranges: PlotPointRanges) -> str | None:
    if ranges.conclusion_min <= roll <= ranges.conclusion_max:
        return "conclusion"
    if ranges.none_min <= roll <= ranges.none_max:
        return "none"
    if ranges.meta_min <= roll <= ranges.meta_max:
        return "meta"
    return None


def lookup_meta_plot_point(roll: int) -> str:
    for entry in load_ac_data().meta_plot_points:
        if entry.min <= roll <= entry.max:
            return entry.name
    msg = (
        f"no meta_plot_points entry covers roll={roll}; data/adventure_crafter.json meta_plot_points may be incomplete"
    )
    raise LookupError(msg)


def lookup_theme_priority(roll: int, alternation: ThemeAlternation) -> int:
    for entry in load_ac_data().plot_point_theme_priority:
        if entry.min <= roll <= entry.max:
            priority = str(entry.priority)
            if "_or_" in priority:
                first, second = (int(p) for p in priority.split("_or_"))
                resolved = first if alternation.next_is_4 else second
                alternation.next_is_4 = not alternation.next_is_4
                return resolved
            return int(priority)
    msg = f"no plot_point_theme_priority entry covers roll={roll}"
    raise LookupError(msg)


def _lookup_template_result(roll: int, template: list[TemplateRow], template_key: str) -> str:
    for entry in template:
        if entry.min <= roll <= entry.max:
            return entry.result
    msg = f"no {template_key} entry covers roll={roll}"
    raise LookupError(msg)


def lookup_characters_template(roll: int) -> str:
    return _lookup_template_result(roll, load_ac_data().characters_list_template, "characters_list_template")


def lookup_plotlines_template(roll: int) -> str:
    return _lookup_template_result(roll, load_ac_data().plotlines_list_template, "plotlines_list_template")


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
    rng: random.Random, themes: list[str], alternation: ThemeAlternation, *, conclusion_counts_as_none: bool
) -> PlotPointHit:
    priority = lookup_theme_priority(rng.randint(1, crafter().adventure_crafter_dice.theme_die), alternation)
    theme_index = priority - 1
    if not 0 <= theme_index < len(themes):
        msg = f"theme priority {priority} outside themes list of length {len(themes)}"
        raise LookupError(msg)
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


def _roll_plot_points(rng: random.Random, themes: list[str], *, conclusion_counts_as_none: bool) -> list[PlotPointHit]:
    per_turning_point = load_ac_data().turning_point_rules.plot_points_per_turning_point
    slots = per_turning_point.max
    none_limit = slots - per_turning_point.min
    alternation = ThemeAlternation(next_is_4=True)
    hits: list[PlotPointHit] = []
    none_count = 0
    while len(hits) < slots:
        hit = _roll_plot_point(rng, themes, alternation, conclusion_counts_as_none=conclusion_counts_as_none)
        if hit.special_range == "none":
            if none_count == none_limit:
                continue
            none_count += 1
        hits.append(hit)
    return hits


def roll_turning_point(
    rng: random.Random,
    themes: list[str],
    narrative: NarrativeState,
) -> TurningPoint:
    cfg = crafter().adventure_crafter
    if len(themes) != cfg.theme_slots:
        msg = f"themes length {len(themes)} != theme_slots {cfg.theme_slots}"
        raise ValueError(msg)

    plotline_template = lookup_plotlines_template(_table_roll(rng))
    existing_plotline = _select_active_plotline(narrative)
    if plotline_template == "new_plotline" or existing_plotline is None:
        plotline = _create_plotline(
            narrative,
            name=cfg.plotline_name_template.format(n=len(narrative.plotlines_list) + 1),
        )
        plotline_was_new = True
    else:
        plotline = existing_plotline
        plotline_was_new = False

    hits = _roll_plot_points(rng, themes, conclusion_counts_as_none=plotline_was_new or plotline.status == "conclusion")
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
