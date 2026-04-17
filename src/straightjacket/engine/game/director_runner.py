#!/usr/bin/env python3
"""Director runner: deferred Director call."""

from ..ai.provider_base import AIProvider
from ..director import apply_director_guidance, call_director
from ..logging_util import log
from ..models import GameState


def run_deferred_director(provider: AIProvider, game: GameState, director_ctx: dict) -> None:
    """Run the Director call that was deferred from process_turn.
    Called by the UI layer AFTER rendering narration for non-blocking display.
    Modifies game state in-place (adds guidance + reflections)."""
    try:
        narration = director_ctx["narration"]
        config = director_ctx.get("config")
        guidance = call_director(provider, game, narration, config)
        apply_director_guidance(game, guidance)
    except Exception as e:
        # Intentional graceful degradation — see AI-CALL SUPPRESSION POLICY in provider_base.py.
        log(f"[Director] Deferred call failed gracefully: {e}", level="warning")
