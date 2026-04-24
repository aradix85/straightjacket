"""Move outcome resolution: data-driven mechanical effects.

Replaces the category-based apply_consequences with move-specific outcomes.
Each move outcome is a list of effect strings parsed from engine.yaml.

Narrator-facing consequence labels are templates from engine.yaml
ai_text.consequence_labels, keyed by effect type. Each template uses
str.format with named placeholders (value, n, track, name, old, new, impact).
The resulting strings end up in the <consequences> block read by the narrator.

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

import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, NpcData
from ..npc import find_npc

from .impacts import apply_impact, blocks_recovery, clear_impact


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


def _roll_pay_the_price(game: GameState) -> str:
    """Pick one of the pay_the_price oracle outcomes and return the formatted line.

    The lines are in engine/pay_the_price.yaml. Some contain a {player}
    placeholder; all other tokens pass through unchanged.
    """
    pay_lines = eng().get_raw("pay_the_price")
    return random.choice(pay_lines).format(player=game.player_name)


def _apply_momentum_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    _e = eng()
    game.resources.adjust_momentum(effect.value, floor=_e.momentum.floor, ceiling=_e.momentum.max)
    sign = "+" if effect.value > 0 else ""
    result.consequences.append(_e.ai_text.consequence_labels["momentum_change"].format(value=f"{sign}{effect.value}"))


def _apply_resource_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    _e = eng()
    _labels = _e.ai_text.consequence_labels
    if effect.value > 0:
        cap = getattr(_e.resources, f"{effect.type}_max")
        gained = game.resources.heal(effect.type, effect.value, cap=cap)
        if gained:
            result.consequences.append(_labels["track_gain"].format(track=effect.type, n=gained))
    else:
        lost = game.resources.damage(effect.type, abs(effect.value))
        if lost:
            result.consequences.append(_labels["track_loss"].format(track=effect.type, n=lost))


def _apply_integrity_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    # Future: asset condition tracks (step 10). Log and skip for now.
    sign = "+" if effect.value > 0 else ""
    result.consequences.append(
        eng().ai_text.consequence_labels["integrity_change"].format(value=f"{sign}{effect.value}")
    )


def _apply_mark_progress_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.progress_marks += effect.value
    result.consequences.append(eng().ai_text.consequence_labels["mark_progress"].format(n=effect.value))


def _apply_pay_the_price_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.pay_the_price = True
    result.consequences.append(_roll_pay_the_price(game))


def _apply_next_move_bonus_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.next_move_bonus = effect.value
    result.consequences.append(eng().ai_text.consequence_labels["next_move_bonus"].format(n=effect.value))


def _apply_position_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    result.combat_position = effect.target


def _apply_suffer_move_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    _apply_generic_suffer(game, abs(effect.value), result)


def _apply_legacy_reward_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.legacy_track = effect.target
    result.consequences.append(eng().ai_text.consequence_labels["legacy_reward"].format(track=effect.target))


def _apply_fill_clock_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.clock_fills += effect.value
    result.consequences.append(eng().ai_text.consequence_labels["clock_fill"].format(n=effect.value))


def _apply_bond_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    if not target:
        return
    conn_track = next(
        (
            t
            for t in game.progress_tracks
            if t.track_type == "connection" and t.id == f"connection_{target.id}" and t.status == "active"
        ),
        None,
    )
    if not conn_track:
        log(f"[MoveOutcome] bond effect but no connection track for {target.name}")
        return
    _labels = eng().ai_text.consequence_labels
    for _ in range(abs(effect.value)):
        added = conn_track.mark_progress()
        if added:
            result.consequences.append(_labels["bond_progress"].format(name=target.name, n=added))


def _apply_disposition_shift_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    if not target:
        return
    _e = eng()
    shifts = _e.get_raw("disposition_shifts")
    old_disp = target.disposition
    # Top of the ladder (loyal) has no further shift; yaml only lists dispositions
    # that advance. Unchanged when no entry exists.
    if old_disp in shifts:
        target.disposition = shifts[old_disp]
        result.consequences.append(
            _e.ai_text.consequence_labels["disposition_shift"].format(
                name=target.name, old=old_disp, new=target.disposition
            )
        )


def _apply_narrative_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    result.narrative_only = True


_EFFECT_HANDLERS: dict[str, Callable[[GameState, MoveEffect, OutcomeResult, NpcData | None], None]] = {
    "momentum": _apply_momentum_effect,
    "health": _apply_resource_effect,
    "spirit": _apply_resource_effect,
    "supply": _apply_resource_effect,
    "integrity": _apply_integrity_effect,
    "mark_progress": _apply_mark_progress_effect,
    "pay_the_price": _apply_pay_the_price_effect,
    "next_move_bonus": _apply_next_move_bonus_effect,
    "position": _apply_position_effect,
    "suffer_move": _apply_suffer_move_effect,
    "legacy_reward": _apply_legacy_reward_effect,
    "fill_clock": _apply_fill_clock_effect,
    "bond": _apply_bond_effect,
    "disposition_shift": _apply_disposition_shift_effect,
    "narrative": _apply_narrative_effect,
}


def apply_effects(game: GameState, effects: list[MoveEffect], target_npc_id: str | None = None) -> OutcomeResult:
    """Apply a list of parsed effects to game state. Dispatches each effect
    to its handler. Unknown effect types log a warning. Returns result summary.
    """
    result = OutcomeResult()
    target = find_npc(game, target_npc_id) if target_npc_id else None

    for effect in effects:
        handler = _EFFECT_HANDLERS.get(effect.type)
        if handler:
            handler(game, effect, result, target)
        elif effect.type != "unknown":
            log(f"[MoveOutcome] Unhandled effect type: {effect.type}", level="warning")

    return result


def _apply_generic_suffer(game: GameState, amount: int, result: OutcomeResult) -> None:
    """Apply generic suffer move: pick the most appropriate track based on game state."""
    _e = eng()
    _labels = _e.ai_text.consequence_labels
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
        result.consequences.append(_labels["track_loss"].format(track=track, n=lost))


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
    _labels = _e.ai_text.consequence_labels
    res = game.resources
    track = params["track"]
    recovery = params["recovery"]
    miss_extra_track = params["miss_extra_track"]
    miss_extra_momentum = params["miss_extra_momentum"]

    has_blocking_impact = bool(blocks_recovery(game, track))
    strong_gain = _e.momentum.suffer_recovery.strong_hit_gain
    weak_exchange = _e.momentum.suffer_recovery.weak_hit_exchange_cost

    if roll_result == "STRONG_HIT":
        if track in ("health", "spirit", "supply") and not has_blocking_impact:
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, recovery, cap=cap)
            if gained:
                result.consequences.append(_labels["track_gain"].format(track=track, n=gained))
            else:
                # Track already at max, take momentum instead
                res.adjust_momentum(strong_gain, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(_labels["momentum_change"].format(value=f"+{strong_gain}"))
        else:
            # Blocking impact or non-standard track: take momentum
            res.adjust_momentum(strong_gain, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            result.consequences.append(_labels["momentum_change"].format(value=f"+{strong_gain}"))

    elif roll_result == "WEAK_HIT":
        if track in ("health", "spirit", "supply") and not has_blocking_impact:
            # Exchange: momentum -weak_exchange for track +recovery
            res.adjust_momentum(-weak_exchange, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, recovery, cap=cap)
            result.consequences.append(_labels["momentum_change"].format(value=f"-{weak_exchange}"))
            if gained:
                result.consequences.append(_labels["track_gain"].format(track=track, n=gained))

    else:  # MISS
        # Extra track damage or momentum loss — engine picks track damage
        if track in ("health", "spirit", "supply"):
            lost = res.damage(track, abs(miss_extra_track))
            if lost:
                result.consequences.append(_labels["track_loss"].format(track=track, n=lost))
            else:
                # Track already at 0, take momentum instead
                res.adjust_momentum(miss_extra_momentum, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(_labels["momentum_change"].format(value=str(miss_extra_momentum)))
        else:
            res.adjust_momentum(miss_extra_momentum, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            result.consequences.append(_labels["momentum_change"].format(value=str(miss_extra_momentum)))

        # Track at zero → mark impact. Engine picks first of impact_pair.
        track_value = getattr(res, track, None) if track in ("health", "spirit", "supply") else None
        if track_value is not None and track_value <= 0:
            impact_pair = params["impact_pair"]
            if impact_pair:
                # First impact if not yet active, otherwise the worse one
                chosen = impact_pair[0] if impact_pair[0] not in game.impacts else impact_pair[1]
                if apply_impact(game, chosen):
                    result.consequences.append(_labels["mark_impact"].format(impact=chosen))

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
    _labels = eng().ai_text.consequence_labels

    if roll_result == "STRONG_HIT":
        result.narrative_only = True

    elif roll_result == "WEAK_HIT":
        impact = params["impact"]
        if impact and apply_impact(game, impact):
            result.consequences.append(_labels["mark_impact"].format(impact=impact))
        result.consequences.append(_labels["threshold_vow"])

    else:  # MISS
        game.game_over = True
        result.consequences.append(params["game_over_text"])

    return result


def apply_recovery_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
    """Handle recovery moves with conditional impact clearing: heal, hearten, resupply.

    strong_hit: if blocking impact, clear it and take reduced amount. Otherwise full amount.
    weak_hit: same as strong_hit but with additional cost (momentum or supply loss).
    miss: pay the price.

    Params:
      track: health / spirit / supply
      full_amount: recovery without impact
      impact_amount: recovery when clearing impact
      blocking_impact: impact name (wounded, shaken, unprepared)
      weak_hit_cost_type: momentum / supply
      weak_hit_cost: amount
    """
    result = OutcomeResult()
    _e = eng()
    _labels = _e.ai_text.consequence_labels
    res = game.resources
    track = params["track"]
    full_amount = params["full_amount"]
    impact_amount = params["impact_amount"]
    blocking_impact = params["blocking_impact"]
    weak_cost_type = params["weak_hit_cost_type"]
    weak_cost = params["weak_hit_cost"]

    has_impact = bool(blocking_impact) and blocking_impact in game.impacts

    if roll_result in ("STRONG_HIT", "WEAK_HIT"):
        amount = impact_amount if has_impact else full_amount
        if has_impact and clear_impact(game, blocking_impact):
            result.consequences.append(_labels["clear_impact"].format(impact=blocking_impact))

        if track in ("health", "spirit", "supply"):
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, amount, cap=cap)
            if gained:
                result.consequences.append(_labels["track_gain"].format(track=track, n=gained))

        if roll_result == "WEAK_HIT":
            if weak_cost_type == "momentum":
                res.adjust_momentum(weak_cost, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(_labels["momentum_change"].format(value=str(weak_cost)))
            elif weak_cost_type == "supply":
                lost = res.damage("supply", abs(weak_cost))
                if lost:
                    result.consequences.append(_labels["track_loss"].format(track="supply", n=lost))

    else:  # MISS
        result.pay_the_price = True
        result.consequences.append(_roll_pay_the_price(game))

    return result


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
    outcomes_cfg = _e.get_raw("move_outcomes")

    result_key = roll_result.lower()

    move_cfg = outcomes_cfg.get(move_key)
    if move_cfg is None:
        raise ValueError(f"No outcome config for {move_key}. Add it to engine.yaml move_outcomes.")

    # Handler-based moves
    handler = move_cfg.get("handler")
    if handler:
        # Handler moves require a params block in yaml.
        params_dict = dict(move_cfg["params"])
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
    """Dispatch to the appropriate handler function. Raises on unknown handler."""
    handlers = {
        "suffer": apply_suffer_handler,
        "threshold": apply_threshold_handler,
        "recovery": apply_recovery_handler,
    }
    if handler not in handlers:
        raise ValueError(f"Unknown move-outcome handler {handler!r}. Valid: {sorted(handlers)}.")
    return handlers[handler](game, roll_result, params)
