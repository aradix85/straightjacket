from ..ai.provider_base import AIProvider
from ..director import apply_director_guidance, call_director
from ..logging_util import log
from ..models import GameState


def run_deferred_director(provider: AIProvider, game: GameState, director_ctx: dict) -> None:
    try:
        narration = director_ctx["narration"]
        config = director_ctx.get("config")
        guidance = call_director(provider, game, narration, config)
        apply_director_guidance(game, guidance)
    except Exception as e:
        log(f"[Director] Deferred call failed gracefully: {e}", level="warning")
