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
    scene_type: str
    chaos_roll: int = 0
    adjustments: list[str] = field(default_factory=list)
    interrupt_event: RandomEvent | None = None
    narrative_hint: str = ""


def check_scene(game: GameState, roll: int | None = None) -> SceneSetup:
    keyed = evaluate_keyed_scenes(game)
    if keyed is not None:
        game.narrative.keyed_scenes = [k for k in game.narrative.keyed_scenes if k.id != keyed.id]
        log(
            f"[Scene] Keyed ({keyed.id}, trigger={keyed.trigger_type}={keyed.trigger_value}, priority={keyed.priority})"
        )
        return SceneSetup(scene_type="keyed", narrative_hint=keyed.narrative_hint)

    cf = game.world.chaos_factor

    if roll is None:
        roll = random.randint(1, 10)

    if roll == 10 or roll > cf:
        log(f"[Scene] Expected (roll={roll} > CF{cf})")
        return SceneSetup(scene_type="expected", chaos_roll=roll)

    if roll % 2 == 1:
        adjustments = _roll_adjustments()
        adj_str = ", ".join(adjustments)
        log(f"[Scene] Altered (roll={roll} ≤ CF{cf}, odd): {adj_str}")
        return SceneSetup(scene_type="altered", chaos_roll=roll, adjustments=adjustments)
    else:
        event = generate_random_event(game, source="interrupt_scene")
        log(
            f"[Scene] Interrupt (roll={roll} ≤ CF{cf}, even): {event.focus} → {event.meaning_action} / {event.meaning_subject}"
        )
        return SceneSetup(scene_type="interrupt", chaos_roll=roll, interrupt_event=event)


def _roll_adjustments(roll: int | None = None) -> list[str]:
    data = _load_mythic()
    table = data["scene_adjustment"]

    if roll is None:
        roll = random.randint(1, 10)

    result = _lookup_adjustment(table, roll)
    if result != "make_2_adjustments":
        return [result]

    adjustments = []
    for _ in range(2):
        sub = _roll_single_adjustment(table)
        adjustments.append(sub)
    return adjustments


def _lookup_adjustment(table: list[dict], roll: int) -> str:
    for entry in table:
        if entry["min"] <= roll <= entry["max"]:
            return entry["result"]
    raise KeyError(f"scene_adjustment table has no entry covering roll={roll}; table={table!r}")


def _roll_single_adjustment(table: list[dict]) -> str:
    for _ in range(10):
        roll = random.randint(1, 10)
        result = _lookup_adjustment(table, roll)
        if result != "make_2_adjustments":
            return result
    raise RuntimeError(
        "scene_adjustment table produced 10 consecutive make_2_adjustments rolls; "
        "single-adjustment entries are unreachable"
    )


def adjustment_descriptions(adjustments: list[str]) -> list[str]:
    mapping = eng().scene_adjustments.mapping
    return [mapping[a] for a in adjustments]
