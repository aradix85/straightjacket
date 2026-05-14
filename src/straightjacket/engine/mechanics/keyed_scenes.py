from __future__ import annotations

from collections.abc import Callable

from ..engine_loader import eng
from ..logging_util import log
from ..models import ClockData, GameState, KeyedScene, NarrativeState
from ..models_npc import NpcData
from ..npc import find_npc, get_npc_bond
from .spawn_sources import CLOCK_KEYED_SOURCE_PREFIX


def _eval_clock_fills(game: GameState, value: str) -> bool:
    pool, threshold = _parse_pattern_value(value, "clock_fills")
    return len(_clock_pool_candidates(game, pool, threshold, exclude_ids=set())) > 0


def _eval_threat_menace_phase(game: GameState, value: str) -> bool:
    pool, threshold = _parse_pattern_value(value, "threat_menace_phase")
    return len(_threat_pool_candidates(game, pool, threshold, exclude_ids=set())) > 0


def _eval_bond_threshold(game: GameState, value: str) -> bool:
    pool, threshold = _parse_pattern_value(value, "bond_threshold")
    return len(_bond_pool_candidates(game, pool, threshold, exclude_ids=set())) > 0


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


def _bond_pool_candidates(
    game: GameState,
    pool: str,
    threshold: int,
    exclude_ids: set[str],
) -> list[str]:
    if pool != "any" and not _is_disposition_pattern(pool):
        npc = find_npc(game, pool)
        if npc is None:
            raise KeyError(f"bond_threshold trigger references unknown npc_id {pool!r}")
        if npc.id in exclude_ids:
            return []
        return [npc.id] if get_npc_bond(game, npc.id) >= threshold else []

    matches: list[str] = []
    for npc in game.npcs:
        if npc.id in exclude_ids:
            continue
        if not _npc_matches_pool(npc, pool):
            continue
        if get_npc_bond(game, npc.id) >= threshold:
            matches.append(npc.id)
    return matches


def _threat_pool_candidates(
    game: GameState,
    pool: str,
    threshold: int,
    exclude_ids: set[str],
) -> list[str]:
    if pool != "any":
        threat = next((t for t in game.threats if t.name == pool), None)
        if threat is None:
            return []
        if threat.id in exclude_ids:
            return []
        return [threat.id] if threat.menace_filled_boxes >= threshold else []

    matches: list[str] = []
    for threat in game.threats:
        if threat.id in exclude_ids:
            continue
        if threat.menace_filled_boxes >= threshold:
            matches.append(threat.id)
    return matches


def _clock_pool_candidates(
    game: GameState,
    pool: str,
    threshold: int,
    exclude_ids: set[str],
) -> list[str]:
    if pool != "any":
        clock = next((c for c in game.world.clocks if c.name == pool), None)
        if clock is None:
            return []
        clock_key = _clock_key(clock.name)
        if clock_key in exclude_ids:
            return []
        return [clock_key] if clock.filled >= threshold else []

    matches: list[str] = []
    for clock in game.world.clocks:
        clock_key = _clock_key(clock.name)
        if clock_key in exclude_ids:
            continue
        if clock.filled >= threshold:
            matches.append(clock_key)
    return matches


def _clock_key(clock_name: str) -> str:
    return f"clock:{clock_name}"


def _npc_matches_pool(npc: NpcData, pool: str) -> bool:
    if pool == "any":
        return True
    if _is_disposition_pattern(pool):
        wanted = pool[len("disposition_") :]
        return npc.disposition == wanted
    return False


def _is_disposition_pattern(pool: str) -> bool:
    return pool.startswith("disposition_")


def _resolve_pattern_entity(
    game: GameState,
    trigger_type: str,
    value: str,
    already_bound: set[str],
) -> str | None:
    pool, threshold = _parse_pattern_value(value, trigger_type)
    grammar = eng().keyed_scenes.pattern_grammars[trigger_type]
    strategy = grammar.matcher_strategy

    if trigger_type == "bond_threshold":
        candidates = _bond_pool_candidates(game, pool, threshold, exclude_ids=already_bound)
        if not candidates:
            return None
        if strategy == "highest_bond":
            return max(candidates, key=lambda nid: get_npc_bond(game, nid))
        raise ValueError(f"unknown bond_threshold matcher_strategy {strategy!r}")

    if trigger_type == "threat_menace_phase":
        candidates = _threat_pool_candidates(game, pool, threshold, exclude_ids=already_bound)
        if not candidates:
            return None
        if strategy == "highest_menace":
            id_to_threat = {t.id: t for t in game.threats}
            return max(candidates, key=lambda tid: id_to_threat[tid].menace_filled_boxes)
        raise ValueError(f"unknown threat_menace_phase matcher_strategy {strategy!r}")

    if trigger_type == "clock_fills":
        candidates = _clock_pool_candidates(game, pool, threshold, exclude_ids=already_bound)
        if not candidates:
            return None
        if strategy == "highest_filled":
            key_to_clock = {_clock_key(c.name): c for c in game.world.clocks}
            return max(candidates, key=lambda key: key_to_clock[key].filled)
        raise ValueError(f"unknown clock_fills matcher_strategy {strategy!r}")

    raise ValueError(f"trigger_type {trigger_type!r} has no resolver")


