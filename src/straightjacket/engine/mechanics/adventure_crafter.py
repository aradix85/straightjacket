"""Adventure Crafter primitives: themes, plot points, meta-plot dispatch.

Adventure Crafter (Pigeon, Word Mill Games) provides plot-level structure
that complements Mythic GME 2e's scene-level chaos. AC operates over a small
set of primitives:

- Themes (Action, Tension, Mystery, Social, Personal): five canonical
  categories assigned to priority slots at adventure start. The active
  theme set steers plot-point selection toward setting-appropriate beats.
- Plot points (186 entries): themed d100 ranges per theme. Lookup is
  (theme, roll) -> entry; an entry's range may cover only a subset of
  themes, so a flat d100 -> entry table does not exist in the data.
- Special d100 ranges on plot-point lookup: Conclusion (1-8) closes the
  plotline, None (9-24) skips this turn, Meta (96-100) routes to the
  meta-handler dispatch in this module.
- Meta plot points: seven types (Character Exits, Character Returns,
  Character Steps Up/Down, Character Downgrade/Upgrade, Plotline Combo)
  with d100 range-based dispatch.

Step 5 lands the data-loading and lookup primitives. The seven meta
handlers are stubbed (NotImplementedError with handler name): the
dispatch shape is testable now, the bodies are filled in step 6 once
characters/plotlines lists exist for handlers to mutate.

Data: data/adventure_crafter.json → random_themes, plot_points,
meta_plot_points (and step-6 tables: plot_point_theme_priority,
character_special_trait, character_identity, character_descriptors,
characters_list_template, plotlines_list_template, turning_point_rules).

Config: engine/adventure_crafter.yaml → themes, theme_slots,
theme_die_table, special_ranges. Loaded as AdventureCrafterConfig.
"""

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
    """Load and cache data/adventure_crafter.json.

    On first call, validates the JSON's random_themes block matches the
    theme_die_table in engine/adventure_crafter.yaml exactly. A mismatch
    raises ValueError at load time so the engine never silently diverges
    from the AC data file.
    """
    global _ac_data
    if _ac_data is None:
        with open(_AC_DATA_PATH, encoding="utf-8") as f:
            _ac_data = json.load(f)
        log(f"[AdventureCrafter] Loaded {_AC_DATA_PATH}")
        _validate_random_themes(_ac_data)
    return _ac_data


def _validate_random_themes(data: dict[str, Any]) -> None:
    """Cross-check yaml theme_die_table against JSON random_themes.

    JSON random_themes is a list of {min, max, theme} ranges over a d10.
    The yaml theme_die_table must produce exactly the same d10 -> theme
    mapping. Mismatch raises ValueError naming the first offending face.
    """
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
    # Also verify every theme name in yaml.themes appears as a value.
    yaml_theme_set = set(cfg.themes)
    json_theme_set = set(json_table.values())
    if yaml_theme_set != json_theme_set:
        raise ValueError(
            f"adventure_crafter.yaml themes {sorted(yaml_theme_set)} does not match "
            f"random_themes theme set {sorted(json_theme_set)}"
        )


@dataclass(frozen=True)
class PlotPointResult:
    """Result of a plot-point lookup.

    name is the entry's plot-point name (e.g. "Conclusion", "Persuasion",
    "Meta"). special_range names the special d100 band the rolled value
    fell in: "conclusion", "none", "meta", or None for a normal beat.
    """

    name: str
    special_range: str | None


def assign_themes(rng: random.Random) -> list[str]:
    """Roll one theme per priority slot via the d10 theme_die_table.

    Returns a list of length theme_slots in priority order (slot 1 first).
    The same theme can appear in multiple slots — AC allows reinforcement.
    Pass an rng for deterministic ordering in tests.
    """
    cfg = eng().adventure_crafter
    return [cfg.theme_die_table[rng.randint(1, 10)] for _ in range(cfg.theme_slots)]


def lookup_plot_point(theme: str, roll: int) -> PlotPointResult:
    """Look up the plot-point entry covering this d100 roll on this theme.

    The plot_points list in data/adventure_crafter.json is sparse: most
    entries declare ranges on only a subset of themes. The lookup walks
    the list and returns the first entry whose theme range contains roll.

    The special-range flag is computed from the roll alone (1-8, 9-24,
    96-100 are theme-independent in the data). Callers route on the flag:
    "conclusion" closes the plotline, "none" skips, "meta" routes to
    dispatch_meta. None means a normal plot beat.

    Raises:
        KeyError: theme is not one of engine.adventure_crafter.themes.
        ValueError: roll is outside 1-100.
        LookupError: no plot-point entry covers this (theme, roll). The
            shipped data covers the full d100 for every theme, so this
            indicates corrupt data, not a normal flow path.
    """
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
    """Return the special-range name for this roll, or None for a normal beat."""
    if ranges.conclusion_min <= roll <= ranges.conclusion_max:
        return "conclusion"
    if ranges.none_min <= roll <= ranges.none_max:
        return "none"
    if ranges.meta_min <= roll <= ranges.meta_max:
        return "meta"
    return None


