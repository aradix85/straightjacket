from dataclasses import replace

from ..ai.provider_base import AIProvider
from ..engine_loader import eng
from ..models import GameState
from ..prompt_loader import get_prompt
from .turn import build_scene_context, resolve_and_narrate_action
from .turn_types import BurnOffer, DirectorCall, RollOutcome


def process_momentum_burn(
    provider: AIProvider,
    game: GameState,
    offer: BurnOffer,
) -> tuple[GameState, str, DirectorCall | None]:
    game.restore(offer.resume_snapshot)
    _e = eng()
    game.resources.reset_momentum(
        reset_floor=_e.momentum.reset_floor, reset_value=_e.momentum.start, max_cap=_e.momentum.max
    )

    ctx = build_scene_context(
        provider,
        game,
        offer.brain,
        offer.player_words,
        offer.scene_setup,
        list(offer.random_events),
        list(offer.facts),
        get_prompt("history_label_burn"),
        stream=None,
        narrator_note=_e.ai_text.narrator_defaults["momentum_burn_injection"],
    )
    outcome = RollOutcome(
        roll=replace(offer.roll, result=offer.new_result),
        ds_move=offer.ds_move,
        track=None,
        is_progress_roll=False,
    )
    narration, director_ctx = resolve_and_narrate_action(ctx, outcome)
    return game, narration, director_ctx
