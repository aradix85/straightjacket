from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.logging_util import log
from straightjacket.engine.models import consequence, labels_of
from straightjacket.engine.ruleset.boasts import apply_boasts
from straightjacket.engine.ruleset.bond import connection_track, is_bonded
from straightjacket.engine.ruleset.bonuses import apply_momentum_on_hit, bond_of_bonus, chosen_bonus
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.legacy import mark_legacy_ticks
from straightjacket.engine.ruleset.meters import momentum
from straightjacket.engine.ruleset.move_effects import apply_effects, parse_effects
from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
from straightjacket.engine.ruleset.moves import PICK_METHODS, get_moves
from straightjacket.engine.ruleset.outcome_result import move_outcome_config
from straightjacket.engine.ruleset.progress import filled_boxes
from straightjacket.engine.ruleset.roll_sources import best_roll_option, roll_by_method, roll_source_without_stat
from straightjacket.engine.ruleset.rolls import (
    downgrade_in_position,
    keep_action_dice,
    keep_progress_dice,
    roll_action,
    roll_progress,
)
from straightjacket.engine.ruleset.tracks import apply_progress_and_legacy, find_progress_track
from straightjacket.engine.setting.oracle_rolls import plain_text, roll_rows

if TYPE_CHECKING:
    from straightjacket.engine.models import BrainResult, GameState, ProgressTrack, RollResult
    from straightjacket.engine.ruleset.moves import Move
    from straightjacket.engine.ruleset.outcome_result import OutcomeResult
    from straightjacket.engine.setting.loader import OracleTable


@dataclass
class RollOutcome:
    roll: RollResult
    ds_move: Move | None
    track: ProgressTrack | None


def roll_move(game: GameState, brain: BrainResult, earlier: RollResult | None) -> RollOutcome:
    ds_move = get_moves(game.setting_id).get(brain.move)
    track: ProgressTrack | None = None

    if ds_move is not None and ds_move.is_progress_roll:
        track = find_progress_track(game, ds_move.track_category, brain.target_track)
        filled = filled_boxes(track)
        if earlier is None:
            roll = roll_progress(track.name, filled, brain.move)
        else:
            roll = keep_progress_dice(earlier, track.name, filled, brain.move)
        roll = downgrade_in_position(game, roll)
        log(
            f"[Roll] {roll.move} (progress: {track.name}={filled} boxes): "
            f"{roll.action_score} vs [{roll.c1},{roll.c2}] "
            f"→ {roll.result}{' MATCH!' if roll.match else ''}"
        )
    else:
        stat_name, stat_value = _roll_source(game, brain, ds_move)
        bonus = chosen_bonus(game, brain.bonus_id)
        adds = game.resources.next_move_bonus + (bonus.add if bonus else 0)
        rolled_momentum = momentum(game)
        if earlier is None:
            roll = roll_action(stat_name, stat_value, brain.move, rolled_momentum, adds)
        else:
            roll = keep_action_dice(earlier, stat_name, stat_value, brain.move, rolled_momentum, adds)
        game.resources.next_move_bonus = 0
        if bonus:
            apply_momentum_on_hit(game, bonus, roll.result)
        _log_action_roll(roll, adds, cancelled=rolled_momentum < 0 and -rolled_momentum == roll.d1)

    return RollOutcome(roll=roll, ds_move=ds_move, track=track)


def plays_without_roll(move: str) -> bool:
    return move in rules().offered_without_roll


def make_move_without_roll(game: GameState, brain: BrainResult) -> OutcomeResult:
    effects = parse_effects(move_outcome_config(game, brain.move)["no_roll"])
    outcome = apply_effects(game, effects, target_npc_id=brain.target_npc)
    apply_progress_and_legacy(game, outcome, brain, None)
    log(f"[Move] {brain.move} without a roll: {', '.join(labels_of(outcome.consequences))}")
    return outcome


def _roll_source(game: GameState, brain: BrainResult, ds_move: Move | None) -> tuple[str, int]:
    if ds_move is not None and not ds_move.valid_stats:
        source = roll_source_without_stat(game, ds_move, brain.target_npc)
        if source is None:
            raise ValueError(f"{brain.move!r} has nothing to roll with for target {brain.target_npc!r}")
        return source
    if brain.stat == eng().ai_text.no_stat:
        raise ValueError(f"{brain.move!r} is an action roll, but the Brain named no stat")
    if brain.stat in PICK_METHODS:
        if ds_move is None:
            raise ValueError(f"{brain.move!r} has no way that rolls the {brain.stat} stat")
        return roll_by_method(game, ds_move, brain.stat)
    return brain.stat, game.stats[brain.stat]


