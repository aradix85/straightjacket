from dataclasses import replace

from straightjacket.engine.ai.provider_base import AIProvider
from straightjacket.engine.engine_loader import eng
from straightjacket.engine.game.turn import build_scene_context, resolve_and_narrate_action
from straightjacket.engine.game.turn_types import BurnOffer, DirectorCall
from straightjacket.engine.models import GameState
from straightjacket.engine.prompt_loader import get_prompt
from straightjacket.engine.ruleset.make_move import RollOutcome
from straightjacket.engine.ruleset.meters import reset_momentum


def process_momentum_burn(
    provider: AIProvider,
    game: GameState,
    offer: BurnOffer,
) -> tuple[str, DirectorCall | None]:
    game.restore(offer.resume_snapshot)
    reset_momentum(game)

    ctx = build_scene_context(
        provider,
        game,
        offer.brain,
        offer.player_words,
        offer.scene_setup,
        pending_random_events=list(offer.random_events),
        facts=list(offer.facts),
        summary_label=get_prompt("history_label_burn"),
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
