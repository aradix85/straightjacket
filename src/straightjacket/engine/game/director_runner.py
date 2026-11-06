from straightjacket.engine.ai.provider_base import AIProvider
from straightjacket.engine.director import apply_director_guidance, call_director
from straightjacket.engine.game.turn_types import DirectorCall
from straightjacket.engine.models import GameState


def run_deferred_director(provider: AIProvider, game: GameState, director_call: DirectorCall) -> None:
    guidance = call_director(provider, game, director_call.narration)
    apply_director_guidance(game, guidance)