def _log_action_roll(roll: RollResult, adds: int, cancelled: bool) -> None:
    raw = (0 if cancelled else roll.d1) + roll.stat_value + adds
    score = f"{raw}→{roll.action_score}(cap)" if raw > roll.action_score else str(roll.action_score)
    log(
        f"[Roll] {roll.move} ({roll.stat_name}={roll.stat_value}): "
        f"{roll.d1}+{roll.stat_value}{f'+{adds}' if adds else ''}={score} vs [{roll.c1},{roll.c2}] "
        f"→ {roll.result}{' MATCH!' if roll.match else ''}"
        f"{' (action die cancelled by negative momentum)' if cancelled else ''}"
    )


def resolve_move(game: GameState, brain: BrainResult, roll: RollResult) -> OutcomeResult:
    outcome = resolve_move_outcome(
        game,
        brain.move,
        roll.result,
        target_npc_id=brain.target_npc,
        aided_by=bond_of_bonus(game, brain.bonus_id),
        match=roll.match,
    )
    if outcome.chained_move:
        _chain_move(game, brain, outcome)
    if outcome.boast_slots:
        apply_boasts(game, brain.boasts, outcome)
    if outcome.combat_position:
        game.world.combat_position = outcome.combat_position
    return outcome


def _chained_roll_value(game: GameState, brain: BrainResult, move: Move) -> tuple[str, int] | None:
    if move.valid_stats:
        return best_roll_option(game, move)
    return roll_source_without_stat(game, move, brain.target_npc)


def _roll_chained_table(table: OracleTable, reroll_prefixes: list[str]) -> str:
    while True:
        rolled = roll_rows(table)
        rows = [plain_text(row.text) for row in rolled.rows]
        if not any(row.startswith(tuple(reroll_prefixes)) for row in rows):
            text = "; ".join(rows)
            return eng().ai_text.consequence_labels["oracle_worse"].format(result=text) if rolled.worse else text


def _chain_oracle_move(game: GameState, move: Move, cfg: dict[str, Any], outcome: OutcomeResult) -> None:
    table = move.tables[cfg["table"]]
    results = [_roll_chained_table(table, cfg["reroll_prefixes"]) for _ in range(cfg["rolls"])]
    outcome.consequences.append(consequence("chained_move", move=move.name, result="; ".join(results)))
    if cfg["legacy_track"]:
        mark_legacy_ticks(game, cfg["legacy_track"], cfg["ticks_per_roll"] * cfg["rolls"])
    log(f"[Chain] {move.name}: {'; '.join(results)}")


def _chain_without_bond(game: GameState, brain: BrainResult, outcome: OutcomeResult) -> bool:
    cfg = move_outcome_config(game, outcome.chained_move)
    track = connection_track(game, brain.target_npc) if brain.target_npc is not None else None
    if "without_bond" not in cfg or track is None or is_bonded(track):
        return False
    marked = apply_effects(game, parse_effects(cfg["without_bond"]), target_npc_id=brain.target_npc)
    outcome.consequences.extend(marked.consequences)
    log(f"[Chain] {outcome.chained_move}: no bond with {track.name} yet, so progress is marked without a roll")
    return True


def _chain_move(game: GameState, brain: BrainResult, outcome: OutcomeResult) -> None:
    move = get_moves(game.setting_id)[outcome.chained_move]
    oracle_moves = rules().get_raw("oracle_moves")
    if move.roll_type == "no_roll" and outcome.chained_move in oracle_moves:
        _chain_oracle_move(game, move, oracle_moves[outcome.chained_move], outcome)
        return
    if _chain_without_bond(game, brain, outcome):
        return
    value = _chained_roll_value(game, brain, move)
    if value is None:
        log(f"[Chain] {outcome.chained_move}: nothing to roll with, follow-up skipped", level="warning")
        return
    label, stat_value = value
    adds = game.resources.next_move_bonus
    roll = roll_action(label, stat_value, outcome.chained_move, momentum(game), adds)
    game.resources.next_move_bonus = 0
    chained = resolve_move_outcome(
        game, outcome.chained_move, roll.result, target_npc_id=brain.target_npc, aided_by=None, match=roll.match
    )
    log(
        f"[Chain] {outcome.chained_move} ({label}={stat_value}, +{adds}): "
        f"score {roll.action_score} vs [{roll.c1},{roll.c2}] → {roll.result}"
    )
    outcome.consequences.append(consequence("chained_move", move=move.name, result=roll.result))
    outcome.consequences.extend(chained.consequences)
    outcome.follow_up_moves.extend(chained.follow_up_moves)
    if chained.legacy_track and not outcome.legacy_track:
        outcome.legacy_track = chained.legacy_track
        outcome.legacy_rank_shift = chained.legacy_rank_shift
        outcome.legacy_fixed_ticks = chained.legacy_fixed_ticks
