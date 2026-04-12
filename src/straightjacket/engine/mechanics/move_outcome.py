#!/usr/bin/env python3
"""Move outcome resolution: data-driven mechanical effects.

Replaces the category-based apply_consequences with move-specific outcomes.
Each move outcome is a list of effect strings parsed from engine.yaml.

Effect vocabulary:
    momentum +N / -N        Resource change (clamped to floor/ceiling)
    health +N / -N          Resource change
    spirit +N / -N          Resource change
    supply +N / -N          Resource change
    integrity +N / -N       Asset control change (future: step 10)
    mark_progress N         Mark N times on the active progress track
    pay_the_price           Generic miss consequence via pay_the_price table
    next_move_bonus +N      Temporary bonus on next move (decays after one turn)
    suffer_move -N          Trigger a generic suffer move at -N
    position in_control     Set combat position to in_control
    position bad_spot       Set combat position to bad_spot
    legacy_reward TRACK     Mark legacy track reward per completed track rank
    fill_clock N            Fill N segments on scene challenge clock
    narrative               No mechanical effect, pure narrative

Handler-based moves use engine.yaml params instead of effect lists:
    handler: suffer         Suffer pattern (endure_harm, endure_stress, withstand_damage, companion_takes_a_hit)
    handler: threshold      Threshold pattern (face_death, face_desolation)
    handler: recovery       Recovery with conditional impact clear (heal, hearten, resupply)
    handler: repair         Repair point system
    handler: sojourn        Chained recovery moves
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState


# ── Parsed effect ────────────────────────────────────────────


@dataclass
class MoveEffect:
    """Single parsed mechanical effect."""

    type: str = ""  # momentum, health, spirit, supply, integrity, mark_progress, etc.
    value: int = 0  # numeric value (positive or negative)
    target: str = ""  # for legacy_reward: track name; for position: in_control/bad_spot


_EFFECT_RE = re.compile(r"^(\w+)\s+([+-]?\d+)$")
_POSITION_RE = re.compile(r"^position\s+(\w+)$")
_LEGACY_RE = re.compile(r"^legacy_reward\s+(\w+)$")
_FILL_CLOCK_RE = re.compile(r"^fill_clock\s+(\d+)$")


def parse_effect(effect_str: str) -> MoveEffect:
    """Parse a single effect string from engine.yaml."""
    effect_str = effect_str.strip()

    # Simple resource/track changes: "momentum +1", "health -2", "mark_progress 2"
    m = _EFFECT_RE.match(effect_str)
    if m:
        return MoveEffect(type=m.group(1), value=int(m.group(2)))

    # Position: "position in_control"
    m = _POSITION_RE.match(effect_str)
    if m:
        return MoveEffect(type="position", target=m.group(1))

    # Legacy reward: "legacy_reward quests"
    m = _LEGACY_RE.match(effect_str)
    if m:
        return MoveEffect(type="legacy_reward", target=m.group(1))

    # Fill clock: "fill_clock 2"
    m = _FILL_CLOCK_RE.match(effect_str)
    if m:
        return MoveEffect(type="fill_clock", value=int(m.group(1)))

    # No-arg effects: "pay_the_price", "narrative"
    if effect_str in ("pay_the_price", "narrative", "suffer_move", "disposition_shift"):
        return MoveEffect(type=effect_str)

    # Suffer move with value: "suffer_move -1"
    if effect_str.startswith("suffer_move"):
        parts = effect_str.split()
        if len(parts) == 2:
            return MoveEffect(type="suffer_move", value=int(parts[1]))

    log(f"[MoveOutcome] Unknown effect: {effect_str!r}", level="warning")
    return MoveEffect(type="unknown", target=effect_str)


def parse_effects(effect_list: list[str]) -> list[MoveEffect]:
    """Parse a list of effect strings."""
    return [parse_effect(e) for e in effect_list]


# ── Effect application ───────────────────────────────────────


@dataclass
class OutcomeResult:
    """Result of applying a move outcome. Fed to consequence sentence generation and narrator prompt."""

    consequences: list[str] = field(default_factory=list)  # human-readable, e.g. "momentum +2"
    combat_position: str = ""  # "in_control" or "bad_spot" or "" (unchanged)
    pay_the_price: bool = False
    next_move_bonus: int = 0
    progress_marks: int = 0
    clock_fills: int = 0
    legacy_track: str = ""
    narrative_only: bool = False


def apply_effects(game: GameState, effects: list[MoveEffect], target_npc_id: str | None = None) -> OutcomeResult:
    """Apply a list of parsed effects to game state. Returns result summary."""
    from ..npc import find_npc

    result = OutcomeResult()
    _e = eng()
    res = game.resources
    target = find_npc(game, target_npc_id) if target_npc_id else None

    for effect in effects:
        if effect.type == "momentum":
            res.adjust_momentum(effect.value, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            result.consequences.append(f"momentum {'+' if effect.value > 0 else ''}{effect.value}")

        elif effect.type in ("health", "spirit", "supply"):
            if effect.value > 0:
                cap = getattr(_e.resources, f"{effect.type}_max")
                gained = res.heal(effect.type, effect.value, cap=cap)
                if gained:
                    result.consequences.append(f"{effect.type} +{gained}")
            else:
                lost = res.damage(effect.type, abs(effect.value))
                if lost:
                    result.consequences.append(f"{effect.type} -{lost}")

        elif effect.type == "integrity":
            # Future: asset condition tracks (step 10). Log and skip for now.
            result.consequences.append(f"integrity {'+' if effect.value > 0 else ''}{effect.value}")

        elif effect.type == "mark_progress":
            result.progress_marks += effect.value
            result.consequences.append(f"mark progress ×{effect.value}")

        elif effect.type == "pay_the_price":
            result.pay_the_price = True

        elif effect.type == "next_move_bonus":
            result.next_move_bonus = effect.value
            result.consequences.append(f"next move +{effect.value}")

        elif effect.type == "position":
            result.combat_position = effect.target

        elif effect.type == "suffer_move":
            _apply_generic_suffer(game, abs(effect.value), result)

        elif effect.type == "legacy_reward":
            result.legacy_track = effect.target
            result.consequences.append(f"legacy reward ({effect.target})")

        elif effect.type == "fill_clock":
            result.clock_fills += effect.value
            result.consequences.append(f"clock +{effect.value}")

        elif effect.type == "bond":
            if target:
                # Find connection track for this NPC
                conn_track = next(
                    (
                        t
                        for t in game.progress_tracks
                        if t.track_type == "connection" and t.id == f"connection_{target.id}" and t.status == "active"
                    ),
                    None,
                )
                if conn_track:
                    for _ in range(abs(effect.value)):
                        added = conn_track.mark_progress()
                        if added:
                            result.consequences.append(f"{target.name} bond progress +{added} ticks")
                else:
                    log(f"[MoveOutcome] bond effect but no connection track for {target.name}")

        elif effect.type == "disposition_shift":
            if target:
                shifts = _e.get_raw("disposition_shifts", {})
                old_disp = target.disposition
                target.disposition = shifts.get(target.disposition, target.disposition)
                if target.disposition != old_disp:
                    result.consequences.append(f"{target.name} disposition {old_disp}→{target.disposition}")

        elif effect.type == "narrative":
            result.narrative_only = True

        elif effect.type != "unknown":
            log(f"[MoveOutcome] Unhandled effect type: {effect.type}", level="warning")

    return result


def _apply_generic_suffer(game: GameState, amount: int, result: OutcomeResult) -> None:
    """Apply generic suffer move: pick the most appropriate track based on game state."""
    _e = eng()
    res = game.resources
    # Pick the track with the most room to lose
    tracks = [
        ("health", res.health),
        ("spirit", res.spirit),
        ("supply", res.supply),
    ]
    # Pick highest-value track (most room to absorb damage)
    tracks.sort(key=lambda t: t[1], reverse=True)
    track = tracks[0][0]
    lost = res.damage(track, amount)
    if lost:
        result.consequences.append(f"{track} -{lost}")


# ── Handler-based resolution ─────────────────────────────────
# These handle complex moves with conditional logic that doesn't
# fit in the simple effect list format.


def apply_suffer_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
    """Handle suffer moves: endure_harm, endure_stress, withstand_damage, companion_takes_a_hit.

    Shared pattern:
      strong_hit: choose recovery (+1 track) or momentum (+1). Engine picks track if no impact.
      weak_hit: may exchange momentum -1 for +1 track (if no blocking impact).
      miss: extra -1 track or momentum -2. If track=0: mark impact or roll table.

    Params from engine.yaml:
      track: health / spirit / integrity / companion_health
      recovery: amount to recover on strong/weak hit (default 1)
      miss_extra_track: extra track loss on miss (default -1)
      miss_extra_momentum: alternative momentum loss on miss (default -2)
      impact_pair: [impact_name, worse_impact_name] for miss at zero
      blocking_impact: impact that blocks track recovery on strong/weak hit
    """
    result = OutcomeResult()
    _e = eng()
    res = game.resources
    track = params.get("track", "health")
    recovery = params.get("recovery", 1)
    params.get("blocking_impact", "")
    miss_extra_track = params.get("miss_extra_track", -1)
    miss_extra_momentum = params.get("miss_extra_momentum", -2)

    # For now, impacts are not yet tracked (step 9). We always take the track recovery.
    has_blocking_impact = False  # TODO step 9: check game.impacts

    if roll_result == "STRONG_HIT":
        if track in ("health", "spirit", "supply") and not has_blocking_impact:
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, recovery, cap=cap)
            if gained:
                result.consequences.append(f"{track} +{gained}")
            else:
                # Track already at max, take momentum instead
                res.adjust_momentum(1, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append("momentum +1")
        else:
            # Blocking impact or non-standard track: take momentum
            res.adjust_momentum(1, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            result.consequences.append("momentum +1")

    elif roll_result == "WEAK_HIT":
        if track in ("health", "spirit", "supply") and not has_blocking_impact:
            # Exchange: momentum -1 for track +1
            res.adjust_momentum(-1, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, recovery, cap=cap)
            result.consequences.append("momentum -1")
            if gained:
                result.consequences.append(f"{track} +{gained}")

    else:  # MISS
        # Extra track damage or momentum loss — engine picks track damage
        if track in ("health", "spirit", "supply"):
            lost = res.damage(track, abs(miss_extra_track))
            if lost:
                result.consequences.append(f"{track} -{lost}")
            else:
                # Track already at 0, take momentum instead
                res.adjust_momentum(miss_extra_momentum, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(f"momentum {miss_extra_momentum}")
        else:
            res.adjust_momentum(miss_extra_momentum, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            result.consequences.append(f"momentum {miss_extra_momentum}")

        # Check if at zero — would mark impact (step 9) or roll table
        track_value = getattr(res, track, None) if track in ("health", "spirit", "supply") else None
        if track_value is not None and track_value <= 0:
            impact_pair = params.get("impact_pair", [])
            if impact_pair:
                result.consequences.append(f"must mark {impact_pair[0]} or {impact_pair[1]}")
                # TODO step 9: actually mark the impact

    return result


def apply_threshold_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
    """Handle threshold moves: face_death, face_desolation.

    strong_hit: survive, no mechanical effect.
    weak_hit: survive with cost (mark impact or swear a vow). Engine marks impact.
    miss: dead or lost. Game over.

    Params:
      impact: impact to mark on weak hit (doomed, tormented)
      game_over_text: narrative for miss
    """
    result = OutcomeResult()

    if roll_result == "STRONG_HIT":
        result.narrative_only = True

    elif roll_result == "WEAK_HIT":
        impact = params.get("impact", "")
        if impact:
            result.consequences.append(f"mark {impact}")
            # TODO step 9: game.impacts.add(impact)
        result.consequences.append("swear a deathbound vow")

    else:  # MISS
        game.game_over = True
        result.consequences.append(params.get("game_over_text", "you are lost"))

    return result


def apply_recovery_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
    """Handle recovery moves with conditional impact clearing: heal, hearten, resupply.

    strong_hit: if blocking impact, clear it and take reduced amount. Otherwise full amount.
    weak_hit: same as strong_hit but with additional cost (momentum or supply loss).
    miss: pay the price.

    Params:
      track: health / spirit / supply
      full_amount: recovery without impact (default 3 for heal, 2 for hearten/resupply)
      impact_amount: recovery when clearing impact (default 2 for heal, 1 for hearten/resupply)
      blocking_impact: impact name (wounded, shaken, unprepared)
      weak_hit_cost_type: momentum / supply
      weak_hit_cost: amount (default -2)
    """
    result = OutcomeResult()
    _e = eng()
    res = game.resources
    track = params.get("track", "health")
    full_amount = params.get("full_amount", 2)
    impact_amount = params.get("impact_amount", 1)
    blocking_impact = params.get("blocking_impact", "")
    weak_cost_type = params.get("weak_hit_cost_type", "momentum")
    weak_cost = params.get("weak_hit_cost", -2)

    # TODO step 9: check if blocking impact is active
    has_impact = False

    if roll_result in ("STRONG_HIT", "WEAK_HIT"):
        amount = impact_amount if has_impact else full_amount
        if has_impact:
            result.consequences.append(f"clear {blocking_impact}")
            # TODO step 9: game.impacts.remove(blocking_impact)

        if track in ("health", "spirit", "supply"):
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, amount, cap=cap)
            if gained:
                result.consequences.append(f"{track} +{gained}")

        if roll_result == "WEAK_HIT":
            if weak_cost_type == "momentum":
                res.adjust_momentum(weak_cost, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(f"momentum {weak_cost}")
            elif weak_cost_type == "supply":
                lost = res.damage("supply", abs(weak_cost))
                if lost:
                    result.consequences.append(f"supply -{lost}")

    else:  # MISS
        result.pay_the_price = True

    return result


# ── Main resolver ────────────────────────────────────────────


def resolve_move_outcome(
    game: GameState, move_key: str, roll_result: str, target_npc_id: str | None = None
) -> OutcomeResult:
    """Resolve a move outcome from engine.yaml configuration.

    Args:
        game: current game state (mutated in place).
        move_key: full move key, e.g. "adventure/face_danger".
        roll_result: "STRONG_HIT", "WEAK_HIT", or "MISS".
        target_npc_id: NPC id for bond/disposition effects.

    Returns:
        OutcomeResult with consequences, position changes, etc.
    """
    _e = eng()
    outcomes_cfg = _e.get_raw("move_outcomes", {})

    result_key = roll_result.lower()

    move_cfg = outcomes_cfg.get(move_key)
    if move_cfg is None:
        raise ValueError(f"No outcome config for {move_key}. Add it to engine.yaml move_outcomes.")

    # Handler-based moves
    handler = move_cfg.get("handler")
    if handler:
        params_raw = move_cfg.get("params")
        params_dict = dict(params_raw) if params_raw is not None else {}
        return _dispatch_handler(game, handler, roll_result, params_dict)

    # Effect-list based moves
    effects_raw = move_cfg.get(result_key)
    if effects_raw is None:
        raise ValueError(f"No effects for {move_key}/{result_key}. Add it to engine.yaml move_outcomes.")

    # Normalize to list of strings
    if isinstance(effects_raw, str):
        effects_raw = [effects_raw]
    elif not isinstance(effects_raw, list):
        effects_raw = list(effects_raw)

    effects = parse_effects(effects_raw)
    return apply_effects(game, effects, target_npc_id=target_npc_id)


def _dispatch_handler(game: GameState, handler: str, roll_result: str, params: dict) -> OutcomeResult:
    """Dispatch to the appropriate handler function."""
    handlers = {
        "suffer": apply_suffer_handler,
        "threshold": apply_threshold_handler,
        "recovery": apply_recovery_handler,
    }
    fn = handlers.get(handler)
    if fn is None:
        log(f"[MoveOutcome] Unknown handler: {handler!r}", level="warning")
        return OutcomeResult(narrative_only=True)
    return fn(game, roll_result, params)
