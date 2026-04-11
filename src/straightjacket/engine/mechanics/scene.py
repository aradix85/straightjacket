#!/usr/bin/env python3
"""Mythic GME 2e scene structure: chaos check, altered scenes, interrupt scenes.

Every turn starts with a scene test that determines whether the scene plays
as expected, gets altered, or is replaced by an interrupt. Replaces the
old check_chaos_interrupt system.

Data: data/mythic_gme_2e.json → scene_adjustment.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..logging_util import log
from ..models import GameState, RandomEvent
from ..serialization import SerializableMixin
from .fate import _load_mythic
from .random_events import generate_random_event

# Scene adjustment descriptions for narrator prompt injection.
_ADJUSTMENT_DESCRIPTIONS: dict[str, str] = {
    "remove_character": "The most logical NPC is absent from the scene",
    "add_character": "An unexpected character appears in the scene",
    "reduce_activity": "The expected activity is diminished or absent",
    "increase_activity": "The expected activity is more intense than anticipated",
    "remove_object": "Something expected is missing from the scene",
    "add_object": "Something unexpected is present in the scene",
}


@dataclass
class SceneSetup(SerializableMixin):
    """Result of the scene test at the start of each turn.

    scene_type: "expected", "altered", or "interrupt".
    chaos_roll: the d10 roll used for the chaos check.
    adjustments: list of adjustment types for altered scenes (e.g. ["add_character", "remove_object"]).
    interrupt_event: the RandomEvent generated for interrupt scenes, or None.
    """

    scene_type: str = "expected"
    chaos_roll: int = 0
    adjustments: list[str] = field(default_factory=list)
    interrupt_event: RandomEvent | None = None


def check_scene(game: GameState, roll: int | None = None) -> SceneSetup:
    """Run the Mythic 2e scene test.

    d10 vs chaos factor:
    - Roll > CF → expected (proceeds unchanged).
    - Roll ≤ CF and odd → altered scene.
    - Roll ≤ CF and even → interrupt scene.
    - Roll of 10 → always expected (CF max is 9).

    Args:
        game: current game state (reads chaos_factor)
        roll: override d10 roll (for testing), None = random
    """
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
    """Look up a single roll on the adjustment table."""
    for entry in table:
        if entry["min"] <= roll <= entry["max"]:
            return entry["result"]
    return "increase_activity"


def _roll_single_adjustment(table: list[dict]) -> str:
    """Roll a single adjustment, rerolling 7-10 (make_2_adjustments)."""
    for _ in range(10):  # safety limit
        roll = random.randint(1, 10)
        result = _lookup_adjustment(table, roll)
        if result != "make_2_adjustments":
            return result
    return "increase_activity"


def adjustment_descriptions(adjustments: list[str]) -> list[str]:
    """Map adjustment types to narrator-facing descriptions."""
    return [_ADJUSTMENT_DESCRIPTIONS.get(a, a) for a in adjustments]
