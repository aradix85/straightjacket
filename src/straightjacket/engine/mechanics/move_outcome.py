from __future__ import annotations

from ..engine_loader import eng
from ..models import GameState
from .move_effects import OutcomeResult, apply_effects, parse_effects
from .move_handlers import apply_recovery_handler, apply_suffer_handler, apply_threshold_handler


def resolve_move_outcome(
    game: GameState, move_key: str, roll_result: str, target_npc_id: str | None = None
) -> OutcomeResult:
    _e = eng()
    outcomes_cfg = _e.get_raw("move_outcomes")

    result_key = roll_result.lower()

    move_cfg = outcomes_cfg.get(move_key)
    if move_cfg is None:
        raise ValueError(f"No outcome config for {move_key}. Add it to engine.yaml move_outcomes.")

    handler = move_cfg.get("handler")
    if handler:
        params_dict = dict(move_cfg["params"])
        return _dispatch_handler(game, handler, roll_result, params_dict)

    effects_raw = move_cfg.get(result_key)
    if effects_raw is None:
        raise ValueError(f"No effects for {move_key}/{result_key}. Add it to engine.yaml move_outcomes.")

    if isinstance(effects_raw, str):
        effects_raw = [effects_raw]
    elif not isinstance(effects_raw, list):
        effects_raw = list(effects_raw)

    effects = parse_effects(effects_raw)
    return apply_effects(game, effects, target_npc_id=target_npc_id)


def _dispatch_handler(game: GameState, handler: str, roll_result: str, params: dict) -> OutcomeResult:
    handlers = {
        "suffer": apply_suffer_handler,
        "threshold": apply_threshold_handler,
        "recovery": apply_recovery_handler,
    }
    if handler not in handlers:
        raise ValueError(f"Unknown move-outcome handler {handler!r}. Valid: {sorted(handlers)}.")
    return handlers[handler](game, roll_result, params)
