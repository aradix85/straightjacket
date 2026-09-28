from dataclasses import replace
from typing import Any

from ..ai.provider_base import AIProvider
from ..engine_loader import eng
from ..models import EngineConfig, GameState
from .turn import build_scene_context, resolve_and_narrate_action
from .turn_types import BurnOffer, RollOutcome


def process_momentum_burn(
    provider: AIProvider,
    game: GameState,
    offer: BurnOffer,
    config: EngineConfig | None,
) -> tuple[GameState, str, dict[str, Any] | None]:
    game.restore(offer.resume_snapshot)
    _e = eng()
    game.resources.reset_momentum(
        reset_floor=_e.momentum.reset_floor, reset_value=_e.momentum.start, max_cap=_e.momentum.max
    )

    ctx = build_scene_context(
        provider,
        game,
        offer.brain,
        config,
        offer.player_words,
        offer.scene_setup,
        list(offer.random_events),
        list(offer.facts),
    )
    outcome = RollOutcome(
        roll=replace(offer.roll, result=offer.new_result),
        ds_move=offer.ds_move,
        track=None,
        is_progress_roll=False,
    )
    narration, director_ctx = resolve_and_narrate_action(ctx, outcome, burned=True)
    return game, narration, director_ctx
