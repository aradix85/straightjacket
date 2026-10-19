from __future__ import annotations

from ..logging_util import log
from ..models import BrainResult, GameState, WorldState
from .config import gm
from .questions import answers


def locations_match(loc_a: str, loc_b: str) -> bool:
    if not loc_a or not loc_b:
        return True

    stop = gm().stopwords.location

    def _words(s: str) -> list[str]:
        return [w for w in s.replace("_", " ").strip().lower().split() if w not in stop]

    wa, wb = _words(loc_a), _words(loc_b)
    if not wa or not wb:
        return False
    if wa == wb:
        return True
    shorter, longer = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    if len(shorter) >= gm().location.word_match_min_words:
        return set(shorter).issubset(set(longer))
    return shorter[0] == longer[0]


def new_world() -> WorldState:
    return WorldState(chaos_factor=gm().chaos.start)


def resolve_time_progression(move: str, has_location_change: bool) -> str:
    if has_location_change:
        return gm().location.change_time
    if move in gm().moves:
        return gm().moves[move].time
    return answers().time_taken(move)


def advance_time(game: GameState, progression: str) -> None:
    steps = gm().time_progression_steps.mapping[progression]
    phases = gm().enums.time_phases
    game.world.time_of_day = phases[(phases.index(game.world.time_of_day) + steps) % len(phases)]


def clear_facts(game: GameState) -> None:
    if game.world.facts:
        log(f"[Fact] Cleared {len(game.world.facts)} fact(s) of {game.world.current_location!r}")
        game.world.facts = []


def update_location(game: GameState, new_location: str) -> bool:
    new_location = new_location.replace("_", " ").strip()
    if not new_location:
        return False
    w = game.world

    if not w.current_location:
        w.current_location = new_location
        return True
    if locations_match(new_location, w.current_location):
        return False
    clear_facts(game)
    if w.location_history:
        if locations_match(w.location_history[-1], w.current_location):
            w.location_history[-1] = w.current_location
        else:
            w.location_history.append(w.current_location)
    else:
        w.location_history.append(w.current_location)
    w.location_history = w.location_history[-gm().location.history_size :]
    w.current_location = new_location
    return True


def apply_brain_location_time(game: GameState, brain: BrainResult) -> bool:
    change = brain.location_change
    moved = update_location(game, change.name) if change is not None else False
    time_prog = resolve_time_progression(brain.move, change is not None)
    advance_time(game, time_prog)
    return moved
