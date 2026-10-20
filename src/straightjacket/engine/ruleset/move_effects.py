from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from ..engine_loader import eng
from ..gamemaster.clocks import spawn_complication_clock
from ..gamemaster.config import gm
from ..gamemaster.npc.matching import find_npc
from ..gamemaster.random_events import roll_meaning_table
from ..logging_util import log
from ..models import Consequence, GameState, NpcData, ProgressTrack, consequence
from ..setting.loader import OracleTable
from ..setting.oracle_rolls import plain_text, roll_rows, roll_table
from ..setting.packages import load_package
from .bond import connection_track, seal_bond
from .config import rules
from .impacts import blocks_recovery
from .legacy import shifted_rank
from .meters import adjust_momentum, condition_meters, gain, is_condition_meter
from .moves import Move, get_moves, move_table, offers_table
from .outcome_result import OutcomeResult, new_outcome
from .progress import filled_boxes, mark_progress
from .suffer import suffer


@dataclass
class MoveEffect:
    type: str
    value: int
    target: str


_PLAIN_EFFECTS = frozenset(
    {
        "pay_the_price",
        "disposition_shift",
        "raise_connection_rank",
        "bond_request",
        "seal_bond",
        "clear_bond",
        "obstacle",
        "loyalty_test",
    }
)
_EFFECT_RE = re.compile(r"^(\w+)\s+([+-]?\d+)$")
_POSITION_RE = re.compile(r"^position\s+(\w+)$")
_LEGACY_RE = re.compile(r"^legacy_reward\s+(\w+)$")
_CHAIN_MOVE_RE = re.compile(r"^chain_move\s+(\S+)$")
_LEGACY_LOWER_RE = re.compile(r"^legacy_reward_lower\s+(\w+)$")
_LEGACY_TICKS_RE = re.compile(r"^legacy_ticks\s+(\w+)\s+(\d+)$")
_FILL_CLOCK_RE = re.compile(r"^fill_clock\s+(\d+)$")
_COMPLICATION_RE = re.compile(r"^complication\s+(\w+)$")
_TABLE_RE = re.compile(r"^table\s+(\w+)$")


def parse_effect(effect_str: str) -> MoveEffect:
    effect_str = effect_str.strip()

    m = _EFFECT_RE.match(effect_str)
    if m:
        return MoveEffect(type=m.group(1), value=int(m.group(2)), target="")

    m = _POSITION_RE.match(effect_str)
    if m:
        return MoveEffect(type="position", value=0, target=m.group(1))

    m = _CHAIN_MOVE_RE.match(effect_str)
    if m:
        return MoveEffect(type="chain_move", value=0, target=m.group(1))

    m = _LEGACY_LOWER_RE.match(effect_str)
    if m:
        return MoveEffect(type="legacy_reward_lower", value=0, target=m.group(1))

    m = _LEGACY_TICKS_RE.match(effect_str)
    if m:
        return MoveEffect(type="legacy_ticks", value=int(m.group(2)), target=m.group(1))

    m = _LEGACY_RE.match(effect_str)
    if m:
        return MoveEffect(type="legacy_reward", value=0, target=m.group(1))

    m = _FILL_CLOCK_RE.match(effect_str)
    if m:
        return MoveEffect(type="fill_clock", value=int(m.group(1)), target="")

    m = _COMPLICATION_RE.match(effect_str)
    if m:
        return MoveEffect(type="complication", value=0, target=m.group(1))

    m = _TABLE_RE.match(effect_str)
    if m:
        return MoveEffect(type="table", value=0, target=m.group(1))

    if effect_str in _PLAIN_EFFECTS:
        return MoveEffect(type=effect_str, value=0, target="")

    raise ValueError(f"Unknown move effect {effect_str!r}")


def parse_effects(effect_list: list[str]) -> list[MoveEffect]:
    return [parse_effect(e) for e in effect_list]


def roll_oracle_result(table: OracleTable) -> tuple[list[str], Consequence]:
    rolled = roll_rows(table)
    rows = [plain_text(row.text) for row in rolled.rows]
    worse = rolled.worse
    if len(rows) == 1 and rows[0].startswith(tuple(rules().pay_the_price.worse_reroll_prefixes)):
        again = [plain_text(row.text) for row in roll_rows(table).rows]
        if again != rows:
            rows, worse = again, True
    result = "; ".join(rows)
    if worse:
        result = eng().ai_text.consequence_labels["oracle_worse"].format(result=result)
    return rows, consequence("oracle_result", table=table.title, result=result)


