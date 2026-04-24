"""Move effect parsing and effect-level handlers.

Effect vocabulary (parsed from engine.yaml move_outcomes → <result_key>: [...]):
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
    bond +N                 Mark N on the target NPC's connection track
    disposition_shift       Advance target NPC's disposition one rung
    narrative               No mechanical effect, pure narrative

Narrator-facing consequence labels are templates from engine.yaml
ai_text.consequence_labels, keyed by effect type. Each template uses
str.format with named placeholders (value, n, track, name, old, new, impact).
The resulting strings end up in the <consequences> block read by the narrator.
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


@dataclass
class MoveEffect:
    """Single parsed mechanical effect."""

    type: str = ""  # momentum, health, spirit, supply, integrity, mark_progress, etc.
    value: int = 0  # numeric value (positive or negative)
    target: str = ""  # for legacy_reward: track name; for position: in_control/bad_spot


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
