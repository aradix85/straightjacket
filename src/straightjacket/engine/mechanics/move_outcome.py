"""Move outcome resolution: top-level dispatch.

Reads the move_outcomes config block from engine.yaml and dispatches to
either the effect-list pipeline (move_effects.apply_effects) or one of the
named handlers (move_handlers.apply_suffer_handler / apply_recovery_handler
/ apply_threshold_handler).

This module is the public entry point for callers outside mechanics/.
"""

from __future__ import annotations

from ..engine_loader import eng
from ..models import GameState
from .move_effects import OutcomeResult, apply_effects, parse_effects
from .move_handlers import apply_recovery_handler, apply_suffer_handler, apply_threshold_handler


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