def _pay_the_price_move(game: GameState) -> Move:
    return get_moves(game.setting_id)[rules().pay_the_price.move]


def has_story_complication(game: GameState) -> bool:
    return offers_table(game.setting_id, _pay_the_price_move(game), rules().pay_the_price.match_miss_table)


def complication_replaces_price(game: GameState, match: bool) -> bool:
    return match and has_story_complication(game)


def roll_story_complication(game: GameState, result: OutcomeResult) -> None:
    _rows, told = roll_oracle_result(
        move_table(game.setting_id, _pay_the_price_move(game), rules().pay_the_price.match_miss_table)
    )
    log(f"[StoryComplication] {told.label}")
    result.consequences.append(told)


def roll_move_table(game: GameState, move_key: str, key: str, result: OutcomeResult) -> None:
    table = move_table(game.setting_id, get_moves(game.setting_id)[move_key], key)
    text = plain_text(roll_table(load_package(game.setting_id), table).text)
    told = consequence("oracle_result", table=table.title, result=text)
    log(f"[MoveTable] {told.label}")
    result.consequences.append(told)
    for rule in rules().get_raw("move_table_rows")[key]:
        if text.startswith(rule["prefix"]):
            _apply_effect(game, parse_effect(rule["effect"]), result, None)


def pay_the_price(game: GameState, result: OutcomeResult) -> None:
    rows, told = roll_oracle_result(_pay_the_price_move(game).tables[rules().pay_the_price.table])
    log(f"[PayThePrice] {told.label}")
    result.consequences.append(told)
    for row in rows:
        for rule in rules().pay_the_price.suffer_rows:
            if row.startswith(rule.prefix):
                _apply_effect(game, parse_effect(rule.effect), result, None)


def _apply_momentum_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    adjust_momentum(game, effect.value)
    result.consequences.append(consequence("momentum_change", n=effect.value))


def _apply_meter_effect(game: GameState, effect: MoveEffect, result: OutcomeResult) -> None:
    if effect.value > 0:
        blocking = blocks_recovery(game, effect.type)
        if blocking:
            log(f"[Impact] {blocking} keeps {effect.type} from rising")
            return
        gained = gain(game, effect.type, effect.value)
        if gained:
            result.consequences.append(consequence("track_gain", track=effect.type, n=gained))
    else:
        suffer(game, effect.type, abs(effect.value), result)


def _apply_seal_bond_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    npc = _required_target(effect, target)
    track = seal_bond(game, npc)
    result.consequences.append(consequence("bond_sealed", name=npc.name))
    log(f"[Bond] {npc.name}: bond sealed ({filled_boxes(track)} boxes)")


def _apply_clear_bond_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    npc, track = _target_connection(game, effect, target)
    game.progress_tracks.remove(track)
    result.consequences.append(consequence("bond_cleared", name=npc.name))
    log(f"[Bond] {npc.name}: bond cleared")


def _apply_told_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    result.consequences.append(consequence(effect.type))


def _apply_mark_progress_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.progress_marks += effect.value
    result.consequences.append(consequence("mark_progress", n=effect.value))


def _apply_pay_the_price_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    pay_the_price(game, result)


def _apply_story_complication_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    roll_story_complication(game, result)


def _apply_next_move_bonus_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    game.resources.next_move_bonus += effect.value
    result.consequences.append(consequence("next_move_bonus", n=effect.value))


def _apply_position_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    result.combat_position = effect.target


def _apply_suffer_move_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    _apply_generic_suffer(game, abs(effect.value), result)


NPC_EFFECTS = frozenset({"bond", "raise_connection_rank", "disposition_shift", "seal_bond", "clear_bond"})
CONNECTION_EFFECTS = frozenset({"bond", "raise_connection_rank", "clear_bond"})


def _required_target(effect: MoveEffect, target: NpcData | None) -> NpcData:
    if target is None:
        raise ValueError(f"The {effect.type} effect needs a target NPC")
    return target


def _target_connection(game: GameState, effect: MoveEffect, target: NpcData | None) -> tuple[NpcData, ProgressTrack]:
    npc = _required_target(effect, target)
    track = connection_track(game, npc.id)
    if track is None:
        raise ValueError(f"The {effect.type} effect needs a connection with {npc.name}")
    return npc, track


def _apply_raise_connection_rank_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    target, track = _target_connection(game, effect, target)
    higher = shifted_rank(track.rank, 1)
    if higher is None:
        return
    track.rank = higher
    result.consequences.append(consequence("connection_rank", name=target.name, rank=higher))


