from __future__ import annotations

import random
from typing import Any

from ..logging_util import log
from ..models import GameState, SceneSetup
from .config import gm
from .keyed_scenes import evaluate_keyed_scenes
from .mythic_data import load_mythic
from .random_events import generate_random_event


def check_scene(game: GameState) -> SceneSetup:
    keyed = evaluate_keyed_scenes(game)
    if keyed is not None:
        game.narrative.keyed_scenes = [k for k in game.narrative.keyed_scenes if k.id != keyed.id]
        log(
            f"[Scene] Keyed ({keyed.id}, trigger={keyed.trigger_type}={keyed.trigger_value}, priority={keyed.priority})"
        )
        return SceneSetup(scene_type="keyed", narrative_hint=keyed.narrative_hint)

    cf = game.world.chaos_factor
    roll = random.randint(1, gm().mythic_dice.scene_test_die)

    if roll > cf:
        log(f"[Scene] Expected (roll={roll} > CF{cf})")
        return SceneSetup(scene_type="expected")

    if roll % 2 == 1:
        adjustments = _roll_adjustments()
        adj_str = ", ".join(adjustments)
        log(f"[Scene] Altered (roll={roll} ≤ CF{cf}, odd): {adj_str}")
        return SceneSetup(scene_type="altered", adjustments=adjustments)
    else:
        event = generate_random_event(game, source="interrupt_scene")
        log(
            f"[Scene] Interrupt (roll={roll} ≤ CF{cf}, even): {event.focus} → {event.meaning_action} / {event.meaning_subject}"
        )
        return SceneSetup(scene_type="interrupt", interrupt_event=event)


def _roll_adjustments() -> list[str]:
    table = load_mythic()["scene_adjustment"]
    result = _lookup_adjustment(table, random.randint(1, gm().mythic_dice.scene_adjustment_die))
    if result != "make_2_adjustments":
        return [result]

    adjustments = []
    for _ in range(2):
        sub = _roll_single_adjustment(table)
        adjustments.append(sub)
    return adjustments


def _lookup_adjustment(table: list[dict[str, Any]], roll: int) -> str:
    for entry in table:
        if entry["min"] <= roll <= entry["max"]:
            result: str = entry["result"]
            return result
    raise KeyError(f"scene_adjustment table has no entry covering roll={roll}; table={table!r}")


def _roll_single_adjustment(table: list[dict[str, Any]]) -> str:
    faces = [
        roll
        for roll in range(1, gm().mythic_dice.scene_adjustment_die + 1)
        if _lookup_adjustment(table, roll) != "make_2_adjustments"
    ]
    return _lookup_adjustment(table, random.choice(faces))


def adjustment_descriptions(adjustments: list[str]) -> list[str]:
    mapping = gm().scene_adjustments.mapping
    return [mapping[a] for a in adjustments]
