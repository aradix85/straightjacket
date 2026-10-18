from collections.abc import Sequence

from ..datasworn.oracle_rolls import roll_generator_tables
from ..datasworn.settings import load_package
from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, FactRequest, GameState, GeneratedEntity, PlaceRecord, ResolvedFact
from .facts import resolve_fact
from .world import locations_match

_FACT_CATEGORY = "fact"


def _check_registered(category: str) -> None:
    categories = eng().generation.categories
    if category not in categories:
        raise KeyError(f"Unknown generation category {category!r}; registered: {categories}")


def generate_fact(game: GameState, request: FactRequest) -> ResolvedFact:
    _check_registered(_FACT_CATEGORY)
    return resolve_fact(game, request)


def generate_entity(game: GameState, category: str) -> GeneratedEntity:
    _check_registered(category)
    if category == _FACT_CATEGORY:
        raise ValueError("A fact is settled by generate_fact, not rolled as an entity")
    pkg = load_package(game.setting_id)
    results = roll_generator_tables(pkg, pkg.generator_tables(category))
    log(f"[Generate] {category}: " + "; ".join(f"{role}={value}" for role, value in results.items()))
    return GeneratedEntity(category=category, results=results)


def resolve_turn_facts(game: GameState, brain: BrainResult) -> list[ResolvedFact]:
    return [generate_fact(game, request) for request in brain.undetermined_facts]


def find_place(game: GameState, name: str) -> PlaceRecord | None:
    if not name:
        return None
    return next((place for place in game.world.places if locations_match(place.name, name)), None)


def current_place(game: GameState) -> PlaceRecord | None:
    return find_place(game, game.world.current_location)


def generate_place_on_arrival(
    game: GameState, brain: BrainResult, moved: bool, earlier: Sequence[PlaceRecord]
) -> PlaceRecord | None:
    change = brain.location_change
    if not moved or change is None:
        return None
    here = game.world.current_location
    if find_place(game, here) is not None:
        return None
    if any(locations_match(here, seen) for seen in game.world.location_history):
        return None
    remembered = next(
        (p for p in earlier if locations_match(p.name, here) and p.entity.category == change.kind),
        None,
    )
    place = remembered or PlaceRecord(name=here, entity=generate_entity(game, change.kind))
    game.world.places.append(place)
    log(f"[Generate] New place {here!r} ({change.kind})")
    return place