def lookup_meta_plot_point(roll: int) -> str:
    """Look up the meta-plot-point name covering this d100 roll.

    The meta_plot_points data is a list of {name, min, max} d100 ranges
    covering 1-100 fully. Used after a Meta result on the main plot-point
    table (96-100 special range): caller rolls a fresh d100 and routes
    here to learn which of the seven meta types fires.

    Raises:
        ValueError: roll is outside 1-100.
        LookupError: no meta entry covers this roll (data corruption).
    """
    if not 1 <= roll <= 100:
        raise ValueError(f"meta-plot-point roll {roll} outside 1..100")
    data = _load_ac_data()
    for entry in data["meta_plot_points"]:
        if entry["min"] <= roll <= entry["max"]:
            return entry["name"]
    raise LookupError(
        f"no meta_plot_points entry covers roll={roll}; data/adventure_crafter.json meta_plot_points may be incomplete"
    )


# Meta-plot-point handlers. Step 5 ships the dispatch shape; bodies land
# in step 6 once the characters list and plotlines list exist for the
# handlers to mutate. Each handler receives the full meta context dict
# the caller has assembled (game-state pointer, theme set, current
# plotline, etc.) — concrete signature is locked in step 6 because the
# AC integration with characters/plotlines lists determines the inputs.

MetaHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _meta_character_exits(_: dict[str, Any]) -> dict[str, Any]:
    """character_exits: remove a character from the active list. Step 6 wires."""
    raise NotImplementedError("character_exits not yet implemented — wired in step 6")


def _meta_character_returns(_: dict[str, Any]) -> dict[str, Any]:
    """character_returns: return a previously-exited character. Step 6 wires."""
    raise NotImplementedError("character_returns not yet implemented — wired in step 6")


def _meta_character_steps_up(_: dict[str, Any]) -> dict[str, Any]:
    """character_steps_up: promote a character's prominence. Step 6 wires."""
    raise NotImplementedError("character_steps_up not yet implemented — wired in step 6")


def _meta_character_steps_down(_: dict[str, Any]) -> dict[str, Any]:
    """character_steps_down: demote a character's prominence. Step 6 wires."""
    raise NotImplementedError("character_steps_down not yet implemented — wired in step 6")


def _meta_character_downgrade(_: dict[str, Any]) -> dict[str, Any]:
    """character_downgrade: weaken a character's standing. Step 6 wires."""
    raise NotImplementedError("character_downgrade not yet implemented — wired in step 6")


def _meta_character_upgrade(_: dict[str, Any]) -> dict[str, Any]:
    """character_upgrade: strengthen a character's standing. Step 6 wires."""
    raise NotImplementedError("character_upgrade not yet implemented — wired in step 6")


def _meta_plotline_combo(_: dict[str, Any]) -> dict[str, Any]:
    """plotline_combo: merge two plotlines into one. Step 6 wires."""
    raise NotImplementedError("plotline_combo not yet implemented — wired in step 6")


# Maps the JSON meta_plot_points "name" fields onto the seven handlers.
# Keys are taken verbatim from data/adventure_crafter.json so the
# dispatch layer is grounded in the data, not in renamed mirrors.
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
    """Resolve a Meta plot-point hit by rolling for type and routing to its handler.

    Caller path: lookup_plot_point returned special_range == "meta", caller
    rolls a fresh d100 and passes it here. This rolls the meta type via
    lookup_meta_plot_point and dispatches to the named handler.

    Until step 6 lands the handlers, every dispatch raises NotImplementedError
    from the handler. Tests verify the dispatch table is complete and that
    every meta name in JSON resolves to a handler in this module.

    Raises:
        KeyError: the meta name returned by lookup_meta_plot_point is not
            registered in _META_HANDLERS. This is a data/code mismatch and
            should fail loudly, not silently fall through.
    """
    meta_name = lookup_meta_plot_point(roll)
    if meta_name not in _META_HANDLERS:
        raise KeyError(
            f"meta plot-point {meta_name!r} has no handler in _META_HANDLERS; "
            f"data/adventure_crafter.json meta_plot_points and "
            f"mechanics/adventure_crafter.py _META_HANDLERS have drifted"
        )
    return _META_HANDLERS[meta_name](context)


def get_meta_handler_names() -> tuple[str, ...]:
    """Names of registered meta handlers, for tests and introspection."""
    return tuple(_META_HANDLERS.keys())
