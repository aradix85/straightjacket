from __future__ import annotations

from typing import Any

from ..logging_util import log
from ..models import GameState, consequence
from .config import rules
from .meters import momentum
from .move_effects import NPC_EFFECTS, MoveEffect, apply_effects, has_story_complication, parse_effects, roll_move_table
from .move_handlers import apply_recovery_handler, apply_suffer_handler, apply_threshold_handler
from .moves import get_moves
from .outcome_result import OutcomeResult, move_outcome_config
from .roll_sources import best_roll_option
from .rolls import roll_action


def resolve_move_outcome(
    game: GameState, move_key: str, roll_result: str, target_npc_id: str | None, match: bool
) -> OutcomeResult:
    move_cfg = move_outcome_config(game, move_key)
    result_key = roll_result.lower()

    handler = move_cfg.get("handler")
    if handler:
        params_dict = dict(move_cfg["params"])
        return _dispatch_handler(game, move_key, handler, roll_result, params_dict)

    match_key = f"{result_key}_match"
    effects_raw = move_cfg[match_key] if match and match_key in move_cfg else move_cfg.get(result_key)
    if effects_raw is None:
        raise ValueError(f"No effects for {move_key}/{result_key}. Add it to ruleset/move_outcomes.yaml.")

    effects = parse_effects(effects_raw)
    if match and roll_result not in rules().dice.hit_results and has_story_complication(game):
        effects = [MoveEffect(type="story_complication") if e.type == "pay_the_price" else e for e in effects]
    result = apply_effects(game, [e for e in effects if e.type != "table"], target_npc_id=target_npc_id)
    for effect in effects:
        if effect.type == "table":
            roll_move_table(game, move_key, effect.target, result)
    return result


def acts_on_an_npc(game: GameState, move_key: str) -> bool:
    lists = [effects for effects in move_outcome_config(game, move_key).values() if isinstance(effects, list)]
    return any(effect.type in NPC_EFFECTS for effects in lists for effect in parse_effects(effects))


def make_follow_up_moves(game: GameState, result: OutcomeResult) -> None:
    moves = get_moves(game.setting_id)
    for move_key in result.follow_up_moves:
        if game.game_over:
            return
        move = moves[move_key]
        stat, value = best_roll_option(game, move)
        roll = roll_action(stat, value, move_key, momentum(game), 0)
        log(f"[FollowUp] {move_key} ({stat}={value}): {roll.action_score} vs [{roll.c1},{roll.c2}] → {roll.result}")
        follow = resolve_move_outcome(game, move_key, roll.result, target_npc_id=None, match=roll.match)
        make_follow_up_moves(game, follow)
        result.consequences.append(consequence("chained_move", move=move.name, result=roll.result))
        result.consequences.extend(follow.consequences)


def _dispatch_handler(
    game: GameState, move_key: str, handler: str, roll_result: str, params: dict[str, Any]
) -> OutcomeResult:
    handlers = {
        "suffer": apply_suffer_handler,
        "threshold": apply_threshold_handler,
        "recovery": apply_recovery_handler,
    }
    if handler not in handlers:
        raise ValueError(f"Unknown move-outcome handler {handler!r}. Valid: {sorted(handlers)}.")
    return handlers[handler](game, move_key, roll_result, params)
