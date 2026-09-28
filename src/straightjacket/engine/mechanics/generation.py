from collections.abc import Callable

from ..engine_loader import eng
from ..models import BrainResult, FactRequest, GameState, ResolvedFact
from .facts import resolve_fact

_GENERATORS: dict[str, Callable[[GameState, FactRequest], ResolvedFact]] = {
    "fact": resolve_fact,
}


def generate(game: GameState, category: str, context: FactRequest) -> ResolvedFact:
    categories = eng().generation.categories
    if category not in categories:
        raise KeyError(f"Unknown generation category {category!r}; registered: {categories}")
    return _GENERATORS[category](game, context)


def resolve_turn_facts(game: GameState, brain: BrainResult) -> list[ResolvedFact]:
    return [generate(game, "fact", request) for request in brain.undetermined_facts]