def _apply_chain_move_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.chained_move = effect.target


def _apply_legacy_reward_lower_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.legacy_track = effect.target
    result.legacy_rank_shift = -1
    result.consequences.append(consequence("legacy_reward", track=effect.target))


def _apply_legacy_ticks_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.legacy_track = effect.target
    result.legacy_fixed_ticks = effect.value
    result.consequences.append(consequence("legacy_reward", track=effect.target))


def _apply_legacy_reward_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.legacy_track = effect.target
    result.consequences.append(consequence("legacy_reward", track=effect.target))


def _apply_experience_by_rank_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.experience_rank_shift = effect.value
    result.consequences.append(consequence("experience_reward"))


def _apply_boasts_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    result.boast_slots = effect.value


def _apply_fill_clock_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.clock_fills += effect.value
    result.consequences.append(consequence("clock_fill", n=effect.value))


def _complication_danger(game: GameState) -> str:
    pkg = load_package(game.setting_id)
    path = gm().clocks.complication.name_oracle_path
    if pkg.has_oracle(path):
        return "; ".join(plain_text(row.text) for row in roll_rows(pkg.oracle_table(path)).rows)
    action, subject = roll_meaning_table("actions")
    return f"{action} {subject}"


def _apply_complication_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    result.consequences.append(consequence("complication", kind=effect.target))
    clock = spawn_complication_clock(game, effect.target, _complication_danger(game))
    if clock is not None:
        result.consequences.append(consequence("complication_clock", name=clock.name))


def _apply_bond_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    target, conn_track = _target_connection(game, effect, target)
    for _ in range(abs(effect.value)):
        added = mark_progress(conn_track)
        if added:
            result.consequences.append(consequence("bond_progress", name=target.name, n=added))


def _apply_disposition_shift_effect(
    game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None
) -> None:
    target = _required_target(effect, target)
    shifts = gm().get_raw("disposition_shifts")
    old_disp = target.disposition

    if old_disp in shifts:
        target.disposition = shifts[old_disp]
        result.consequences.append(
            consequence("disposition_shift", name=target.name, old=old_disp, new=target.disposition)
        )


_EFFECT_HANDLERS: dict[str, Callable[[GameState, MoveEffect, OutcomeResult, NpcData | None], None]] = {
    "momentum": _apply_momentum_effect,
    "mark_progress": _apply_mark_progress_effect,
    "pay_the_price": _apply_pay_the_price_effect,
    "story_complication": _apply_story_complication_effect,
    "next_move_bonus": _apply_next_move_bonus_effect,
    "position": _apply_position_effect,
    "suffer_move": _apply_suffer_move_effect,
    "legacy_reward": _apply_legacy_reward_effect,
    "legacy_reward_lower": _apply_legacy_reward_lower_effect,
    "experience_by_rank": _apply_experience_by_rank_effect,
    "boasts": _apply_boasts_effect,
    "chain_move": _apply_chain_move_effect,
    "raise_connection_rank": _apply_raise_connection_rank_effect,
    "legacy_ticks": _apply_legacy_ticks_effect,
    "fill_clock": _apply_fill_clock_effect,
    "complication": _apply_complication_effect,
    "bond": _apply_bond_effect,
    "disposition_shift": _apply_disposition_shift_effect,
    "bond_request": _apply_told_effect,
    "obstacle": _apply_told_effect,
    "loyalty_test": _apply_told_effect,
    "seal_bond": _apply_seal_bond_effect,
    "clear_bond": _apply_clear_bond_effect,
}


def _apply_effect(game: GameState, effect: MoveEffect, result: OutcomeResult, target: NpcData | None) -> None:
    if is_condition_meter(game, effect.type):
        _apply_meter_effect(game, effect, result)
    else:
        _EFFECT_HANDLERS[effect.type](game, effect, result, target)


def apply_effects(game: GameState, effects: list[MoveEffect], target_npc_id: str | None = None) -> OutcomeResult:
    result = new_outcome()
    target = find_npc(game, target_npc_id) if target_npc_id else None

    for effect in effects:
        _apply_effect(game, effect, result, target)

    return result


def _apply_generic_suffer(game: GameState, amount: int, result: OutcomeResult) -> None:
    meters = game.resources.meters
    highest = max(condition_meters(game.setting_id), key=lambda meter: meters[meter])
    suffer(game, highest, amount, result)
