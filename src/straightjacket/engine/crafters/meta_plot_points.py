from __future__ import annotations

import random
from collections.abc import Callable

from ..ids import next_id
from ..logging_util import log
from ..models_story import CharacterListEntry, NarrativeState
from .adventure_crafter import lookup_meta_plot_point
from .config import crafter

_CHARACTER_ID_PREFIX = "ac_char_"


def _ac_active_characters(narrative: NarrativeState) -> list[CharacterListEntry]:
    present = crafter().adventure_crafter.present_character_statuses
    return [c for c in narrative.characters_list if c.ac_status in present]


def _create_character(narrative: NarrativeState, name: str) -> CharacterListEntry:
    entry = CharacterListEntry(
        id=next_id(_CHARACTER_ID_PREFIX, (c.id for c in narrative.characters_list)),
        name=name,
        entry_type="ac",
        weight=1,
        active=True,
        ac_status="present",
    )
    narrative.characters_list.append(entry)
    log(f"[AdventureCrafter] Created character '{name}' id={entry.id}")
    return entry


MetaHandler = Callable[[NarrativeState, str | None], None]


def _apply_weight_delta(target: CharacterListEntry, delta: int) -> None:
    floor = crafter().adventure_crafter.meta_handlers.weight_floor
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
        new_char = _create_character(
            narrative,
            name=crafter().adventure_crafter.returning_character_name_template.format(
                n=len(narrative.characters_list) + 1
            ),
        )
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
    _apply_weight_delta(target, crafter().adventure_crafter.meta_handlers.weight_delta_step_up)
    log(f"[AdventureCrafter] character_steps_up: '{target.name}' weight → {target.weight}")


def _meta_character_steps_down(narrative: NarrativeState, _active_plotline_id: str | None) -> None:
    rng = random.Random()
    active = _ac_active_characters(narrative)
    if not active:
        log("[AdventureCrafter] character_steps_down: no active character")
        return
    target = rng.choice(active)
    _apply_weight_delta(target, crafter().adventure_crafter.meta_handlers.weight_delta_step_down)
    log(f"[AdventureCrafter] character_steps_down: '{target.name}' weight → {target.weight}")


def _meta_character_downgrade(narrative: NarrativeState, _active_plotline_id: str | None) -> None:
    rng = random.Random()
    active = _ac_active_characters(narrative)
    if not active:
        log("[AdventureCrafter] character_downgrade: no active character")
        return
    target = rng.choice(active)
    target.ac_status = "downgraded"
    _apply_weight_delta(target, crafter().adventure_crafter.meta_handlers.weight_delta_downgrade)
    log(f"[AdventureCrafter] character_downgrade: '{target.name}' downgraded weight → {target.weight}")


def _meta_character_upgrade(narrative: NarrativeState, _active_plotline_id: str | None) -> None:
    rng = random.Random()
    active = _ac_active_characters(narrative)
    if not active:
        log("[AdventureCrafter] character_upgrade: no active character")
        return
    target = rng.choice(active)
    target.ac_status = "upgraded"
    _apply_weight_delta(target, crafter().adventure_crafter.meta_handlers.weight_delta_upgrade)
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
            f"crafters/meta_plot_points.py _META_HANDLERS have drifted"
        )
    _META_HANDLERS[meta_name](narrative, active_plotline_id)
