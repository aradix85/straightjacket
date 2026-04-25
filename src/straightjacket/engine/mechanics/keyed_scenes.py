"""Keyed-scene evaluator.

A keyed scene is a director-pre-defined narrative beat that overrides the
chaos check at scene start. evaluate_keyed_scenes runs at the top of
check_scene; on a hit, the matched scene replaces the normal scene-test
outcome for that turn and is removed from narrative.keyed_scenes (one-shot).

Spawning is out of scope for step 4. The Adventure Crafter (step 7) is the
keyed-scene spawner — AC turning points and plot beats that map onto an
engine trigger get written into narrative.keyed_scenes by AC. Until then
the list stays empty in normal play, the keyed-priority branch in
check_scene is dormant, and tests seed the list directly.

Trigger types are registered in engine/keyed_scenes.yaml. Each registered
type has a matching evaluator function in this module's _EVALUATORS map;
trigger_type validation in KeyedScene.__post_init__ catches unknown names
at construction.
"""

from __future__ import annotations

from collections.abc import Callable

from ..engine_loader import eng
from ..models import GameState, KeyedScene
from ..npc import find_npc, get_npc_bond


def _eval_clock_fills(game: GameState, value: str) -> bool:
    """Trigger when a named clock has at least N filled segments.

    trigger_value: <clock_name>:<segments_filled>
    """
    name, threshold_str = _split_two(value, "clock_fills")
    threshold = _parse_int(threshold_str, "clock_fills.segments_filled")
    return any(clock.name == name and clock.filled >= threshold for clock in game.world.clocks)


def _eval_threat_menace_phase(game: GameState, value: str) -> bool:
    """Trigger when a named threat's menace track has at least N filled boxes.

    trigger_value: <threat_name>:<filled_boxes>
    """
    name, threshold_str = _split_two(value, "threat_menace_phase")
    threshold = _parse_int(threshold_str, "threat_menace_phase.filled_boxes")
    return any(threat.name == name and threat.menace_filled_boxes >= threshold for threat in game.threats)


def _eval_bond_threshold(game: GameState, value: str) -> bool:
    """Trigger when an NPC's connection track reaches at least N filled boxes.

    trigger_value: <npc_id>:<filled_boxes>
    Unknown npc_id raises — a spawner that referenced a missing NPC has a bug;
    silent-false would hide it.
    """
    npc_id, threshold_str = _split_two(value, "bond_threshold")
    threshold = _parse_int(threshold_str, "bond_threshold.filled_boxes")
    npc = find_npc(game, npc_id)
    if npc is None:
        raise KeyError(f"bond_threshold trigger references unknown npc_id {npc_id!r}")
    return get_npc_bond(game, npc.id) >= threshold


def _eval_chaos_extreme(game: GameState, value: str) -> bool:
    """Trigger when chaos_factor is at its configured min or max.

    trigger_value: "min" | "max"
    """
    chaos = eng().chaos
    cf = game.world.chaos_factor
    if value == "min":
        return cf <= chaos.min
    if value == "max":
        return cf >= chaos.max
    raise ValueError(f"chaos_extreme trigger_value must be 'min' or 'max', got {value!r}")


def _eval_scene_count(game: GameState, value: str) -> bool:
    """Trigger when narrative.scene_count has reached at least n.

    trigger_value: <n>
    """
    threshold = _parse_int(value, "scene_count")
    return game.narrative.scene_count >= threshold


def _split_two(value: str, trigger_name: str) -> tuple[str, str]:
    """Split a colon-delimited trigger_value into exactly two non-empty parts."""
    parts = value.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"{trigger_name} trigger_value must be '<name>:<n>', got {value!r}")
    return parts[0], parts[1]


def _parse_int(text: str, label: str) -> int:
    """Parse an integer trigger component, raising with a labelled message on miss."""
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer, got {text!r}") from exc


# Dispatch table: trigger_type → evaluator. Adding a trigger means adding an
# entry here AND a matching trigger registration in engine/keyed_scenes.yaml.
# A trigger that exists in yaml without an evaluator here raises KeyError
# during evaluation; the inverse (evaluator without yaml registration)
# never gets called because KeyedScene.__post_init__ rejects unknown types.
_EVALUATORS: dict[str, Callable[[GameState, str], bool]] = {
    "clock_fills": _eval_clock_fills,
    "threat_menace_phase": _eval_threat_menace_phase,
    "bond_threshold": _eval_bond_threshold,
    "chaos_extreme": _eval_chaos_extreme,
    "scene_count": _eval_scene_count,
}


def evaluate_keyed_scenes(game: GameState) -> KeyedScene | None:
    """Return the highest-priority keyed scene whose trigger fires, or None.

    Iterates narrative.keyed_scenes sorted by priority descending; returns
    the first match. Stable-sorted on priority, so ties resolve in insertion
    order — earlier-spawned scenes win ties.

    The matched scene is NOT removed here. The caller (check_scene) consumes
    it on hit so the evaluator stays a pure read.
    """
    if not game.narrative.keyed_scenes:
        return None
    ordered = sorted(game.narrative.keyed_scenes, key=lambda k: -k.priority)
    for scene in ordered:
        evaluator = _EVALUATORS[scene.trigger_type]
        if evaluator(game, scene.trigger_value):
            return scene
    return None
