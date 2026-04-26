from __future__ import annotations

from collections.abc import Callable

from ..engine_loader import eng
from ..models import GameState, KeyedScene
from ..npc import find_npc, get_npc_bond


def _eval_clock_fills(game: GameState, value: str) -> bool:
    name, threshold_str = _split_two(value, "clock_fills")
    threshold = _parse_int(threshold_str, "clock_fills.segments_filled")
    return any(clock.name == name and clock.filled >= threshold for clock in game.world.clocks)


def _eval_threat_menace_phase(game: GameState, value: str) -> bool:
    name, threshold_str = _split_two(value, "threat_menace_phase")
    threshold = _parse_int(threshold_str, "threat_menace_phase.filled_boxes")
    return any(threat.name == name and threat.menace_filled_boxes >= threshold for threat in game.threats)


def _eval_bond_threshold(game: GameState, value: str) -> bool:
    npc_id, threshold_str = _split_two(value, "bond_threshold")
    threshold = _parse_int(threshold_str, "bond_threshold.filled_boxes")
    npc = find_npc(game, npc_id)
    if npc is None:
        raise KeyError(f"bond_threshold trigger references unknown npc_id {npc_id!r}")
    return get_npc_bond(game, npc.id) >= threshold


def _eval_chaos_extreme(game: GameState, value: str) -> bool:
    chaos = eng().chaos
    cf = game.world.chaos_factor
    if value == "min":
        return cf <= chaos.min
    if value == "max":
        return cf >= chaos.max
    raise ValueError(f"chaos_extreme trigger_value must be 'min' or 'max', got {value!r}")


def _eval_scene_count(game: GameState, value: str) -> bool:
    threshold = _parse_int(value, "scene_count")
    return game.narrative.scene_count >= threshold


def _split_two(value: str, trigger_name: str) -> tuple[str, str]:
    parts = value.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"{trigger_name} trigger_value must be '<name>:<n>', got {value!r}")
    return parts[0], parts[1]


def _parse_int(text: str, label: str) -> int:
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer, got {text!r}") from exc


_EVALUATORS: dict[str, Callable[[GameState, str], bool]] = {
    "clock_fills": _eval_clock_fills,
    "threat_menace_phase": _eval_threat_menace_phase,
    "bond_threshold": _eval_bond_threshold,
    "chaos_extreme": _eval_chaos_extreme,
    "scene_count": _eval_scene_count,
}


def evaluate_keyed_scenes(game: GameState) -> KeyedScene | None:
    if not game.narrative.keyed_scenes:
        return None
    ordered = sorted(game.narrative.keyed_scenes, key=lambda k: -k.priority)
    for scene in ordered:
        evaluator = _EVALUATORS[scene.trigger_type]
        if evaluator(game, scene.trigger_value):
            return scene
    return None
