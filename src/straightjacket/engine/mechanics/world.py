from __future__ import annotations

import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, GameState


def locations_match(loc_a: str, loc_b: str) -> bool:
    if not loc_a or not loc_b:
        return True

    stop = eng().stopwords.location

    def _words(s: str) -> list[str]:
        return [w for w in s.replace("_", " ").strip().lower().split() if w not in stop]

    wa, wb = _words(loc_a), _words(loc_b)
    if not wa or not wb:
        return False
    if wa == wb:
        return True
    shorter, longer = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    if len(shorter) >= eng().location.word_match_min_words:
        return set(shorter).issubset(set(longer))
    return shorter[0] == longer[0]


def update_chaos_factor(game: GameState, result: str, target_npc_id: str | None) -> None:
    _e = eng()
    _c = _e.chaos
    if result == "MISS":
        game.world.tick_chaos(_c.adjust_miss, floor=_c.min, ceiling=_c.max)
    elif result == "STRONG_HIT":
        game.world.tick_chaos(_c.adjust_strong, floor=_c.min, ceiling=_c.max)
    elif result == "dialog" and target_npc_id:
        from ..npc import find_npc

        npc = find_npc(game, target_npc_id)
        if npc:
            if npc.disposition in _c.dialog_raising_dispositions:
                game.world.tick_chaos(_c.adjust_dialog_hostile, floor=_c.min, ceiling=_c.max)
            elif npc.disposition in _c.dialog_lowering_dispositions:
                game.world.tick_chaos(_c.adjust_dialog_friendly, floor=_c.min, ceiling=_c.max)


def advance_time(game: GameState, progression: str) -> None:
    steps = eng().time_progression_steps.mapping[progression]
    phases = eng().enums.time_phases
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
    w.location_history = w.location_history[-eng().location.history_size :]
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
    _e = eng()
    history = game.narrative.scene_intensity_history[-_e.pacing.window_size :]
    if not history:
        return "neutral"

    consecutive_intense = 0
    for h in reversed(history):
        if h in _e.pacing.intense_scene_types:
            consecutive_intense += 1
        else:
            break
    if consecutive_intense >= _e.pacing.intense_threshold:
        return "breather"

    consecutive_calm = 0
    for h in reversed(history):
        if h == "breather":
            consecutive_calm += 1
        else:
            break
    if consecutive_calm >= _e.pacing.calm_threshold:
        return "action"
    return "neutral"


def record_scene_intensity(game: GameState, scene_type: str) -> None:
    window = eng().pacing.window_size
    game.narrative.scene_intensity_history.append(scene_type)
    if len(game.narrative.scene_intensity_history) > window:
        game.narrative.scene_intensity_history = game.narrative.scene_intensity_history[-window:]


def choose_story_structure(tone: str) -> str:
    probability = eng().story.kishotenketsu_probability[tone]
    return "kishotenketsu" if random.random() < probability else "3act"
