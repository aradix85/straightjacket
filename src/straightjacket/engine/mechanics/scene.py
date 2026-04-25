"""Mythic GME 2e scene structure: chaos check, altered scenes, interrupt scenes,
plus the keyed-scene priority branch that overrides chaos when the director has
pre-defined a beat for the current state.

Every turn starts with a scene test. If a keyed scene's trigger fires, the
keyed scene replaces the chaos-driven outcome for this turn and is consumed
from narrative.keyed_scenes. Otherwise the chaos check determines whether
the scene plays as expected, gets altered, or is replaced by an interrupt.

Priority: keyed > interrupt > altered > expected.

Data: data/mythic_gme_2e.json → scene_adjustment.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, RandomEvent
from ..serialization import SerializableMixin
from .fate import _load_mythic
from .keyed_scenes import evaluate_keyed_scenes
from .random_events import generate_random_event


@dataclass
class SceneSetup(SerializableMixin):
    """Result of the scene test at the start of each turn.

    scene_type: "keyed", "expected", "altered", or "interrupt". Required —
    every construction site has a known scene type, no domain-safe default.
    chaos_roll: the d10 roll used for the chaos check, or 0 when no roll
    happened (keyed scenes skip the chaos check; 0 is the no-roll sentinel,
    parallel to combat_position="").
    adjustments: scene-adjustment types for altered scenes.
    interrupt_event: the RandomEvent generated for interrupt scenes, or None.
    narrative_hint: the keyed scene's hint text when scene_type="keyed",
    empty string otherwise.
    """

    scene_type: str
    chaos_roll: int = 0
    adjustments: list[str] = field(default_factory=list)
    interrupt_event: RandomEvent | None = None
    narrative_hint: str = ""


def check_scene(game: GameState, roll: int | None = None) -> SceneSetup:
    """Run the scene test with keyed-priority override.

    Priority: keyed > interrupt > altered > expected.

    1. evaluate_keyed_scenes — first matching keyed scene fires; consumed
       from narrative.keyed_scenes; returned with scene_type="keyed".
    2. Otherwise the d10 vs chaos factor check:
       - Roll > CF → expected.
       - Roll ≤ CF and odd → altered.
       - Roll ≤ CF and even → interrupt.
       - Roll of 10 → always expected (CF max is 9).

    Args:
        game: current game state (reads chaos_factor, narrative.keyed_scenes)
        roll: override d10 roll (for testing), None = random
    """
    keyed = evaluate_keyed_scenes(game)
    if keyed is not None:
        # Consume on hit. Caller does not need to re-remove.
        game.narrative.keyed_scenes = [k for k in game.narrative.keyed_scenes if k.id != keyed.id]
        log(
            f"[Scene] Keyed ({keyed.id}, trigger={keyed.trigger_type}={keyed.trigger_value}, priority={keyed.priority})"
        )
        return SceneSetup(scene_type="keyed", narrative_hint=keyed.narrative_hint)

    cf = game.world.chaos_factor

    if roll is None:
        roll = random.randint(1, 10)

    # 10 always expected
    if roll == 10 or roll > cf:
        log(f"[Scene] Expected (roll={roll} > CF{cf})")
        return SceneSetup(scene_type="expected", chaos_roll=roll)

    # Roll ≤ CF
    if roll % 2 == 1:
        # Odd → altered
        adjustments = _roll_adjustments()
        adj_str = ", ".join(adjustments)
        log(f"[Scene] Altered (roll={roll} ≤ CF{cf}, odd): {adj_str}")
        return SceneSetup(scene_type="altered", chaos_roll=roll, adjustments=adjustments)
    else:
        # Even → interrupt
        event = generate_random_event(game, source="interrupt_scene")
        log(
            f"[Scene] Interrupt (roll={roll} ≤ CF{cf}, even): {event.focus} → {event.meaning_action} / {event.meaning_subject}"
        )
        return SceneSetup(scene_type="interrupt", chaos_roll=roll, interrupt_event=event)


def _roll_adjustments(roll: int | None = None) -> list[str]:
    """Roll on the Scene Adjustment Table (d10).

    Results 1-6 are single adjustments. Results 7-10 mean "make 2 adjustments"
    — roll twice more, rerolling 7-10 on sub-rolls.
    """
    data = _load_mythic()
    table = data["scene_adjustment"]

    if roll is None:
        roll = random.randint(1, 10)

    result = _lookup_adjustment(table, roll)
    if result != "make_2_adjustments":
        return [result]

    # Two adjustments: roll twice, reroll 7-10
    adjustments = []
    for _ in range(2):
        sub = _roll_single_adjustment(table)
        adjustments.append(sub)
    return adjustments


def _lookup_adjustment(table: list[dict], roll: int) -> str:
    """Look up a single roll on the adjustment table.

    Raises KeyError if the roll falls outside any min/max range — a malformed
    table is a bug, not a condition to silently substitute around.
    """
    for entry in table:
        if entry["min"] <= roll <= entry["max"]:
            return entry["result"]
    raise KeyError(f"scene_adjustment table has no entry covering roll={roll}; table={table!r}")


def _roll_single_adjustment(table: list[dict]) -> str:
    """Roll a single adjustment, rerolling 7-10 (make_2_adjustments).

    Raises RuntimeError after 10 consecutive make_2_adjustments rolls — that
    means the table is broken (no single-adjustment entries reachable), which
    is a bug not a case to default-around.
    """
    for _ in range(10):  # safety limit
        roll = random.randint(1, 10)
        result = _lookup_adjustment(table, roll)
        if result != "make_2_adjustments":
            return result
    raise RuntimeError(
        "scene_adjustment table produced 10 consecutive make_2_adjustments rolls; "
        "single-adjustment entries are unreachable"
    )


def adjustment_descriptions(adjustments: list[str]) -> list[str]:
    """Map adjustment types to narrator-facing descriptions from yaml."""
    mapping = eng().scene_adjustments.mapping
    return [mapping[a] for a in adjustments]
