from collections.abc import Callable, Sequence

from ..engine_loader import eng
from ..logging_util import log
from ..models import FactRequest, GameState, ResolvedFact
from ..npc import find_npc
from .fate import resolve_fate, score_to_odds
from .world import locations_match


def _npc_disposition(game: GameState, request: FactRequest) -> int:
    npc = find_npc(game, request.about)
    if npc is None:
        raise ValueError(f"fact input npc_disposition needs an NPC, got about={request.about!r}")
    return eng().fate.likelihood_rules.disposition_scores[npc.disposition]


_INPUTS: dict[str, Callable[[GameState, FactRequest], int]] = {
    "npc_disposition": _npc_disposition,
}


def fact_odds(game: GameState, request: FactRequest) -> str:
    spec = eng().fact_resolution.types[request.fact_type]
    score = spec.base_score + sum(weight * _INPUTS[name](game, request) for name, weight in spec.inputs.items())
    return score_to_odds(score)


def find_fact(game: GameState, about: str, fact_type: str) -> ResolvedFact | None:
    for fact in game.world.facts:
        if fact.about == about and fact.fact_type == fact_type:
            return fact
    return None


def _about_name(game: GameState, request: FactRequest) -> str:
    if eng().fact_resolution.types[request.fact_type].subject == "place":
        return game.world.current_location
    npc = find_npc(game, request.about)
    if npc is None:
        raise ValueError(f"fact {request.fact_type!r} is about an NPC that does not exist: {request.about!r}")
    return npc.name


def resolve_fact(game: GameState, request: FactRequest) -> ResolvedFact:
    known = find_fact(game, request.about, request.fact_type)
    if known is not None:
        log(f"[Fact] Reused {request.fact_type} about {known.about_name}: {known.answer}")
        return known
    odds = fact_odds(game, request)
    fate = resolve_fate(game, odds, game.world.chaos_factor, question=f"{request.fact_type}:{request.about}")
    fact = ResolvedFact(
        about=request.about,
        about_name=_about_name(game, request),
        fact_type=request.fact_type,
        answer=fate.answer,
        odds=odds,
        location=game.world.current_location,
    )
    game.world.facts.append(fact)
    log(f"[Fact] Resolved {fact.fact_type} about {fact.about_name}: {fact.answer} ({odds})")
    return fact


_YES_ANSWERS = ("yes", "exceptional_yes")


def clear_facts_settled_by_hit(game: GameState, facts: Sequence[ResolvedFact], result: str) -> None:
    if result not in ("STRONG_HIT", "WEAK_HIT"):
        return
    types = eng().fact_resolution.types
    settled = {(f.about, f.fact_type) for f in facts if f.answer in _YES_ANSWERS and types[f.fact_type].cleared_by_hit}
    if not settled:
        return
    game.world.facts = [f for f in game.world.facts if (f.about, f.fact_type) not in settled]
    log(f"[Fact] Settled by {result}: {sorted(t for _, t in settled)}")


def facts_of_this_place(game: GameState, facts: Sequence[ResolvedFact]) -> list[ResolvedFact]:
    return [f for f in facts if locations_match(f.location, game.world.current_location)]


def remember_facts(game: GameState, facts: Sequence[ResolvedFact]) -> None:
    for fact in facts_of_this_place(game, facts):
        if find_fact(game, fact.about, fact.fact_type) is None:
            game.world.facts.append(fact)
