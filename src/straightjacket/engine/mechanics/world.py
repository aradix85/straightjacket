"""World-state mechanics: location matching, chaos factor, time progression, pacing."""

from __future__ import annotations

import random

from ..engine_loader import eng
from ..models import BrainResult, GameState

# LOCATION MATCHING


def locations_match(loc_a: str, loc_b: str) -> bool:
    """Fuzzy location comparison for deduplication and spatial guards.

    Empty/blank input is treated as 'unspecified' and matches anything — this
    prevents false negatives when the engine hasn't established a location yet.
    """
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
    if len(shorter) >= 2:
        return set(shorter).issubset(set(longer))
    return shorter[0] == longer[0]


# CHAOS FACTOR SYSTEM


def update_chaos_factor(game: GameState, result: str, target_npc_id: str | None = None) -> None:
    """Adjust chaos factor based on roll result or dialog outcome.

    Action scenes: STRONG_HIT −1, MISS +1, WEAK_HIT no change.
    Dialog scenes: derive from target NPC stance. Hostile/distrustful → +1 (not in control).
    Friendly/loyal → −1 (in control). Neutral/no target → no change.
    """
    _e = eng()
    _c = _e.chaos
    if result == "MISS":
        game.world.tick_chaos(_c.adjust_miss, floor=_c.min, ceiling=_c.max)
    elif result == "STRONG_HIT":
        game.world.tick_chaos(_c.adjust_strong, floor=_c.min, ceiling=_c.max)
    elif result == "dialog" and target_npc_id:
        # circular: npc package ↔ mechanics via prompt_blocks/processing
        from ..npc import find_npc

        npc = find_npc(game, target_npc_id)
        if npc:
            if npc.disposition in ("hostile", "distrustful"):
                game.world.tick_chaos(_c.adjust_dialog_hostile, floor=_c.min, ceiling=_c.max)
            elif npc.disposition in ("friendly", "loyal"):
                game.world.tick_chaos(_c.adjust_dialog_friendly, floor=_c.min, ceiling=_c.max)


# TEMPORAL & SPATIAL CONSISTENCY


def time_phases() -> list[str]:
    """Read time phases from engine.yaml."""
    return list(eng().enums.time_phases)


def advance_time(game: GameState, progression: str) -> None:
    """Advance time_of_day based on Brain's time_progression assessment."""
    phases = time_phases()
    if not game.world.time_of_day or progression in ("none", "short"):
        return
    try:
        idx = phases.index(game.world.time_of_day)
    except ValueError:
        return
    steps_map = eng().get_raw("time_progression_steps")
    steps = steps_map[progression]
    if steps:
        new_idx = (idx + steps) % len(phases)
        game.world.time_of_day = phases[new_idx]


def update_location(game: GameState, new_location: str) -> None:
    """Update current location and maintain location history."""
    if not new_location:
        return
    new_location = new_location.replace("_", " ").strip()
    if not new_location:
        return
    w = game.world
    # First location ever: just set it, no comparison needed
    if not w.current_location:
        w.current_location = new_location
        return
    if locations_match(new_location, w.current_location):
        return
    if w.location_history:
        if locations_match(w.location_history[-1], w.current_location):
            w.location_history[-1] = w.current_location
        else:
            w.location_history.append(w.current_location)
    else:
        w.location_history.append(w.current_location)
    w.location_history = w.location_history[-eng().location.history_size :]
    w.current_location = new_location


def apply_brain_location_time(game: GameState, brain: BrainResult) -> None:
    """Apply location change and engine-resolved time progression."""
    # circular: resolvers → npc → mechanics package
    from .resolvers import resolve_time_progression

    loc = brain.location_change
    has_location_change = bool(loc and loc != "null")
    if loc and has_location_change:
        update_location(game, loc)
    time_prog = resolve_time_progression(brain.move, has_location_change)
    advance_time(game, time_prog)


# SCENE / SEQUEL PACING SYSTEM


def get_pacing_hint(game: GameState) -> str:
    """Analyze recent scene intensity and suggest pacing."""
    _e = eng()
    history = game.narrative.scene_intensity_history[-_e.pacing.window_size :]
    if not history:
        return "neutral"

    consecutive_intense = 0
    for h in reversed(history):
        if h in ("action", "interrupt"):
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
    """Record a scene's intensity type for pacing analysis."""
    window = eng().pacing.window_size
    game.narrative.scene_intensity_history.append(scene_type)
    if len(game.narrative.scene_intensity_history) > window:
        game.narrative.scene_intensity_history = game.narrative.scene_intensity_history[-window:]


# KISHŌTENKETSU STRUCTURE SELECTION


def choose_story_structure(tone: str) -> str:
    """Choose between '3act' and 'kishotenketsu' based on tone probability."""
    _e = eng()
    kprob = _e.story.kishotenketsu_probability
    probability = kprob[tone] if tone in kprob else _e.story.kishotenketsu_fallback_probability
    return "kishotenketsu" if random.random() < probability else "3act"
