from dataclasses import replace

from ..ai.provider_base import AIProvider
from ..engine_loader import eng
from ..models import GameState
from ..prompt_loader import get_prompt
from ..ruleset.config import rules
from .turn import build_scene_context, resolve_and_narrate_action
from .turn_types import BurnOffer, DirectorCall, RollOutcome


def process_momentum_burn(
    provider: AIProvider,
    game: GameState,
    offer: BurnOffer,
) -> tuple[str, DirectorCall | None]:
    game.restore(offer.resume_snapshot)
    game.resources.reset_momentum(
        reset_floor=rules().momentum.reset_floor, reset_value=rules().momentum.start, max_cap=rules().momentum.max
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
        narrator_note=eng().ai_text.narrator_defaults["momentum_burn_injection"],
    )
    outcome = RollOutcome(
        roll=replace(offer.roll, result=offer.new_result),
        ds_move=offer.ds_move,
        track=None,
    )
    narration, director_ctx = resolve_and_narrate_action(ctx, outcome)
    return narration, director_ctx
