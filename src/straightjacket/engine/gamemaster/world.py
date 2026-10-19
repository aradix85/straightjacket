from __future__ import annotations

import random

from ..logging_util import log
from ..models import BrainResult, GameState, WorldState
from .config import gm


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


def tick_chaos(world: WorldState, direction: int) -> None:
    old = world.chaos_factor
    chaos = gm().chaos
    world.chaos_factor = max(chaos.min, min(chaos.max, world.chaos_factor + direction))
    if world.chaos_factor != old:
        log(f"[World] chaos {old}→{world.chaos_factor}")


def update_chaos_factor(game: GameState, outcome: str, target_npc_id: str | None) -> None:
    _c = gm().chaos
    if outcome in _c.adjust_by_outcome:
        tick_chaos(game.world, _c.adjust_by_outcome[outcome])
    elif outcome == "dialog" and target_npc_id:
        from .npc.matching import find_npc

        npc = find_npc(game, target_npc_id)
        if npc:
            if npc.disposition in _c.dialog_raising_dispositions:
                tick_chaos(game.world, _c.adjust_dialog_hostile)
            elif npc.disposition in _c.dialog_lowering_dispositions:
                tick_chaos(game.world, _c.adjust_dialog_friendly)


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
    from .resolvers import resolve_time_progression

    change = brain.location_change
    moved = update_location(game, change.name) if change is not None else False
    time_prog = resolve_time_progression(brain.move, change is not None)
    advance_time(game, time_prog)
    return moved


def get_pacing_hint(game: GameState) -> str:
    history = game.narrative.scene_intensity_history[-gm().pacing.window_size :]
    if not history:
        return "neutral"

    consecutive_intense = 0
    for h in reversed(history):
        if h in gm().pacing.intense_scene_types:
            consecutive_intense += 1
        else:
            break
    if consecutive_intense >= gm().pacing.intense_threshold:
        return "breather"

    consecutive_calm = 0
    for h in reversed(history):
        if h == "breather":
            consecutive_calm += 1
        else:
            break
    if consecutive_calm >= gm().pacing.calm_threshold:
        return "action"
    return "neutral"


def record_scene_intensity(game: GameState, scene_type: str) -> None:
    window = gm().pacing.window_size
    game.narrative.scene_intensity_history.append(scene_type)
    if len(game.narrative.scene_intensity_history) > window:
        game.narrative.scene_intensity_history = game.narrative.scene_intensity_history[-window:]


def choose_story_structure(tone: str) -> str:
    probability = gm().story.kishotenketsu_probability[tone]
    return "kishotenketsu" if random.random() < probability else "3act"
