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


MetaHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _meta_character_exits(_: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("character_exits not yet implemented — wired in step 6")


def _meta_character_returns(_: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("character_returns not yet implemented — wired in step 6")


def _meta_character_steps_up(_: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("character_steps_up not yet implemented — wired in step 6")


def _meta_character_steps_down(_: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("character_steps_down not yet implemented — wired in step 6")


def _meta_character_downgrade(_: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("character_downgrade not yet implemented — wired in step 6")


def _meta_character_upgrade(_: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("character_upgrade not yet implemented — wired in step 6")


def _meta_plotline_combo(_: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("plotline_combo not yet implemented — wired in step 6")


_META_HANDLERS: dict[str, MetaHandler] = {
    "Character Exits The Adventure": _meta_character_exits,
    "Character Returns": _meta_character_returns,
    "Character Steps Up": _meta_character_steps_up,
    "Character Steps Down": _meta_character_steps_down,
    "Character Downgrade": _meta_character_downgrade,
    "Character Upgrade": _meta_character_upgrade,
    "Plotline Combo": _meta_plotline_combo,
}


def dispatch_meta(roll: int, context: dict[str, Any]) -> dict[str, Any]:
    meta_name = lookup_meta_plot_point(roll)
    if meta_name not in _META_HANDLERS:
        raise KeyError(
            f"meta plot-point {meta_name!r} has no handler in _META_HANDLERS; "
            f"data/adventure_crafter.json meta_plot_points and "
            f"mechanics/adventure_crafter.py _META_HANDLERS have drifted"
        )
    return _META_HANDLERS[meta_name](context)


def get_meta_handler_names() -> tuple[str, ...]:
    return tuple(_META_HANDLERS.keys())
