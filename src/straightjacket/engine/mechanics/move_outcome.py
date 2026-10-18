from __future__ import annotations

from typing import Any

from ..datasworn.moves import get_moves
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState
from .consequences import roll_action
from .move_effects import MoveEffect, apply_effects, has_story_complication, parse_effects
from .move_handlers import apply_recovery_handler, apply_suffer_handler, apply_threshold_handler
from .outcome_result import OutcomeResult, move_outcome_config
from .roll_sources import best_roll_option


def resolve_move_outcome(
    game: GameState, move_key: str, roll_result: str, target_npc_id: str | None, match: bool
) -> OutcomeResult:
    move_cfg = move_outcome_config(game, move_key)
    result_key = roll_result.lower()

    handler = move_cfg.get("handler")
    if handler:
        params_dict = dict(move_cfg["params"])
        return _dispatch_handler(game, handler, roll_result, params_dict)

    match_key = f"{result_key}_match"
    effects_raw = move_cfg[match_key] if match and match_key in move_cfg else move_cfg.get(result_key)
    if effects_raw is None:
        raise ValueError(f"No effects for {move_key}/{result_key}. Add it to engine.yaml move_outcomes.")

    effects = parse_effects(effects_raw)
    if match and roll_result == "MISS" and has_story_complication(game):
        effects = [MoveEffect(type="story_complication") if e.type == "pay_the_price" else e for e in effects]
    return apply_effects(game, effects, target_npc_id=target_npc_id)


def make_follow_up_moves(game: GameState, result: OutcomeResult) -> None:
    labels = eng().ai_text.consequence_labels
    moves = get_moves(game.setting_id)
    for move_key in result.follow_up_moves:
        if game.game_over:
            return
        move = moves[move_key]
        stat, value = best_roll_option(game, move)
        roll = roll_action(stat, value, move_key, game.resources.momentum, 0)
        log(f"[FollowUp] {move_key} ({stat}={value}): {roll.action_score} vs [{roll.c1},{roll.c2}] → {roll.result}")
        follow = resolve_move_outcome(game, move_key, roll.result, target_npc_id=None, match=roll.match)
        make_follow_up_moves(game, follow)
        result.consequences.append(labels["chained_move"].format(move=move.name, result=roll.result))
        result.consequences.extend(follow.consequences)


def _dispatch_handler(game: GameState, handler: str, roll_result: str, params: dict[str, Any]) -> OutcomeResult:
    handlers = {
        "suffer": apply_suffer_handler,
        "threshold": apply_threshold_handler,
        "recovery": apply_recovery_handler,
    }
    if handler not in handlers:
        raise ValueError(f"Unknown move-outcome handler {handler!r}. Valid: {sorted(handlers)}.")
    return handlers[handler](game, roll_result, params)
