from __future__ import annotations

from typing import Any

from ..gamemaster.npc.matching import find_npc
from ..logging_util import log
from ..models import GameState, consequence
from .bond import connection_track, is_bonded
from .config import rules
from .datasworn import load_ruleset
from .meters import momentum
from .move_effects import (
    CONNECTION_EFFECTS,
    NPC_EFFECTS,
    MoveEffect,
    apply_effects,
    complication_replaces_price,
    parse_effects,
    roll_move_table,
)
from .move_handlers import apply_recovery_handler, apply_suffer_handler, apply_threshold_handler
from .moves import get_moves
from .outcome_result import OutcomeResult, move_outcome_config
from .roll_sources import best_roll_option
from .rolls import roll_action
from .sojourn import apply_sojourn_handler


def resolve_move_outcome(
    game: GameState, move_key: str, roll_result: str, target_npc_id: str | None, aided_by: str | None, match: bool
) -> OutcomeResult:
    move_cfg = move_outcome_config(game, move_key)
    result_key = roll_result.lower()

    handler = move_cfg.get("handler")
    if handler == "sojourn":
        return apply_sojourn_handler(game, move_key, roll_result, dict(move_cfg["params"]), match, aided_by)
    if handler:
        params_dict = dict(move_cfg["params"])
        return _dispatch_handler(game, move_key, handler, roll_result, params_dict, match)

    match_key = f"{result_key}_match"
    effects_raw = move_cfg[match_key] if match and match_key in move_cfg else move_cfg.get(result_key)
    if effects_raw is None:
        raise ValueError(f"No effects for {move_key}/{result_key}. Add it to ruleset/move_outcomes.yaml.")

    effects = parse_effects(effects_raw)
    if roll_result not in rules().dice.hit_results and complication_replaces_price(game, match):
        effects = [
            MoveEffect(type="story_complication", value=0, target="") if e.type == "pay_the_price" else e
            for e in effects
        ]
    result = apply_effects(game, [e for e in effects if e.type != "table"], target_npc_id=target_npc_id)
    for effect in effects:
        if effect.type == "table":
            roll_move_table(game, move_key, effect.target, result)
    return result


def _effect_types(game: GameState, move_key: str) -> set[str]:
    lists = [effects for effects in move_outcome_config(game, move_key).values() if isinstance(effects, list)]
    return {effect.type for effects in lists for effect in parse_effects(effects)}


def acts_on_an_npc(game: GameState, move_key: str) -> bool:
    return bool(_effect_types(game, move_key) & NPC_EFFECTS)


def needs_a_connection(game: GameState, move_key: str) -> bool:
    return bool(_effect_types(game, move_key) & CONNECTION_EFFECTS)


def make_follow_up_moves(game: GameState, result: OutcomeResult) -> None:
    for move_key in result.follow_up_moves:
        if game.game_over:
            return
        _make_follow_up(game, move_key, None, result)


def _make_follow_up(game: GameState, move_key: str, target_npc_id: str | None, result: OutcomeResult) -> None:
    move = get_moves(game.setting_id)[move_key]
    stat, value = best_roll_option(game, move)
    roll = roll_action(stat, value, move_key, momentum(game), 0)
    log(f"[FollowUp] {move_key} ({stat}={value}): {roll.action_score} vs [{roll.c1},{roll.c2}] → {roll.result}")
    follow = resolve_move_outcome(
        game, move_key, roll.result, target_npc_id=target_npc_id, aided_by=None, match=roll.match
    )
    make_follow_up_moves(game, follow)
    result.consequences.append(consequence("chained_move", move=move.name, result=roll.result))
    result.consequences.extend(follow.consequences)


def make_due_bond_test(game: GameState, npc_id: str | None, rolled_move: str | None, result: OutcomeResult) -> None:
    if npc_id is None or game.game_over:
        return
    forsaken = [t for t in game.progress_tracks if t.vowed_to == npc_id and t.status == "failed"]
    if not forsaken:
        return
    for vow in forsaken:
        vow.vowed_to = None
    move_key = rules().suffer.forsake_vow.bond_test[load_ruleset(game.setting_id).id]
    track = connection_track(game, npc_id)
    if move_key is None or rolled_move == move_key or track is None or not is_bonded(track):
        log(f"[Bond] {npc_id}: the forsaken vow '{forsaken[0].name}' asks no test of a bond now")
        return
    npc = find_npc(game, npc_id)
    assert npc is not None
    result.consequences.append(consequence("bond_tested", name=npc.name, vow=forsaken[0].name))
    log(f"[Bond] {npc.name}: the forsaken vow '{forsaken[0].name}' tests the bond")
    _make_follow_up(game, move_key, npc_id, result)


def _dispatch_handler(
    game: GameState, move_key: str, handler: str, roll_result: str, params: dict[str, Any], match: bool
) -> OutcomeResult:
    handlers = {
        "suffer": apply_suffer_handler,
        "threshold": apply_threshold_handler,
        "recovery": apply_recovery_handler,
    }
    if handler not in handlers:
        raise ValueError(f"Unknown move-outcome handler {handler!r}. Valid: {sorted(handlers)}.")
    return handlers[handler](game, move_key, roll_result, params, match)
