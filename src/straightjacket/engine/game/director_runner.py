from ..ai.provider_base import AIProvider
from ..director import apply_director_guidance, call_director
from ..models import GameState
from .turn_types import DirectorCall


def run_deferred_director(provider: AIProvider, game: GameState, director_call: DirectorCall) -> None:
    guidance = call_director(provider, game, director_call.narration, director_call.config)
    apply_director_guidance(game, guidance)