def _parse_pattern_value(value: str, trigger_name: str) -> tuple[str, int]:
    pool, threshold_str = _split_two(value, trigger_name)
    threshold = _parse_int(threshold_str, f"{trigger_name}.threshold")
    return pool, threshold


def _split_two(value: str, trigger_name: str) -> tuple[str, str]:
    parts = value.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"{trigger_name} trigger_value must be '<pool>:<n>', got {value!r}")
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
    already_bound: set[str] = {s.bound_entity_id for s in game.narrative.keyed_scenes if s.bound_entity_id is not None}
    ordered = sorted(game.narrative.keyed_scenes, key=lambda k: -k.priority)
    pattern_supporting = eng().keyed_scenes.pattern_grammars
    for scene in ordered:
        if scene.trigger_type in pattern_supporting and scene.bound_entity_id is not None:
            if _bound_entity_meets_threshold(game, scene.trigger_type, scene.trigger_value, scene.bound_entity_id):
                return scene
            continue
        evaluator = _EVALUATORS[scene.trigger_type]
        if not evaluator(game, scene.trigger_value):
            continue
        if scene.trigger_type in pattern_supporting:
            entity_id = _resolve_pattern_entity(game, scene.trigger_type, scene.trigger_value, already_bound)
            if entity_id is None:
                continue
            scene.bound_entity_id = entity_id
        return scene
    return None


def _bound_entity_meets_threshold(game: GameState, trigger_type: str, value: str, entity_id: str) -> bool:
    _pool, threshold = _parse_pattern_value(value, trigger_type)
    if trigger_type == "bond_threshold":
        npc = find_npc(game, entity_id)
        if npc is None:
            return False
        return get_npc_bond(game, npc.id) >= threshold
    if trigger_type == "threat_menace_phase":
        threat = next((t for t in game.threats if t.id == entity_id), None)
        if threat is None:
            return False
        return threat.menace_filled_boxes >= threshold
    if trigger_type == "clock_fills":
        for clock in game.world.clocks:
            if _clock_key(clock.name) == entity_id:
                return clock.filled >= threshold
        return False
    raise ValueError(f"trigger_type {trigger_type!r} not pattern-supporting")


def _clock_already_spawned(narrative: NarrativeState, clock_name: str, threshold: int) -> bool:
    target = f"{CLOCK_KEYED_SOURCE_PREFIX}{clock_name}:{threshold}"
    return any(ks.source == target for ks in narrative.keyed_scenes)


def _next_clock_keyed_scene_id(narrative: NarrativeState) -> str:
    n = 1
    while any(ks.id == f"ks_clock_{n}" for ks in narrative.keyed_scenes):
        n += 1
    return f"ks_clock_{n}"


def spawn_keyed_scenes_for_clock(narrative: NarrativeState, clock: ClockData) -> int:
    cks = eng().clock_keyed_scenes.by_clock_type
    if clock.clock_type not in cks:
        return 0
    entry = cks[clock.clock_type]

    spawned = 0
    for fraction in entry.fractions:
        threshold = max(1, int(round(clock.segments * fraction)))
        if _clock_already_spawned(narrative, clock.name, threshold):
            continue
        scene_id = _next_clock_keyed_scene_id(narrative)
        narrative_hint = entry.narrative_hint_template.format(clock_name=clock.name)
        scene = KeyedScene(
            id=scene_id,
            trigger_type="clock_fills",
            trigger_value=f"{clock.name}:{threshold}",
            priority=entry.priority,
            narrative_hint=narrative_hint,
            source=f"{CLOCK_KEYED_SOURCE_PREFIX}{clock.name}:{threshold}",
        )
        narrative.keyed_scenes.append(scene)
        spawned += 1
        log(
            f"[Clock] spawned keyed-scene '{scene_id}' for clock '{clock.name}' "
            f"(type={clock.clock_type}, fraction={fraction}, threshold={threshold}, priority={entry.priority})"
        )
    return spawned
